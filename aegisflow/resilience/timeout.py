import asyncio
from typing import Callable, Any
class TimeoutPolicy:
    def __init__(self, timeout_seconds: float = 30.0):
        self.timeout_seconds = timeout_seconds
    
    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        try:
            return await asyncio.wait_for(func(*args, **kwargs), timeout=self.timeout_seconds)
        except asyncio.TimeoutError:
            raise RuntimeError(f"Operation timed out after {self.timeout_seconds}s")
