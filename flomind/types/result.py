"""
FlowMind Types - Result Handling

Type-safe result handling with Success/Failure patterns.
No more guessing if a result is valid or an error.
"""

from dataclasses import dataclass
from typing import Any, Generic, Optional, TypeVar, Union

T = TypeVar('T')
E = TypeVar('E')


@dataclass
class Success(Generic[T]):
    """Represents a successful operation result."""
    value: T
    metadata: dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def map(self, func) -> 'Success':
        """Transform the success value."""
        return Success(value=func(self.value), metadata=self.metadata)
    
    def unwrap(self) -> T:
        """Get the success value."""
        return self.value


@dataclass
class Failure(Generic[E]):
    """Represents a failed operation result."""
    error: E
    error_code: str = "UNKNOWN_ERROR"
    metadata: dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def map_error(self, func) -> 'Failure':
        """Transform the error value."""
        return Failure(error=func(self.error), error_code=self.error_code, metadata=self.metadata)
    
    def unwrap_error(self) -> E:
        """Get the error value."""
        return self.error


# Type alias for result type
Result = Union[Success[T], Failure[E]]


def ok(value: T) -> Success[T]:
    """Create a success result."""
    return Success(value=value)


def fail(error: E, error_code: str = "UNKNOWN_ERROR") -> Failure[E]:
    """Create a failure result."""
    return Failure(error=error, error_code=error_code)


def try_execute(func, *args, **kwargs) -> Result[Any, Exception]:
    """
    Execute a function and wrap result in Success/Failure.
    
    Usage:
        result = try_execute(risky_function, arg1, arg2)
        if isinstance(result, Success):
            print(f"Got: {result.value}")
        else:
            print(f"Error: {result.error}")
    """
    try:
        result = func(*args, **kwargs)
        return ok(result)
    except Exception as e:
        return fail(e, error_code=type(e).__name__)


async def try_execute_async(func, *args, **kwargs) -> Result[Any, Exception]:
    """
    Execute an async function and wrap result in Success/Failure.
    
    Usage:
        result = await try_execute_async(risky_async_function, arg1)
        if isinstance(result, Success):
            print(f"Got: {result.value}")
        else:
            print(f"Error: {result.error}")
    """
    try:
        result = await func(*args, **kwargs)
        return ok(result)
    except Exception as e:
        return fail(e, error_code=type(e).__name__)
