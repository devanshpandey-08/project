"""
Vector store abstraction for FlowMind.

Provides a unified interface for all vector databases.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import hashlib


@dataclass
class Document:
    """A document in the vector store."""
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: hashlib.sha256(str(id()).encode()).hexdigest()[:16])
    embedding: Optional[List[float]] = None
    
    @classmethod
    def create(cls, content: str, **metadata) -> 'Document':
        return cls(content=content, metadata=metadata)


class EmbeddingModel:
    """Base class for embedding models."""
    
    async def embed(self, text: str) -> List[float]:
        raise NotImplementedError
    
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [await self.embed(t) for t in texts]


class MockEmbedding(EmbeddingModel):
    """Mock embedding model for testing."""
    
    def __init__(self, dimensions: int = 1536):
        self.dimensions = dimensions
    
    async def embed(self, text: str) -> List[float]:
        # Generate deterministic pseudo-random embedding based on text hash
        import random
        seed = int(hashlib.md5(text.encode()).hexdigest(), 16) % (2**32)
        random.seed(seed)
        return [random.gauss(0, 1) for _ in range(self.dimensions)]


class VectorStore:
    """
    Abstract vector store interface.
    
    Provides a unified API for all vector database implementations.
    """
    
    async def add(self, documents: List[Document], embeddings: Optional[List[List[float]]] = None) -> List[str]:
        raise NotImplementedError
    
    async def search(
        self,
        query: str,
        limit: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        raise NotImplementedError
    
    async def delete(self, ids: List[str]) -> None:
        raise NotImplementedError
    
    async def clear(self) -> None:
        raise NotImplementedError


class InMemoryVectorStore(VectorStore):
    """
    Simple in-memory vector store for testing and development.
    
    Not suitable for production use.
    """
    
    def __init__(self, embedding_model: Optional[EmbeddingModel] = None):
        self._documents: Dict[str, Document] = {}
        self._embeddings: Dict[str, List[float]] = {}
        self.embedding_model = embedding_model or MockEmbedding()
    
    async def add(
        self,
        documents: List[Document],
        embeddings: Optional[List[List[float]]] = None
    ) -> List[str]:
        ids = []
        
        for i, doc in enumerate(documents):
            if embeddings and i < len(embeddings):
                emb = embeddings[i]
            else:
                emb = await self.embedding_model.embed(doc.content)
            
            doc.embedding = emb
            self._documents[doc.id] = doc
            self._embeddings[doc.id] = emb
            ids.append(doc.id)
        
        return ids
    
    async def search(
        self,
        query: str,
        limit: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        # Generate query embedding
        query_emb = await self.embedding_model.embed(query)
        
        # Compute similarities (cosine similarity)
        scores = []
        for doc_id, doc_emb in self._embeddings.items():
            doc = self._documents[doc_id]
            
            # Apply metadata filter
            if filter_metadata:
                match = True
                for key, value in filter_metadata.items():
                    if doc.metadata.get(key) != value:
                        match = False
                        break
                if not match:
                    continue
            
            score = self._cosine_similarity(query_emb, doc_emb)
            scores.append((score, doc))
        
        # Sort by score descending
        scores.sort(key=lambda x: x[0], reverse=True)
        
        return [doc for _, doc in scores[:limit]]
    
    async def delete(self, ids: List[str]) -> None:
        for id in ids:
            self._documents.pop(id, None)
            self._embeddings.pop(id, None)
    
    async def clear(self) -> None:
        self._documents.clear()
        self._embeddings.clear()
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot_product / (norm_a * norm_b)
    
    @property
    def size(self) -> int:
        return len(self._documents)
