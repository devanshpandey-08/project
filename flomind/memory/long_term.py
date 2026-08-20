"""Long-term memory with persistent storage."""

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from pathlib import Path
import time


@dataclass
class MemoryEntry:
    """A single entry in long-term memory."""
    id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    access_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "access_count": self.access_count,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        return cls(
            id=data["id"],
            content=data["content"],
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            access_count=data.get("access_count", 0),
        )


class LongTermMemory:
    """
    Persistent long-term memory storage.
    
    Features:
    - File-based persistence (JSON)
    - Key-value and semantic access
    - Metadata filtering
    - Automatic cleanup of old entries
    
    Usage:
        memory = LongTermMemory(storage_path="./memory")
        memory.save("fact_1", "Paris is the capital of France")
        fact = memory.get("fact_1")
        
        # Search by metadata
        results = memory.search(metadata={"category": "geography"})
    """
    
    def __init__(
        self,
        storage_path: str = "./flomind_memory",
        max_entries: int = 10000,
        auto_save: bool = True,
    ):
        self.storage_path = Path(storage_path)
        self.max_entries = max_entries
        self.auto_save = auto_save
        self._entries: Dict[str, MemoryEntry] = {}
        
        # Create storage directory
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Load existing entries
        self._load()
    
    def _get_storage_file(self) -> Path:
        return self.storage_path / "long_term_memory.json"
    
    def _load(self) -> None:
        """Load entries from disk."""
        storage_file = self._get_storage_file()
        if storage_file.exists():
            try:
                with open(storage_file, "r") as f:
                    data = json.load(f)
                    self._entries = {
                        k: MemoryEntry.from_dict(v) for k, v in data.items()
                    }
            except Exception:
                self._entries = {}
    
    def _save(self) -> None:
        """Save entries to disk."""
        storage_file = self._get_storage_file()
        with open(storage_file, "w") as f:
            data = {k: v.to_dict() for k, v in self._entries.items()}
            json.dump(data, f, indent=2)
    
    def save(
        self,
        key: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "LongTermMemory":
        """Save a memory entry."""
        entry = MemoryEntry(
            id=key,
            content=content,
            metadata=metadata or {},
        )
        self._entries[key] = entry
        
        if self.auto_save:
            self._save()
        
        # Cleanup if over limit
        if len(self._entries) > self.max_entries:
            self._cleanup_old_entries()
        
        return self
    
    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a memory entry by key."""
        entry = self._entries.get(key)
        if entry:
            entry.access_count += 1
            entry.updated_at = time.time()
            if self.auto_save:
                self._save()
            return entry.content
        return default
    
    def get_entry(self, key: str) -> Optional[MemoryEntry]:
        """Get full entry object."""
        return self._entries.get(key)
    
    def delete(self, key: str) -> bool:
        """Delete a memory entry."""
        if key in self._entries:
            del self._entries[key]
            if self.auto_save:
                self._save()
            return True
        return False
    
    def search(
        self,
        query: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        limit: int = 10,
    ) -> List[MemoryEntry]:
        """Search memories by content or metadata."""
        results = []
        
        for entry in self._entries.values():
            score = 0
            
            # Content match
            if query and query.lower() in entry.content.lower():
                score += 2
            
            # Metadata match
            if metadata:
                for k, v in metadata.items():
                    if entry.metadata.get(k) == v:
                        score += 1
            
            if score > 0:
                results.append((score, entry))
        
        # Sort by score and recency
        results.sort(key=lambda x: (-x[0], -x[1].updated_at))
        
        return [entry for _, entry in results[:limit]]
    
    def keys(self) -> List[str]:
        """Get all memory keys."""
        return list(self._entries.keys())
    
    def clear(self) -> "LongTermMemory":
        """Clear all memories."""
        self._entries.clear()
        if self.auto_save:
            self._save()
        return self
    
    def _cleanup_old_entries(self) -> None:
        """Remove oldest entries when over limit."""
        sorted_entries = sorted(
            self._entries.items(),
            key=lambda x: (x[1].access_count, x[1].updated_at)
        )
        
        # Remove oldest 10%
        remove_count = max(1, len(sorted_entries) // 10)
        for key, _ in sorted_entries[:remove_count]:
            del self._entries[key]
        
        if self.auto_save:
            self._save()
    
    def stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        total_access = sum(e.access_count for e in self._entries.values())
        return {
            "total_entries": len(self._entries),
            "max_entries": self.max_entries,
            "total_access_count": total_access,
            "storage_path": str(self.storage_path),
        }
    
    def __len__(self) -> int:
        return len(self._entries)
    
    def __repr__(self) -> str:
        return f"LongTermMemory(entries={len(self._entries)}, path={self.storage_path})"
