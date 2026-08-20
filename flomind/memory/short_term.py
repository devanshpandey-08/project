"""Short-term memory for conversation history."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from collections import deque
import time


@dataclass
class Message:
    """A single message in conversation history."""
    role: str  # "user", "assistant", "system", "tool"
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            **self.metadata,
        }


class ShortTermMemory:
    """
    Sliding window memory for conversation history.
    
    Features:
    - Configurable max messages
    - Automatic eviction of old messages
    - Message types: user, assistant, system, tool
    - Token estimation
    
    Usage:
        memory = ShortTermMemory(max_messages=20)
        memory.add_user_message("Hello!")
        memory.add_assistant_message("Hi there!")
        messages = memory.get_messages()
    """
    
    def __init__(self, max_messages: int = 20, estimate_tokens: bool = True):
        self.max_messages = max_messages
        self.estimate_tokens = estimate_tokens
        self._messages: deque[Message] = deque(maxlen=max_messages)
        self._system_prompt: Optional[str] = None
    
    def set_system_prompt(self, prompt: str) -> "ShortTermMemory":
        """Set the system prompt (always included first)."""
        self._system_prompt = prompt
        return self
    
    def add_message(self, role: str, content: str, **metadata) -> "ShortTermMemory":
        """Add a message to memory."""
        msg = Message(role=role, content=content, metadata=metadata)
        self._messages.append(msg)
        return self
    
    def add_user_message(self, content: str, **metadata) -> "ShortTermMemory":
        """Add a user message."""
        return self.add_message("user", content, **metadata)
    
    def add_assistant_message(self, content: str, **metadata) -> "ShortTermMemory":
        """Add an assistant message."""
        return self.add_message("assistant", content, **metadata)
    
    def add_tool_result(self, tool_name: str, result: Any) -> "ShortTermMemory":
        """Add a tool execution result."""
        content = str(result) if not isinstance(result, str) else result
        return self.add_message("tool", content, tool_name=tool_name)
    
    def get_messages(self, include_system: bool = True) -> List[Dict[str, Any]]:
        """Get all messages as a list of dicts."""
        messages = []
        
        # Add system prompt first
        if include_system and self._system_prompt:
            messages.append({"role": "system", "content": self._system_prompt})
        
        # Add conversation messages
        messages.extend([msg.to_dict() for msg in self._messages])
        
        return messages
    
    def get_last_message(self, role: Optional[str] = None) -> Optional[Message]:
        """Get the last message, optionally filtered by role."""
        if role is None:
            return self._messages[-1] if self._messages else None
        
        for msg in reversed(self._messages):
            if msg.role == role:
                return msg
        return None
    
    def clear(self) -> "ShortTermMemory":
        """Clear all messages (except system prompt)."""
        self._messages.clear()
        return self
    
    def pop(self, count: int = 1) -> List[Message]:
        """Remove and return the oldest messages."""
        popped = []
        for _ in range(min(count, len(self._messages))):
            popped.append(self._messages.popleft())
        return popped
    
    def estimate_tokens(self) -> int:
        """Estimate total tokens in memory (rough approximation)."""
        total_chars = sum(len(msg.content) for msg in self._messages)
        if self._system_prompt:
            total_chars += len(self._system_prompt)
        # Rough estimate: 1 token ≈ 4 characters
        return total_chars // 4
    
    def __len__(self) -> int:
        return len(self._messages)
    
    def __repr__(self) -> str:
        return f"ShortTermMemory(messages={len(self._messages)}, max={self.max_messages})"
