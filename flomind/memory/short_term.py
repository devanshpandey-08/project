"""Memory systems for FlowMind."""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from collections import deque
import time


@dataclass
class ShortTermMemory:
    """
    Sliding window short-term memory for agents.
    
    Features:
    - Configurable window size
    - Automatic eviction
    - Context preservation
    """
    max_messages: int = 10
    messages: List[Dict[str, Any]] = field(default_factory=list)
    
    def add(self, role: str, content: str, **metadata) -> None:
        """Add a message to memory."""
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": time.time(),
            **metadata
        })
        
        # Evict old messages
        while len(self.messages) > self.max_messages:
            self.messages.pop(0)
            
    def get_context(self) -> List[Dict[str, Any]]:
        """Get full context for LLM."""
        return self.messages.copy()
        
    def clear(self) -> None:
        """Clear all messages."""
        self.messages = []
        
    def __len__(self) -> int:
        return len(self.messages)


@dataclass
class LongTermMemory:
    """
    Persistent long-term memory with vector storage capability.
    
    Features:
    - Key-value storage
    - Expiration support
    - Metadata tagging
    """
    storage: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None
    ) -> None:
        """Store a value with optional TTL and tags."""
        self.storage[key] = {
            "value": value,
            "created_at": time.time(),
            "expires_at": time.time() + ttl if ttl else None,
            "tags": tags or []
        }
        
    def get(self, key: str) -> Optional[Any]:
        """Retrieve a value by key."""
        if key not in self.storage:
            return None
            
        entry = self.storage[key]
        
        # Check expiration
        if entry.get("expires_at") and time.time() > entry["expires_at"]:
            del self.storage[key]
            return None
            
        return entry["value"]
        
    def delete(self, key: str) -> bool:
        """Delete a key."""
        if key in self.storage:
            del self.storage[key]
            return True
        return False
        
    def search_by_tag(self, tag: str) -> Dict[str, Any]:
        """Search entries by tag."""
        return {
            k: v["value"]
            for k, v in self.storage.items()
            if tag in v.get("tags", [])
        }
        
    def cleanup_expired(self) -> int:
        """Remove expired entries. Returns count removed."""
        now = time.time()
        expired = [
            k for k, v in self.storage.items()
            if v.get("expires_at") and now > v["expires_at"]
        ]
        
        for key in expired:
            del self.storage[key]
            
        return len(expired)


class VectorStore:
    """
    Simple in-memory vector store for embeddings.
    
    For production, use Pinecone, Weaviate, or similar.
    """
    
    def __init__(self):
        self.vectors: Dict[str, List[float]] = {}
        self.metadata: Dict[str, Dict[str, Any]] = {}
        
    def add_vector(
        self,
        id: str,
        vector: List[float],
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add a vector with metadata."""
        self.vectors[id] = vector
        self.metadata[id] = metadata or {}
        
    def similarity_search(
        self,
        query_vector: List[float],
        top_k: int = 5
    ) -> List[tuple]:
        """Find most similar vectors (cosine similarity)."""
        if not self.vectors:
            return []
            
        def cosine_similarity(v1: List[float], v2: List[float]) -> float:
            dot = sum(a * b for a, b in zip(v1, v2))
            norm1 = sum(a * a for a in v1) ** 0.5
            norm2 = sum(b * b for b in v2) ** 0.5
            return dot / (norm1 * norm2) if norm1 and norm2 else 0.0
            
        scores = [
            (id, cosine_similarity(query_vector, vec))
            for id, vec in self.vectors.items()
        ]
        
        scores.sort(key=lambda x: x[1], reverse=True)
        
        return [
            (id, score, self.metadata.get(id, {}))
            for id, score in scores[:top_k]
        ]
        
    def delete(self, id: str) -> bool:
        """Delete a vector by ID."""
        if id in self.vectors:
            del self.vectors[id]
            del self.metadata[id]
            return True
        return False
