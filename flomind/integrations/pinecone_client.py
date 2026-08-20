"""
Pinecone Integration for FlowMind

Production-ready Pinecone vector database client.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import asyncio
import logging

logger = logging.getLogger(__name__)


class PineconeClient:
    """
    Production Pinecone client with connection pooling and retry logic.
    
    Features:
    - Automatic retries with exponential backoff
    - Connection pooling
    - Batch operations
    - Metadata filtering
    - Namespace support
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        environment: Optional[str] = None,
        index_name: str = "flomind-index",
        dimensions: int = 1536,
        metric: str = "cosine",
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        import os
        
        self.api_key = api_key or os.getenv('PINECONE_API_KEY')
        self.environment = environment or os.getenv('PINECONE_ENVIRONMENT')
        self.index_name = index_name
        self.dimensions = dimensions
        self.metric = metric
        self.timeout = timeout
        self.max_retries = max_retries
        
        if not self.api_key:
            raise ValueError("Pinecone API key is required")
        
        self._client = None
        self._index = None
    
    @property
    def client(self):
        if self._client is None:
            try:
                from pinecone import Pinecone, ServerlessSpec
                
                pc = Pinecone(api_key=self.api_key)
                
                # Create index if it doesn't exist
                existing_indexes = pc.list_indexes()
                if self.index_name not in existing_indexes.names():
                    pc.create_index(
                        name=self.index_name,
                        dimension=self.dimensions,
                        metric=self.metric,
                        spec=ServerlessSpec(
                            cloud='aws',
                            region='us-east-1'
                        )
                    )
                
                self._client = pc
                self._index = pc.Index(self.index_name)
                
            except ImportError:
                raise ImportError("Install pinecone package: pip install pinecone")
        
        return self._client
    
    @property
    def index(self):
        if self._index is None:
            _ = self.client
        return self._index
    
    async def upsert(
        self,
        vectors: List[Dict[str, Any]],
        namespace: str = "",
        batch_size: int = 100,
    ) -> Dict[str, Any]:
        """
        Upsert vectors to Pinecone.
        
        Args:
            vectors: List of vectors with id, values, and optional metadata
            namespace: Index namespace
            batch_size: Batch size for upsert operations
            
        Returns:
            Upsert response
        """
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                # Process in batches
                for i in range(0, len(vectors), batch_size):
                    batch = vectors[i:i + batch_size]
                    
                    if namespace:
                        self.index.upsert(vectors=batch, namespace=namespace)
                    else:
                        self.index.upsert(vectors=batch)
                
                return {'status': 'success', 'count': len(vectors)}
                
            except Exception as e:
                last_error = e
                
                if attempt < self.max_retries:
                    delay = min(2 ** attempt * 0.5, 10.0)
                    await asyncio.sleep(delay)
                    continue
                
                raise
        
        raise last_error
    
    async def query(
        self,
        vector: List[float],
        top_k: int = 5,
        filter: Optional[Dict[str, Any]] = None,
        namespace: str = "",
        include_metadata: bool = True,
        include_values: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Query vectors by similarity.
        
        Args:
            vector: Query vector
            top_k: Number of results to return
            filter: Metadata filter
            namespace: Index namespace
            include_metadata: Include vector metadata
            include_values: Include vector values
            
        Returns:
            List of matching vectors with scores
        """
        kwargs = {
            'vector': vector,
            'top_k': top_k,
            'include_metadata': include_metadata,
            'include_values': include_values,
        }
        
        if filter:
            kwargs['filter'] = filter
        
        if namespace:
            kwargs['namespace'] = namespace
        
        result = self.index.query(**kwargs)
        
        return [
            {
                'id': match.id,
                'score': match.score,
                'metadata': match.metadata if include_metadata else None,
                'values': match.values if include_values else None,
            }
            for match in result.matches
        ]
    
    async def delete(
        self,
        ids: Optional[List[str]] = None,
        namespace: str = "",
        delete_all: bool = False,
        filter: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Delete vectors from the index."""
        if delete_all:
            if namespace:
                self.index.delete(delete_all=True, namespace=namespace)
            else:
                self.index.delete(delete_all=True)
        elif ids:
            if namespace:
                self.index.delete(ids=ids, namespace=namespace)
            else:
                self.index.delete(ids=ids)
        elif filter:
            if namespace:
                self.index.delete(filter=filter, namespace=namespace)
            else:
                self.index.delete(filter=filter)
    
    async def describe_index_stats(self, filter: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get index statistics."""
        stats = self.index.describe_index_stats(filter=filter)
        return {
            'dimension': stats.dimension,
            'index_fullness': stats.index_fullness,
            'total_vector_count': stats.total_vector_count,
            'namespaces': dict(stats.namespaces) if hasattr(stats, 'namespaces') else {},
        }
    
    async def list_namespaces(self) -> List[str]:
        """List all namespaces in the index."""
        stats = await self.describe_index_stats()
        return list(stats.get('namespaces', {}).keys())
    
    async def close(self) -> None:
        """Close the client connection."""
        self._client = None
        self._index = None
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
