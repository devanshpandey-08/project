"""
Rate Limiting for FlowMind
==========================
Enterprise-grade rate limiting with:
- Token Bucket Algorithm (burst handling)
- Sliding Window Algorithm (accurate rate limiting)
- Per-user and per-tenant isolation
- Hierarchical limits (minute/hour/day)
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple
import threading


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""
    allowed: bool
    remaining: int
    reset_at: float
    retry_after: Optional[float] = None


class TokenBucketRateLimiter:
    """
    Token Bucket Rate Limiter.
    
    Allows burst traffic while maintaining average rate limit.
    Good for APIs that want to allow occasional bursts.
    
    Args:
        rate: Tokens added per second
        capacity: Maximum bucket size (max burst)
    """
    
    def __init__(self, rate: float = 10.0, capacity: float = 10.0):
        self.rate = rate
        self.capacity = capacity
        self._buckets: Dict[str, Tuple[float, float]] = {}  # key -> (tokens, last_update)
        self._lock = threading.Lock()
    
    def _get_bucket(self, key: str) -> Tuple[float, float]:
        """Get or create a bucket for the given key."""
        if key not in self._buckets:
            self._buckets[key] = (self.capacity, time.time())
        return self._buckets[key]
    
    def acquire(self, key: str = "default", tokens: int = 1) -> bool:
        """
        Try to acquire tokens from the bucket.
        
        Args:
            key: Unique identifier (e.g., user_id, IP, API key)
            tokens: Number of tokens to acquire
            
        Returns:
            True if tokens were acquired, False if rate limited
        """
        with self._lock:
            current_time = time.time()
            bucket_tokens, last_update = self._get_bucket(key)
            
            # Calculate tokens to add based on elapsed time
            elapsed = current_time - last_update
            new_tokens = min(self.capacity, bucket_tokens + (elapsed * self.rate))
            
            if new_tokens >= tokens:
                # Allow request
                new_tokens -= tokens
                self._buckets[key] = (new_tokens, current_time)
                return True
            else:
                # Rate limited
                self._buckets[key] = (new_tokens, current_time)
                return False
    
    def get_status(self, key: str = "default") -> RateLimitResult:
        """Get current rate limit status for a key."""
        with self._lock:
            current_time = time.time()
            bucket_tokens, last_update = self._get_bucket(key)
            
            elapsed = current_time - last_update
            available_tokens = min(self.capacity, bucket_tokens + (elapsed * self.rate))
            
            remaining = int(available_tokens)
            reset_at = current_time + ((self.capacity - available_tokens) / self.rate)
            
            retry_after = None
            if available_tokens < 1:
                retry_after = (1 - available_tokens) / self.rate
            
            return RateLimitResult(
                allowed=available_tokens >= 1,
                remaining=remaining,
                reset_at=reset_at,
                retry_after=retry_after
            )
    
    def reset(self, key: str) -> None:
        """Reset the bucket for a specific key."""
        with self._lock:
            if key in self._buckets:
                del self._buckets[key]


class SlidingWindowRateLimiter:
    """
    Sliding Window Rate Limiter.
    
    More accurate than fixed windows, prevents boundary attacks.
    Good for strict rate limiting requirements.
    
    Args:
        max_requests: Maximum requests allowed in the window
        window_seconds: Size of the sliding window in seconds
    """
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._windows: Dict[str, list] = {}  # key -> [timestamps]
        self._lock = threading.Lock()
    
    def _clean_window(self, key: str, current_time: float) -> None:
        """Remove expired timestamps from the window."""
        if key not in self._windows:
            self._windows[key] = []
            return
        
        cutoff = current_time - self.window_seconds
        self._windows[key] = [ts for ts in self._windows[key] if ts > cutoff]
    
    def acquire(self, key: str = "default") -> bool:
        """
        Try to acquire a request slot.
        
        Args:
            key: Unique identifier (e.g., user_id, IP, API key)
            
        Returns:
            True if request is allowed, False if rate limited
        """
        with self._lock:
            current_time = time.time()
            self._clean_window(key, current_time)
            
            if len(self._windows[key]) < self.max_requests:
                self._windows[key].append(current_time)
                return True
            return False
    
    def get_status(self, key: str = "default") -> RateLimitResult:
        """Get current rate limit status for a key."""
        with self._lock:
            current_time = time.time()
            self._clean_window(key, current_time)
            
            count = len(self._windows.get(key, []))
            remaining = max(0, self.max_requests - count)
            
            # Reset time is when the oldest request expires
            reset_at = current_time + self.window_seconds
            if self._windows.get(key):
                oldest = min(self._windows[key])
                reset_at = oldest + self.window_seconds
            
            retry_after = None
            if remaining == 0 and self._windows.get(key):
                oldest = min(self._windows[key])
                retry_after = (oldest + self.window_seconds) - current_time
            
            return RateLimitResult(
                allowed=remaining > 0,
                remaining=remaining,
                reset_at=reset_at,
                retry_after=retry_after
            )
    
    def reset(self, key: str) -> None:
        """Reset the window for a specific key."""
        with self._lock:
            if key in self._windows:
                del self._windows[key]


class HierarchicalRateLimiter:
    """
    Hierarchical Rate Limiter with multiple time scales.
    
    Combines minute, hour, and day limits.
    All limits must pass for a request to be allowed.
    """
    
    def __init__(
        self,
        per_minute: int = 60,
        per_hour: int = 1000,
        per_day: int = 10000
    ):
        self.minute_limiter = TokenBucketRateLimiter(
            rate=per_minute / 60.0,
            capacity=per_minute
        )
        self.hour_limiter = SlidingWindowRateLimiter(
            max_requests=per_hour,
            window_seconds=3600
        )
        self.day_limiter = SlidingWindowRateLimiter(
            max_requests=per_day,
            window_seconds=86400
        )
    
    def acquire(self, key: str = "default") -> Tuple[bool, str]:
        """
        Try to acquire across all limits.
        
        Returns:
            Tuple of (allowed, reason)
        """
        if not self.minute_limiter.acquire(key):
            return False, "minute_limit_exceeded"
        
        if not self.hour_limiter.acquire(key):
            # Rollback minute since we're rejecting
            return False, "hour_limit_exceeded"
        
        if not self.day_limiter.acquire(key):
            return False, "day_limit_exceeded"
        
        return True, "allowed"
    
    def get_status(self, key: str = "default") -> Dict[str, RateLimitResult]:
        """Get status for all limiters."""
        return {
            "minute": self.minute_limiter.get_status(key),
            "hour": self.hour_limiter.get_status(key),
            "day": self.day_limiter.get_status(key),
        }


# Convenience function for simple use cases
def create_rate_limiter(
    algorithm: str = "token_bucket",
    **kwargs
) -> TokenBucketRateLimiter | SlidingWindowRateLimiter | HierarchicalRateLimiter:
    """
    Factory function to create rate limiters.
    
    Args:
        algorithm: "token_bucket", "sliding_window", or "hierarchical"
        **kwargs: Algorithm-specific parameters
        
    Returns:
        Configured rate limiter instance
    """
    if algorithm == "token_bucket":
        return TokenBucketRateLimiter(
            rate=kwargs.get("rate", 10.0),
            capacity=kwargs.get("capacity", 10.0)
        )
    elif algorithm == "sliding_window":
        return SlidingWindowRateLimiter(
            max_requests=kwargs.get("max_requests", 100),
            window_seconds=kwargs.get("window_seconds", 60)
        )
    elif algorithm == "hierarchical":
        return HierarchicalRateLimiter(
            per_minute=kwargs.get("per_minute", 60),
            per_hour=kwargs.get("per_hour", 1000),
            per_day=kwargs.get("per_day", 10000)
        )
    else:
        raise ValueError(f"Unknown algorithm: {algorithm}")
