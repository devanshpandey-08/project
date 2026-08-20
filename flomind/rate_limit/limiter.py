"""Rate limiting with Token Bucket and Sliding Window algorithms."""

import time
from typing import Any, Dict, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import threading


@dataclass
class RateLimitPolicy:
    """Rate limit policy configuration."""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    requests_per_day: int = 10000
    burst_size: int = 10  # Max requests in a short burst
    
    def to_dict(self) -> Dict[str, int]:
        return {
            "per_minute": self.requests_per_minute,
            "per_hour": self.requests_per_hour,
            "per_day": self.requests_per_day,
            "burst": self.burst_size
        }


class TokenBucket:
    """Token bucket rate limiter for burst handling."""
    
    def __init__(self, capacity: int, refill_rate: float):
        """
        Initialize token bucket.
        
        Args:
            capacity: Maximum tokens in bucket
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = float(capacity)
        self.last_refill = time.time()
        self._lock = threading.Lock()
        
    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now
        
    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens.
        
        Returns:
            True if tokens were consumed, False if rate limited
        """
        with self._lock:
            self._refill()
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False
            
    def get_tokens(self) -> float:
        """Get current token count."""
        with self._lock:
            self._refill()
            return self.tokens
            
    def wait_time(self, tokens: int = 1) -> float:
        """Calculate wait time for tokens to be available."""
        with self._lock:
            self._refill()
            if self.tokens >= tokens:
                return 0.0
            tokens_needed = tokens - self.tokens
            return tokens_needed / self.refill_rate


class SlidingWindowCounter:
    """Sliding window rate limiter for accurate counting."""
    
    def __init__(self, window_size: int, max_requests: int):
        """
        Initialize sliding window counter.
        
        Args:
            window_size: Window size in seconds
            max_requests: Maximum requests per window
        """
        self.window_size = window_size
        self.max_requests = max_requests
        self.requests: Dict[str, list] = defaultdict(list)
        self._lock = threading.Lock()
        
    def _clean_old_requests(self, key: str) -> None:
        """Remove requests outside the current window."""
        now = time.time()
        cutoff = now - self.window_size
        
        if key in self.requests:
            self.requests[key] = [t for t in self.requests[key] if t > cutoff]
            
    def allow(self, key: str = "default") -> bool:
        """
        Check if request is allowed.
        
        Args:
            key: Identifier for the rate limit bucket (e.g., user_id)
            
        Returns:
            True if allowed, False if rate limited
        """
        with self._lock:
            self._clean_old_requests(key)
            
            if len(self.requests[key]) < self.max_requests:
                self.requests[key].append(time.time())
                return True
            return False
            
    def get_count(self, key: str = "default") -> int:
        """Get current request count in window."""
        with self._lock:
            self._clean_old_requests(key)
            return len(self.requests.get(key, []))
            
    def get_remaining(self, key: str = "default") -> int:
        """Get remaining requests in window."""
        return max(0, self.max_requests - self.get_count(key))


class RateLimiter:
    """
    Enterprise rate limiter combining multiple algorithms.
    
    Features:
    - Token bucket for burst handling
    - Sliding window for accurate counting
    - Per-user/tenant isolation
    - Hierarchical limits (minute/hour/day)
    - HTTP header compatibility
    """
    
    def __init__(self, policy: Optional[RateLimitPolicy] = None):
        """Initialize rate limiter with policy."""
        self.policy = policy or RateLimitPolicy()
        
        # Token buckets for burst control
        self._buckets: Dict[str, TokenBucket] = {}
        
        # Sliding windows for different time periods
        self._minute_window = SlidingWindowCounter(60, self.policy.requests_per_minute)
        self._hour_window = SlidingWindowCounter(3600, self.policy.requests_per_hour)
        self._day_window = SlidingWindowCounter(86400, self.policy.requests_per_day)
        
        self._lock = threading.Lock()
        
    def _get_bucket(self, key: str) -> TokenBucket:
        """Get or create token bucket for key."""
        if key not in self._buckets:
            self._buckets[key] = TokenBucket(
                capacity=self.policy.burst_size,
                refill_rate=self.policy.requests_per_minute / 60.0
            )
        return self._buckets[key]
        
    def allow_request(self, key: str = "default") -> Tuple[bool, Dict[str, Any]]:
        """
        Check if request is allowed.
        
        Args:
            key: Identifier (user_id, IP, API key, etc.)
            
        Returns:
            Tuple of (allowed, metadata dict)
        """
        from typing import Any
        
        metadata = {
            "key": key,
            "limited": False,
            "retry_after": 0,
            "limits": {
                "minute": self._minute_window.get_remaining(key),
                "hour": self._hour_window.get_remaining(key),
                "day": self._day_window.get_remaining(key)
            }
        }
        
        # Check all limits
        bucket = self._get_bucket(key)
        
        if not bucket.consume():
            metadata["limited"] = True
            metadata["reason"] = "burst_limit"
            metadata["retry_after"] = bucket.wait_time()
            return False, metadata
            
        if not self._minute_window.allow(key):
            metadata["limited"] = True
            metadata["reason"] = "minute_limit"
            metadata["retry_after"] = 60
            return False, metadata
            
        if not self._hour_window.allow(key):
            metadata["limited"] = True
            metadata["reason"] = "hour_limit"
            metadata["retry_after"] = 3600
            return False, metadata
            
        if not self._day_window.allow(key):
            metadata["limited"] = True
            metadata["reason"] = "day_limit"
            metadata["retry_after"] = 86400
            return False, metadata
            
        # Update remaining counts after successful request
        metadata["limits"] = {
            "minute": self._minute_window.get_remaining(key),
            "hour": self._hour_window.get_remaining(key),
            "day": self._day_window.get_remaining(key)
        }
        
        return True, metadata
        
    def get_headers(self, key: str = "default") -> Dict[str, str]:
        """
        Get rate limit headers for HTTP response.
        
        Returns headers compatible with RFC 6585.
        """
        _, metadata = self.allow_request(key)
        
        return {
            "X-RateLimit-Limit-Minute": str(self.policy.requests_per_minute),
            "X-RateLimit-Remaining-Minute": str(metadata["limits"]["minute"]),
            "X-RateLimit-Limit-Hour": str(self.policy.requests_per_hour),
            "X-RateLimit-Remaining-Hour": str(metadata["limits"]["hour"]),
            "X-RateLimit-Limit-Day": str(self.policy.requests_per_day),
            "X-RateLimit-Remaining-Day": str(metadata["limits"]["day"]),
            **({"Retry-After": str(int(metadata["retry_after"]))} if metadata["limited"] else {})
        }
        
    def reset(self, key: str) -> None:
        """Reset rate limits for a specific key."""
        with self._lock:
            if key in self._buckets:
                del self._buckets[key]
            self._minute_window.requests.pop(key, None)
            self._hour_window.requests.pop(key, None)
            self._day_window.requests.pop(key, None)
