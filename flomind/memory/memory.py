"""
Memory system for FlowMind.

Provides short-term and long-term memory capabilities for agents.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
import asyncio


@dataclass
class MemoryEntry:
    """A single memory entry."""
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    importance: float = 0.5
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'content': self.content,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata,
            'importance': self.importance
        }


class Memory:
    """Base class for memory implementations."""
    
    async def add(self, content: str, **metadata) -> None:
        raise NotImplementedError
    
    async def get(self, query: str, limit: int = 5) -> List[MemoryEntry]:
        raise NotImplementedError
    
    async def clear(self) -> None:
        raise NotImplementedError
    
    def get_messages(self) -> List:
        """Get messages in LLM format."""
        return []


class ShortTermMemory(Memory):
    """
    Short-term memory with limited capacity.
    
    Uses a sliding window approach to maintain recent context.
    """
    
    def __init__(self, max_messages: int = 100):
        self.max_messages = max_messages
        self._messages: List[Dict[str, Any]] = []
        self._entries: List[MemoryEntry] = []
    
    async def add(self, content: str, **metadata) -> None:
        entry = MemoryEntry(content=content, metadata=metadata)
        self._entries.append(entry)
        
        # Prune if over capacity
        while len(self._entries) > self.max_messages:
            self._entries.pop(0)
    
    async def get(self, query: str, limit: int = 5) -> List[MemoryEntry]:
        # Simple recency-based retrieval
        return self._entries[-limit:]
    
    async def clear(self) -> None:
        self._entries.clear()
        self._messages.clear()
    
    def add_message(self, message: Any) -> None:
        """Add a message from the LLM provider format."""
        role = getattr(message, 'role', 'unknown')
        content = getattr(message, 'content', '')
        self._messages.append({'role': role.value if hasattr(role, 'value') else role, 'content': content})
        
        # Also store as entry
        asyncio.create_task(self.add(f"{role}: {content}"))
    
    def get_messages(self) -> List[Dict[str, Any]]:
        """Get messages in LLM format."""
        return self._messages.copy()
    
    @property
    def size(self) -> int:
        return len(self._entries)


class LongTermMemory(Memory):
    """
    Long-term memory with persistence and semantic search.
    
    In production, this would integrate with vector databases.
    """
    
    def __init__(self, storage_path: Optional[str] = None, embedding_model: Optional[Any] = None):
        self.storage_path = storage_path
        self.embedding_model = embedding_model
        self._entries: List[MemoryEntry] = []
        self._index: Dict[str, List[int]] = {}  # Simple keyword index
    
    async def add(self, content: str, **metadata) -> None:
        entry = MemoryEntry(content=content, metadata=metadata)
        self._entries.append(entry)
        
        # Build simple keyword index
        keywords = content.lower().split()
        for word in keywords:
            if len(word) > 3:  # Skip short words
                if word not in self._index:
                    self._index[word] = []
                self._index[word].append(len(self._entries) - 1)
        
        # Persist if path is set
        if self.storage_path:
            await self._persist()
    
    async def get(self, query: str, limit: int = 5) -> List[MemoryEntry]:
        # Simple keyword-based retrieval
        query_words = query.lower().split()
        scores: Dict[int, float] = {}
        
        for word in query_words:
            if len(word) > 3 and word in self._index:
                for idx in self._index[word]:
                    scores[idx] = scores.get(idx, 0) + 1
        
        # Sort by score and return top results
        sorted_indices = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        return [self._entries[i] for i in sorted_indices[:limit]]
    
    async def clear(self) -> None:
        self._entries.clear()
        self._index.clear()
    
    async def _persist(self) -> None:
        """Persist memory to disk (simplified)."""
        if self.storage_path:
            import json
            data = [e.to_dict() for e in self._entries]
            with open(self.storage_path, 'w') as f:
                json.dump(data, f)
    
    async def load(self) -> None:
        """Load memory from disk."""
        if self.storage_path:
            import json
            import os
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    self._entries = [
                        MemoryEntry(
                            content=d['content'],
                            timestamp=datetime.fromisoformat(d['timestamp']),
                            metadata=d.get('metadata', {}),
                            importance=d.get('importance', 0.5)
                        )
                        for d in data
                    ]


@dataclass
class ContextWindow:
    """
    Manages the context window for LLM interactions.
    
    Provides intelligent context management with token counting and truncation.
    """
    max_tokens: int = 8000
    system_prompt: Optional[str] = None
    messages: List[Dict[str, Any]] = field(default_factory=list)
    
    def add_message(self, role: str, content: str) -> 'ContextWindow':
        self.messages.append({'role': role, 'content': content})
        self._trim_if_needed()
        return self
    
    def set_system_prompt(self, prompt: str) -> 'ContextWindow':
        self.system_prompt = prompt
        return self
    
    def clear(self) -> 'ContextWindow':
        self.messages.clear()
        return self
    
    def get_messages(self) -> List[Dict[str, Any]]:
        result = []
        if self.system_prompt:
            result.append({'role': 'system', 'content': self.system_prompt})
        result.extend(self.messages)
        return result
    
    def _trim_if_needed(self) -> None:
        # Simple token estimation (1 token ≈ 4 characters)
        total_chars = sum(len(m.get('content', '')) for m in self.messages)
        estimated_tokens = total_chars // 4
        
        while estimated_tokens > self.max_tokens and len(self.messages) > 1:
            self.messages.pop(0)
            total_chars = sum(len(m.get('content', '')) for m in self.messages)
            estimated_tokens = total_chars // 4
    
    @property
    def token_count(self) -> int:
        total_chars = sum(len(m.get('content', '')) for m in self.messages)
        if self.system_prompt:
            total_chars += len(self.system_prompt)
        return total_chars // 4
