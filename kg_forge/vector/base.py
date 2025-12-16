"""Abstract base class for vector stores."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple


class VectorStore(ABC):
    """Abstract interface for vector storage and similarity search."""
    
    @abstractmethod
    def add_entity(
        self,
        entity_id: str,
        entity_type: str,
        entity_name: str,
        embedding: List[float],
        namespace: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add entity embedding to the vector store.
        
        Args:
            entity_id: Unique entity identifier
            entity_type: Type of entity (Technology, Product, etc.)
            entity_name: Entity name
            embedding: Embedding vector
            namespace: Namespace for isolation
            metadata: Additional metadata
        """
        pass
    
    @abstractmethod
    def search_similar(
        self,
        entity_type: str,
        embedding: List[float],
        namespace: str,
        limit: int = 5,
        threshold: float = 0.85
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        """
        Search for similar entities by vector similarity.
        
        Args:
            entity_type: Type to filter by
            embedding: Query embedding vector
            namespace: Namespace to search in
            limit: Maximum results
            threshold: Minimum similarity score (0-1)
            
        Returns:
            List of (entity_id, similarity_score, metadata) tuples
        """
        pass
    
    @abstractmethod
    def delete_namespace(self, namespace: str) -> int:
        """
        Delete all entities in a namespace.
        
        Args:
            namespace: Namespace to clear
            
        Returns:
            Number of entities deleted
        """
        pass
    
    @abstractmethod
    def get_stats(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics about stored vectors.
        
        Args:
            namespace: Optional namespace to filter by
            
        Returns:
            Statistics dictionary
        """
        pass
