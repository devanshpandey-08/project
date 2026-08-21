"""Unified resilience policies: Retry, Circuit Breaker, Timeout, Rate Limiter."""
import asyncio
import time
from typing import Any, Callable, Dict, List, Optional, TypeVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from collections import deque
import threading

T = TypeVar('T')


class CircuitState(Enum):
    CLOSED = auto()
    OPEN = auto()
    HALF_OPEN = auto()


@dataclass
class RetryPolicy:
    """Exponential backoff retry policy with jitter."""
    
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    
    def get_delay(self, attempt: int) -> float:
        delay = self.base_delay * (self.exponential_base ** attempt)
        
        if self.jitter:
            import random
            delay = delay * (0.5 + random.random())
        
        return min(delay, self.max_delay)


@dataclass
class CircuitBreaker:
    """Circuit breaker for fault tolerance."""
    
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    half_open_max_calls: int = 3
    
    state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    failure_count: int = field(default=0, init=False)
    success_count: int = field(default=0, init=False)
    last_failure_time: Optional[float] = field(default=None, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    
    def call(self, func: Callable[[], T]) -> T:
        with self._lock:
            self._check_state()
            
            if self.state == CircuitState.OPEN:
                raise RuntimeError("Circuit breaker is OPEN")
        
        try:
            result = func()
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    async def call_async(self, func: Callable[[], Any]) -> Any:
        with self._lock:
            self._check_state()
            
            if self.state == CircuitState.OPEN:
                raise RuntimeError("Circuit breaker is OPEN")
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func()
            else:
                result = func()
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _check_state(self) -> None:
        if self.state == CircuitState.OPEN:
            if self.last_failure_time and (time.time() - self.last_failure_time) > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
    
    def _on_success(self) -> None:
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.half_open_max_calls:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
            elif self.state == CircuitState.CLOSED:
                self.failure_count = 0
    
    def _on_failure(self) -> None:
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN


@dataclass
class TimeoutPolicy:
    """Timeout policy for operation limits."""
    
    timeout_seconds: float = 30.0
    
    async def execute(self, func: Callable[[], Any], *args, **kwargs) -> Any:
        try:
            if asyncio.iscoroutinefunction(func):
                return await asyncio.wait_for(func(*args, **kwargs), timeout=self.timeout_seconds)
            else:
                return await asyncio.wait_for(
                    asyncio.to_thread(func, *args, **kwargs),
                    timeout=self.timeout_seconds
                )
        except asyncio.TimeoutError:
            raise TimeoutError(f"Operation timed out after {self.timeout_seconds}s")


@dataclass
class RateLimiter:
    """Token bucket rate limiter with sliding window."""
    
    rate_limit: int = 60  # requests per window
    window_seconds: float = 60.0
    burst_size: int = 10
    
    _tokens: float = field(default=0.0, init=False)
    _last_update: float = field(default_factory=time.time, init=False)
    _requests: deque = field(default_factory=lambda: deque(maxlen=1000), init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    
    def __post_init__(self):
        self._tokens = float(self.burst_size)
    
    async def acquire(self) -> bool:
        async with self._lock:
            now = time.time()
            
            # Token bucket refill
            elapsed = now - self._last_update
            self._tokens = min(self.burst_size, self._tokens + elapsed * (self.rate_limit / self.window_seconds))
            self._last_update = now
            
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            
            # Sliding window check
            window_start = now - self.window_seconds
            while self._requests and self._requests[0] < window_start:
                self._requests.popleft()
            
            if len(self._requests) < self.rate_limit:
                self._requests.append(now)
                return True
            
            return False
    
    async def wait_and_acquire(self) -> None:
        while not await self.acquire():
            await asyncio.sleep(0.1)
    
    def get_remaining(self) -> int:
        now = time.time()
        window_start = now - self.window_seconds
        
        while self._requests and self._requests[0] < window_start:
            self._requests.popleft()
        
        return max(0, self.rate_limit - len(self._requests))
