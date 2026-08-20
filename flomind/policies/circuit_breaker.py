"""
Circuit breaker policy for FlowMind.

Provides circuit breaker pattern for fault tolerance.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, TypeVar
import asyncio
import time

T = TypeVar('T')


class CircuitState:
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    """
    Circuit breaker for fault tolerance.
    
    Usage:
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=30.0)
        result = await cb.execute(my_async_function, arg1, arg2)
    """
    
    failure_threshold: int = 5
    success_threshold: int = 2
    recovery_timeout: float = 30.0
    timeout_seconds: float = 60.0
    
    _state: str = field(default=CircuitState.CLOSED, init=False)
    _failures: int = field(default=0, init=False)
    _successes: int = field(default=0, init=False)
    _last_failure_time: Optional[float] = field(default=None, init=False)
    
    @property
    def state(self) -> str:
        """Get current circuit state."""
        if self._state == CircuitState.OPEN:
            # Check if we should transition to half-open
            if self._last_failure_time is not None:
                elapsed = time.time() - self._last_failure_time
                if elapsed >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._successes = 0
        return self._state
    
    async def execute(
        self,
        func: Callable[..., T],
        *args,
        **kwargs
    ) -> T:
        """Execute a function with circuit breaker protection."""
        if self.state == CircuitState.OPEN:
            raise CircuitBreakerOpen("Circuit breaker is open")
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=self.timeout_seconds
                )
            else:
                loop = asyncio.get_event_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: func(*args, **kwargs)),
                    timeout=self.timeout_seconds
                )
            
            self._on_success()
            return result
            
        except Exception as e:
            self._on_failure()
            raise
    
    def _on_success(self) -> None:
        """Handle successful execution."""
        if self._state == CircuitState.HALF_OPEN:
            self._successes += 1
            if self._successes >= self.success_threshold:
                self._state = CircuitState.CLOSED
                self._failures = 0
                self._successes = 0
        elif self._state == CircuitState.CLOSED:
            self._failures = 0
    
    def _on_failure(self) -> None:
        """Handle failed execution."""
        self._failures += 1
        self._last_failure_time = time.time()
        
        if self._failures >= self.failure_threshold:
            self._state = CircuitState.OPEN
    
    def reset(self) -> None:
        """Reset the circuit breaker."""
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._successes = 0
        self._last_failure_time = None
    
    def wrap(self, func: Callable[..., T]) -> Callable[..., T]:
        """Wrap a function with circuit breaker logic."""
        async def wrapper(*args, **kwargs):
            return await self.execute(func, *args, **kwargs)
        return wrapper


class CircuitBreakerOpen(Exception):
    """Exception raised when circuit breaker is open."""
    pass
