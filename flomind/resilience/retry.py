"""
FlowMind Resilience Patterns

Production systems fail. FlowMind handles failures gracefully with:
1. Retry with exponential backoff and jitter
2. Circuit breaker to prevent cascade failures
3. Timeout policies for slow operations
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Optional, TypeVar, Coroutine
import asyncio
import time
import random
from enum import Enum

T = TypeVar('T')


class CircuitState(Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing fast
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class RetryStrategy:
    """
    Retry configuration with exponential backoff and jitter.
    
    Why jitter? Without it, retries from many clients can synchronize
    and overwhelm the service when it recovers (thundering herd).
    """
    max_retries: int = 3
    base_delay: float = 1.0  # seconds
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number."""
        delay = self.base_delay * (self.exponential_base ** attempt)
        delay = min(delay, self.max_delay)
        
        if self.jitter:
            # Add ±25% jitter
            delay = delay * (0.75 + random.random() * 0.5)
        
        return delay


@dataclass
class CircuitBreaker:
    """
    Circuit breaker to prevent cascade failures.
    
    When a service fails repeatedly, open the circuit to:
    1. Give the service time to recover
    2. Prevent wasting resources on doomed requests
    3. Fail fast instead of timing out
    """
    failure_threshold: int = 5
    recovery_timeout: float = 30.0  # seconds
    half_open_max_calls: int = 3
    
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[float] = None
    half_open_calls: int = 0
    
    def record_success(self):
        """Record a successful call."""
        self.failure_count = 0
        self.success_count += 1
        
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_calls += 1
            if self.half_open_calls >= self.half_open_max_calls:
                # Recovered, close circuit
                self.state = CircuitState.CLOSED
                self.half_open_calls = 0
    
    def record_failure(self):
        """Record a failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        self.success_count = 0
        
        if self.state == CircuitState.HALF_OPEN:
            # Failed during recovery test, reopen circuit
            self.state = CircuitState.OPEN
            self.half_open_calls = 0
        elif self.failure_count >= self.failure_threshold:
            # Threshold reached, open circuit
            self.state = CircuitState.OPEN
    
    def can_execute(self) -> bool:
        """Check if a call can be executed."""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if self.last_failure_time:
                elapsed = time.time() - self.last_failure_time
                if elapsed >= self.recovery_timeout:
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_calls = 0
                    return True
            return False
        
        # HALF_OPEN state
        return self.half_open_calls < self.half_open_max_calls


@dataclass
class TimeoutPolicy:
    """Timeout configuration for operations."""
    timeout_seconds: float = 30.0
    
    async def execute_with_timeout(self, coro, operation_name: str = "operation") -> Any:
        """Execute a coroutine with timeout."""
        try:
            return await asyncio.wait_for(coro, timeout=self.timeout_seconds)
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"{operation_name} timed out after {self.timeout_seconds}s"
            )


class ResilientExecutor:
    """
    Combines retry, circuit breaker, and timeout for resilient execution.
    
    Usage:
        executor = ResilientExecutor()
        result = await executor.execute(my_async_func, arg1, arg2)
    """
    
    def __init__(self, 
                 retry_strategy: Optional[RetryStrategy] = None,
                 circuit_breaker: Optional[CircuitBreaker] = None,
                 timeout_policy: Optional[TimeoutPolicy] = None):
        self.retry_strategy = retry_strategy or RetryStrategy()
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self.timeout_policy = timeout_policy or TimeoutPolicy()
    
    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute a function with resilience patterns."""
        # Check circuit breaker
        if not self.circuit_breaker.can_execute():
            raise Exception("Circuit breaker is OPEN - service unavailable")
        
        last_error = None
        
        for attempt in range(self.retry_strategy.max_retries + 1):
            try:
                # Apply timeout
                coro = func(*args, **kwargs)
                result = await self.timeout_policy.execute_with_timeout(
                    coro, 
                    operation_name=func.__name__
                )
                
                # Success
                self.circuit_breaker.record_success()
                return result
                
            except Exception as e:
                last_error = e
                self.circuit_breaker.record_failure()
                
                if attempt < self.retry_strategy.max_retries:
                    delay = self.retry_strategy.get_delay(attempt)
                    await asyncio.sleep(delay)
        
        # All retries exhausted
        raise last_error
