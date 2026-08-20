"""
Timeout policy for FlowMind.

Provides timeout handling for async operations.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, Optional, TypeVar
import asyncio

T = TypeVar('T')


@dataclass
class TimeoutPolicy:
    """
    Timeout policy for async operations.
    
    Usage:
        policy = TimeoutPolicy(timeout_seconds=30.0)
        result = await policy.execute(my_async_function, arg1, arg2)
    """
    
    timeout_seconds: float = 30.0
    raise_on_timeout: bool = True
    
    async def execute(
        self,
        func: Callable[..., T],
        *args,
        **kwargs
    ) -> Optional[T]:
        """Execute a function with timeout."""
        try:
            if asyncio.iscoroutinefunction(func):
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=self.timeout_seconds
                )
            else:
                # Run sync function in executor
                loop = asyncio.get_event_loop()
                return await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: func(*args, **kwargs)),
                    timeout=self.timeout_seconds
                )
                
        except asyncio.TimeoutError:
            if self.raise_on_timeout:
                raise
            return None
    
    def wrap(self, func: Callable[..., T]) -> Callable[..., T]:
        """Wrap a function with timeout logic."""
        async def wrapper(*args, **kwargs):
            return await self.execute(func, *args, **kwargs)
        return wrapper
