"""
FlowMind Integrations - Vector Store

Production-ready vector database integration with:
- Pinecone support
- Batch operations
- Metadata filtering
- Connection pooling
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import os


@dataclass
class VectorStoreConfig:
    """Vector store configuration."""
    api_key: Optional[str] = None
    environment: Optional[str] = None
    index_name: str = "flomind-index"
    dimension: int = 1536  # OpenAI embeddings default
    
    def __post_init__(self):
        self.api_key = self.api_key or os.getenv("PINECONE_API_KEY")
        self.environment = self.environment or os.getenv("PINECONE_ENVIRONMENT")


@dataclass
class VectorDocument:
    """A document with embedding for vector storage."""
    id: str
    embedding: List[float]
    metadata: Dict[str, Any] = field(default_factory=dict)
    content: str = ""


class VectorStore:
    """
    Production-ready vector database client.
    
    Features:
    - Pinecone integration
    - Batch upsert for efficiency
    - Metadata filtering
    - Similarity search
    """
    
    def __init__(self, config: Optional[VectorStoreConfig] = None):
        self.config = config or VectorStoreConfig()
        self._index = None
    
    def _get_index(self):
        """Lazy-load Pinecone index."""
        if self._index is None:
            try:
                import pinecone
                
                # Initialize connection
                pinecone.init(
                    api_key=self.config.api_key,
                    environment=self.config.environment
                )
                
                # Get or create index
                indexes = pinecone.list_indexes()
                if self.config.index_name not in indexes:
                    pinecone.create_index(
                        name=self.config.index_name,
                        dimension=self.config.dimension,
                        metric="cosine"
                    )
                
                self._index = pinecone.Index(self.config.index_name)
                
            except ImportError:
                raise ImportError(
                    "Install pinecone package: pip install pinecone-client"
                )
        
        return self._index
    
    def upsert(self, documents: List[VectorDocument]) -> Dict[str, Any]:
        """Upsert documents to the vector store."""
        index = self._get_index()
        
        vectors = []
        for doc in documents:
            vectors.append({
                "id": doc.id,
                "values": doc.embedding,
                "metadata": {**doc.metadata, "content": doc.content}
            })
        
        return index.upsert(vectors=vectors)
    
    def upsert_batch(self, documents: List[VectorDocument], 
                     batch_size: int = 100) -> List[Dict[str, Any]]:
        """Upsert documents in batches for large datasets."""
        results = []
        
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            result = self.upsert(batch)
            results.append(result)
        
        return results
    
    def query(self, embedding: List[float], 
              top_k: int = 5,
              filter_metadata: Optional[Dict[str, Any]] = None,
              include_content: bool = True) -> List[Dict[str, Any]]:
        """
        Query for similar vectors.
        
        Args:
            embedding: Query vector
            top_k: Number of results to return
            filter_metadata: Filter by metadata (e.g., {"source": "docs"})
            include_content: Whether to include content in results
        
        Returns:
            List of results with id, score, metadata, and optionally content
        """
        index = self._get_index()
        
        response = index.query(
            vector=embedding,
            top_k=top_k,
            filter=filter_metadata,
            include_metadata=True
        )
        
        results = []
        for match in response.matches:
            result = {
                "id": match.id,
                "score": match.score,
                "metadata": match.metadata
            }
            
            if include_content and match.metadata:
                result["content"] = match.metadata.pop("content", "")
            
            results.append(result)
        
        return results
    
    def delete(self, ids: List[str]) -> Dict[str, Any]:
        """Delete documents by ID."""
        index = self._get_index()
        return index.delete(ids=ids)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        index = self._get_index()
        stats = index.describe_index_stats()
        return {
            "total_vectors": stats.get("total_vector_count", 0),
            "dimension": stats.get("dimension", self.config.dimension),
            "metric": stats.get("metric", "cosine")
        }
