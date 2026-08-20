"""
Streaming system for FlowMind.

Provides real-time event streaming and chunked responses.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, AsyncIterator, Callable
from enum import Enum
import asyncio
import uuid


class EventType(Enum):
    """Types of events in the streaming system."""
    CHUNK = "chunk"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    MESSAGE_START = "message_start"
    MESSAGE_END = "message_end"
    ERROR = "error"
    METADATA = "metadata"
    CUSTOM = "custom"


@dataclass
class StreamChunk:
    """A chunk of streamed data."""
    content: str = ""
    event_type: EventType = EventType.CHUNK
    metadata: Dict[str, Any] = field(default_factory=dict)
    sequence: int = 0
    is_done: bool = False
    
    def __str__(self) -> str:
        return self.content


@dataclass
class StreamEvent:
    """An event in the event bus."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    event_type: EventType = EventType.CUSTOM
    payload: Any = None
    timestamp: float = field(default_factory=asyncio.get_event_loop().time if asyncio.get_event_loop().is_running() else lambda: 0)
    source: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class EventBus:
    """
    Event bus for pub/sub messaging in flows.
    
    Enables decoupled communication between components.
    """
    
    def __init__(self):
        self._subscribers: Dict[EventType, List[Callable]] = {}
        self._queue: asyncio.Queue = asyncio.Queue()
    
    def subscribe(self, event_type: EventType, handler: Callable) -> None:
        """Subscribe to an event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
    
    def unsubscribe(self, event_type: EventType, handler: Callable) -> bool:
        """Unsubscribe from an event type."""
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(handler)
                return True
            except ValueError:
                pass
        return False
    
    async def publish(self, event: StreamEvent) -> None:
        """Publish an event to all subscribers."""
        await self._queue.put(event)
        
        if event.event_type in self._subscribers:
            for handler in self._subscribers[event.event_type]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event)
                    else:
                        handler(event)
                except Exception as e:
                    # Log error but don't fail the publish
                    pass
    
    async def listen(self, event_types: Optional[List[EventType]] = None) -> AsyncIterator[StreamEvent]:
        """Listen for events."""
        while True:
            event = await self._queue.get()
            if event_types is None or event.event_type in event_types:
                yield event
    
    def clear(self) -> None:
        """Clear all subscriptions and queued events."""
        self._subscribers.clear()
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break


class Stream:
    """
    A streaming response handler.
    
    Provides memory-efficient true streaming for LLM responses.
    """
    
    def __init__(self, buffer_size: int = 100):
        self.buffer_size = buffer_size
        self._buffer: asyncio.Queue = asyncio.Queue(maxsize=buffer_size)
        self._done = False
        self._sequence = 0
    
    async def write(self, content: str, **metadata) -> None:
        """Write a chunk to the stream."""
        chunk = StreamChunk(
            content=content,
            sequence=self._sequence,
            metadata=metadata
        )
        self._sequence += 1
        await self._buffer.put(chunk)
    
    async def end(self) -> None:
        """Mark the stream as complete."""
        await self._buffer.put(StreamChunk(is_done=True, sequence=self._sequence))
        self._done = True
    
    async def read(self) -> Optional[StreamChunk]:
        """Read a chunk from the stream."""
        try:
            chunk = await asyncio.wait_for(self._buffer.get(), timeout=30.0)
            return chunk
        except asyncio.TimeoutError:
            return None
    
    async def iter(self) -> AsyncIterator[StreamChunk]:
        """Iterate over all chunks in the stream."""
        while True:
            chunk = await self.read()
            if chunk is None:
                continue
            yield chunk
            if chunk.is_done:
                break
    
    @property
    def is_done(self) -> bool:
        return self._done
    
    def clear(self) -> None:
        """Clear the stream buffer."""
        while not self._buffer.empty():
            try:
                self._buffer.get_nowait()
            except asyncio.QueueEmpty:
                break
        self._done = False
        self._sequence = 0
