"""
FlowMind Memory Systems

Two types of memory for production AI applications:
1. Short-term: Conversation context (sliding window)
2. Long-term: Persistent storage with vector search
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
from collections import deque


@dataclass
class Message:
    """A single message in conversation history."""
    role: str  # user, assistant, system
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ShortTermMemory:
    """
    Short-term memory for conversation context.
    
    Features:
    - Sliding window (keeps last N messages)
    - Token counting for cost management
    - Automatic truncation when limit reached
    """
    
    def __init__(self, max_messages: int = 20, max_tokens: int = 4000):
        self.max_messages = max_messages
        self.max_tokens = max_tokens
        self.messages: deque[Message] = deque(maxlen=max_messages)
        self._token_count = 0
    
    def add_message(self, role: str, content: str, 
                    metadata: Optional[Dict[str, Any]] = None):
        """Add a message to memory."""
        msg = Message(
            role=role,
            content=content,
            metadata=metadata or {}
        )
        self.messages.append(msg)
        
        # Update token count (rough estimate: 1 token ≈ 4 chars)
        self._token_count += len(content) // 4
        
        # Truncate if over token limit
        while self._token_count > self.max_tokens and len(self.messages) > 2:
            old_msg = self.messages.popleft()
            self._token_count -= len(old_msg.content) // 4
    
    def get_messages(self) -> List[Dict[str, str]]:
        """Get all messages in OpenAI format."""
        return [
            {"role": msg.role, "content": msg.content}
            for msg in self.messages
        ]
    
    def clear(self):
        """Clear all messages."""
        self.messages.clear()
        self._token_count = 0
    
    def get_token_count(self) -> int:
        """Get current token count."""
        return self._token_count
    
    def get_last_n(self, n: int) -> List[Message]:
        """Get last N messages."""
        return list(self.messages)[-n:]


@dataclass
class Document:
    """A document for long-term memory."""
    id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


class LongTermMemory:
    """
    Long-term memory with vector search capabilities.
    
    Features:
    - Document storage with metadata
    - Similarity search (when embeddings provided)
    - Persistence ready (can be backed by Pinecone, etc.)
    
    In production, this integrates with vector databases like:
    - Pinecone
    - Weaviate
    - Qdrant
    - pgvector
    """
    
    def __init__(self):
        self.documents: Dict[str, Document] = {}
        self.index: Dict[str, Document] = {}  # Could be replaced with vector index
    
    def store(self, doc_id: str, content: str, 
              metadata: Optional[Dict[str, Any]] = None,
              embedding: Optional[List[float]] = None) -> Document:
        """Store a document in long-term memory."""
        doc = Document(
            id=doc_id,
            content=content,
            metadata=metadata or {},
            embedding=embedding
        )
        self.documents[doc_id] = doc
        
        # Add to search index
        self.index[doc_id] = doc
        
        return doc
    
    def get(self, doc_id: str) -> Optional[Document]:
        """Retrieve a document by ID."""
        return self.documents.get(doc_id)
    
    def delete(self, doc_id: str) -> bool:
        """Delete a document."""
        if doc_id in self.documents:
            del self.documents[doc_id]
            if doc_id in self.index:
                del self.index[doc_id]
            return True
        return False
    
    def search(self, query: str, limit: int = 5,
               filter_metadata: Optional[Dict[str, Any]] = None) -> List[Document]:
        """
        Search for relevant documents.
        
        In production with embeddings:
        - Compute query embedding
        - Find nearest neighbors in vector index
        - Apply metadata filters
        - Return top K results
        
        This is a simplified keyword-based search for demonstration.
        """
        # Simple keyword matching (replace with vector search in production)
        query_words = set(query.lower().split())
        
        scored_docs = []
        for doc in self.documents.values():
            # Apply metadata filter if specified
            if filter_metadata:
                match = all(
                    doc.metadata.get(k) == v 
                    for k, v in filter_metadata.items()
                )
                if not match:
                    continue
            
            # Score by keyword overlap
            doc_words = set(doc.content.lower().split())
            overlap = len(query_words & doc_words)
            
            if overlap > 0:
                scored_docs.append((overlap, doc))
        
        # Sort by score and return top results
        scored_docs.sort(key=lambda x: -x[0])
        return [doc for _, doc in scored_docs[:limit]]
    
    def clear(self):
        """Clear all documents."""
        self.documents.clear()
        self.index.clear()
