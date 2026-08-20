"""Vector memory for semantic search and RAG."""

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import math


@dataclass
class VectorDocument:
    """A document with vector embedding."""
    id: str
    content: str
    embedding: List[float]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "embedding": self.embedding,
            "metadata": self.metadata,
        }


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    if len(v1) != len(v2):
        raise ValueError("Vectors must have same length")
    
    dot_product = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    return dot_product / (norm1 * norm2)


class VectorMemory:
    """
    In-memory vector store for semantic search and RAG.
    
    Features:
    - Cosine similarity search
    - Metadata filtering
    - Configurable top-k results
    - Simple embedding function (for demo - use real embeddings in production)
    
    Usage:
        memory = VectorMemory()
        memory.add("doc1", "Python is great", [0.1, 0.2, ...])
        results = memory.search(query_embedding, top_k=5)
        
    Note: For production, integrate with Pinecone, Weaviate, or similar.
    """
    
    def __init__(self, dimension: int = 1536):
        self.dimension = dimension
        self._documents: Dict[str, VectorDocument] = {}
    
    def add(
        self,
        doc_id: str,
        content: str,
        embedding: List[float],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "VectorMemory":
        """Add a document to the vector store."""
        if len(embedding) != self.dimension:
            raise ValueError(f"Embedding must have {self.dimension} dimensions")
        
        doc = VectorDocument(
            id=doc_id,
            content=content,
            embedding=embedding,
            metadata=metadata or {},
        )
        self._documents[doc_id] = doc
        return self
    
    def add_batch(
        self,
        documents: List[Tuple[str, str, List[float], Optional[Dict[str, Any]]]],
    ) -> "VectorMemory":
        """Add multiple documents."""
        for doc_id, content, embedding, metadata in documents:
            self.add(doc_id, content, embedding, metadata)
        return self
    
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None,
        min_similarity: float = 0.0,
    ) -> List[Tuple[VectorDocument, float]]:
        """
        Search for similar documents.
        
        Args:
            query_embedding: The query vector
            top_k: Number of results to return
            filter_metadata: Filter by metadata fields
            min_similarity: Minimum similarity threshold
        
        Returns:
            List of (document, similarity_score) tuples
        """
        if len(query_embedding) != self.dimension:
            raise ValueError(f"Query embedding must have {self.dimension} dimensions")
        
        results = []
        
        for doc in self._documents.values():
            # Apply metadata filter
            if filter_metadata:
                match = True
                for k, v in filter_metadata.items():
                    if doc.metadata.get(k) != v:
                        match = False
                        break
                if not match:
                    continue
            
            # Calculate similarity
            similarity = cosine_similarity(query_embedding, doc.embedding)
            
            if similarity >= min_similarity:
                results.append((doc, similarity))
        
        # Sort by similarity descending
        results.sort(key=lambda x: -x[1])
        
        return results[:top_k]
    
    def get(self, doc_id: str) -> Optional[VectorDocument]:
        """Get a document by ID."""
        return self._documents.get(doc_id)
    
    def delete(self, doc_id: str) -> bool:
        """Delete a document."""
        if doc_id in self._documents:
            del self._documents[doc_id]
            return True
        return False
    
    def clear(self) -> "VectorMemory":
        """Clear all documents."""
        self._documents.clear()
        return self
    
    def stats(self) -> Dict[str, Any]:
        """Get statistics."""
        return {
            "total_documents": len(self._documents),
            "dimension": self.dimension,
        }
    
    @staticmethod
    def simple_embedding(text: str, dimension: int = 1536) -> List[float]:
        """
        Generate a simple hash-based embedding (for demo only).
        
        In production, use real embeddings from:
        - OpenAI embeddings API
        - Sentence transformers
        - Cohere
        - etc.
        """
        # Create deterministic pseudo-random embedding from text
        hash_bytes = hashlib.md5(text.encode()).digest()
        embedding = []
        
        for i in range(dimension):
            # Use hash + position to generate value
            h = int(hash_bytes[i % len(hash_bytes)])
            value = (h / 256.0) * 2 - 1  # Range [-1, 1]
            embedding.append(value)
        
        # Normalize
        norm = math.sqrt(sum(v * v for v in embedding))
        if norm > 0:
            embedding = [v / norm for v in embedding]
        
        return embedding
    
    def __len__(self) -> int:
        return len(self._documents)
    
    def __repr__(self) -> str:
        return f"VectorMemory(docs={len(self._documents)}, dim={self.dimension})"
