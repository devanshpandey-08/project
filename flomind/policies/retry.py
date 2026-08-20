"""
Retry policy for FlowMind.

Provides configurable retry logic with exponential backoff.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, TypeVar
import asyncio
import random

T = TypeVar('T')


@dataclass
class RetryPolicy:
    """
    Retry policy with exponential backoff and jitter.
    
    Usage:
        policy = RetryPolicy(max_retries=3, base_delay=1.0)
        result = await policy.execute(my_async_function, arg1, arg2)
    """
    
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: tuple = (Exception,)
    
    async def execute(
        self,
        func: Callable[..., T],
        *args,
        **kwargs
    ) -> T:
        """Execute a function with retry logic."""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
                    
            except self.retryable_exceptions as e:
                last_exception = e
                
                if attempt == self.max_retries:
                    raise
                
                # Calculate delay with exponential backoff
                delay = min(
                    self.base_delay * (self.exponential_base ** attempt),
                    self.max_delay
                )
                
                # Add jitter if enabled
                if self.jitter:
                    delay = delay * (0.5 + random.random())
                
                await asyncio.sleep(delay)
        
        raise last_exception
    
    def wrap(self, func: Callable[..., T]) -> Callable[..., T]:
        """Wrap a function with retry logic."""
        async def wrapper(*args, **kwargs):
            return await self.execute(func, *args, **kwargs)
        return wrapper
