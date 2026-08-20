"""Flow Executor with resilience patterns."""

from typing import Any, Dict, Optional, Callable
import asyncio
import time
from dataclasses import dataclass
from datetime import datetime


@dataclass
class RetryPolicy:
    """Retry policy configuration."""
    max_retries: int = 3
    delay: float = 1.0
    backoff_multiplier: float = 2.0
    max_delay: float = 60.0
    retry_on: tuple = (Exception,)
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt."""
        delay = self.delay * (self.backoff_multiplier ** attempt)
        return min(delay, self.max_delay)


@dataclass
class TimeoutPolicy:
    """Timeout policy configuration."""
    timeout: float = 30.0
    raise_on_timeout: bool = True


@dataclass
class CircuitBreaker:
    """Circuit breaker for fault tolerance."""
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    half_open_requests: int = 1
    
    def __post_init__(self):
        self.failures = 0
        self.last_failure_time: Optional[float] = None
        self.state = "closed"  # closed, open, half-open
        
    def record_success(self):
        """Record successful execution."""
        self.failures = 0
        self.state = "closed"
        
    def record_failure(self):
        """Record failed execution."""
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.failure_threshold:
            self.state = "open"
            
    def can_execute(self) -> bool:
        """Check if execution is allowed."""
        if self.state == "closed":
            return True
        if self.state == "open":
            if self.last_failure_time and \
               time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "half-open"
                return True
            return False
        # half-open
        return True


class FlowExecutor:
    """Executes flows with resilience patterns."""
    
    def __init__(
        self,
        retry_policy: Optional[RetryPolicy] = None,
        timeout_policy: Optional[TimeoutPolicy] = None,
        circuit_breaker: Optional[CircuitBreaker] = None
    ):
        self.retry_policy = retry_policy or RetryPolicy()
        self.timeout_policy = timeout_policy or TimeoutPolicy()
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        
    async def execute_with_resilience(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Execute function with retry, timeout, and circuit breaker."""
        # Check circuit breaker
        if not self.circuit_breaker.can_execute():
            raise Exception("Circuit breaker is open")
            
        last_error = None
        attempt = 0
        
        while attempt <= self.retry_policy.max_retries:
            try:
                # Execute with timeout
                if asyncio.iscoroutinefunction(func):
                    result = await asyncio.wait_for(
                        func(*args, **kwargs),
                        timeout=self.timeout_policy.timeout
                    )
                else:
                    result = await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(
                            None, func, *args, **kwargs
                        ),
                        timeout=self.timeout_policy.timeout
                    )
                    
                self.circuit_breaker.record_success()
                return result
                
            except asyncio.TimeoutError as e:
                last_error = e
                if self.timeout_policy.raise_on_timeout:
                    raise
                    
            except Exception as e:
                last_error = e
                self.circuit_breaker.record_failure()
                
                if not isinstance(e, self.retry_policy.retry_on):
                    raise
                    
            attempt += 1
            if attempt <= self.retry_policy.max_retries:
                delay = self.retry_policy.get_delay(attempt)
                await asyncio.sleep(delay)
                
        raise last_error or Exception("Max retries exceeded")
    
    def execute(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Synchronous execution wrapper."""
        return asyncio.run(self.execute_with_resilience(func, *args, **kwargs))
