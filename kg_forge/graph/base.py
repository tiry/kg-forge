"""Abstract base classes for graph database operations.

This module defines backend-agnostic interfaces that can be implemented
by different graph database backends (Neo4j, etc.).

NO database-specific imports should be in this file.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any


class GraphClient(ABC):
    """Abstract base class for graph database client.
    
    Provides connection management and basic query execution.
    Implementations handle specific database connectivity.
    """
    
    @abstractmethod
    def connect(self) -> bool:
        """Connect to the graph database.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        pass
    
    @abstractmethod
    def close(self) -> None:
        """Close the database connection.
        
        Should be idempotent - safe to call multiple times.
        """
        pass
    
    @abstractmethod
    def verify_connectivity(self) -> bool:
        """Verify that the database is accessible.
        
        Returns:
            bool: True if database responds, False otherwise
        """
        pass
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


class SchemaManager(ABC):
    """Abstract base class for schema management operations.
    
    Handles creation and management of database schema (constraints, indexes, etc.).
    """
    
    @abstractmethod
    def create_schema(self) -> None:
        """Create complete schema (constraints and indexes).
        
        Should be idempotent - safe to call multiple times.
        """
        pass
    
    @abstractmethod
    def create_constraints(self) -> None:
        """Create uniqueness constraints for nodes."""
        pass
    
    @abstractmethod
    def create_indexes(self) -> None:
        """Create performance indexes."""
        pass
    
    @abstractmethod
    def verify_schema(self) -> bool:
        """Verify schema is correctly set up.
        
        Returns:
            bool: True if all constraints and indexes exist
        """
        pass
    
    @abstractmethod
    def clear_namespace(self, namespace: str) -> int:
        """Clear all data for a specific namespace.
        
        Args:
            namespace: The namespace to clear
            
        Returns:
            int: Number of nodes deleted
        """
        pass
    
    @abstractmethod
    def get_statistics(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """Get database statistics.
        
        Args:
            namespace: Optional namespace to filter by
            
        Returns:
            dict: Statistics (node counts, relationship counts, etc.)
        """
        pass


class EntityRepository(ABC):
    """Abstract base class for entity operations.
    
    Handles CRUD operations for entities in the knowledge graph.
    """
    
    @abstractmethod
    def create_entity(
        self,
        namespace: str,
        entity_type: str,
        name: str,
        **properties
    ) -> Dict[str, Any]:
        """Create a new entity.
        
        Args:
            namespace: Namespace for isolation
            entity_type: Type of entity (e.g., "Product", "Team")
            name: Entity name
            **properties: Additional properties to store
            
        Returns:
            dict: Created entity with all properties
        """
        pass
    
    @abstractmethod
    def get_entity(
        self,
        namespace: str,
        entity_type: str,
        name: str
    ) -> Optional[Dict[str, Any]]:
        """Get an entity by type and name.
        
        Args:
            namespace: Namespace for isolation
            entity_type: Type of entity
            name: Entity name (will be normalized for lookup)
            
        Returns:
            dict: Entity data, or None if not found
        """
        pass
    
    @abstractmethod
    def list_entities(
        self,
        namespace: str,
        entity_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """List entities, optionally filtered by type.
        
        Args:
            namespace: Namespace for isolation
            entity_type: Optional type filter
            limit: Maximum number of results
            
        Returns:
            list: List of entity dictionaries
        """
        pass
    
    @abstractmethod
    def list_entity_types(self, namespace: str) -> List[str]:
        """List all entity types in namespace.
        
        Args:
            namespace: Namespace for isolation
            
        Returns:
            list: Sorted list of unique entity types
        """
        pass
    
    @abstractmethod
    def update_entity(
        self,
        namespace: str,
        entity_type: str,
        name: str,
        **properties
    ) -> Dict[str, Any]:
        """Update an existing entity's properties.
        
        Args:
            namespace: Namespace for isolation
            entity_type: Type of entity
            name: Entity name
            **properties: Properties to update
            
        Returns:
            dict: Updated entity data
        """
        pass
    
    @abstractmethod
    def delete_entity(
        self,
        namespace: str,
        entity_type: str,
        name: str
    ) -> bool:
        """Delete an entity.
        
        Args:
            namespace: Namespace for isolation
            entity_type: Type of entity
            name: Entity name
            
        Returns:
            bool: True if entity was deleted, False if not found
        """
        pass
    
    @abstractmethod
    def create_relationship(
        self,
        namespace: str,
        from_entity_type: str,
        from_entity_name: str,
        to_entity_type: str,
        to_entity_name: str,
        rel_type: str,
        **properties
    ) -> Dict[str, Any]:
        """Create a relationship between two entities.
        
        Args:
            namespace: Namespace for isolation
            from_entity_type: Source entity type
            from_entity_name: Source entity name
            to_entity_type: Target entity type
            to_entity_name: Target entity name
            rel_type: Relationship type
            **properties: Relationship properties
            
        Returns:
            dict: Created relationship data
        """
        pass
    
    @abstractmethod
    def normalize_name(self, name: str) -> str:
        """Normalize an entity name for matching.
        
        Normalization rules:
        1. Remove content in parentheses
        2. Convert to lowercase
        3. Trim and collapse whitespace
        4. Keep only alphanumeric and spaces
        
        Args:
            name: Original name
            
        Returns:
            str: Normalized name
        """
        pass


class DocumentRepository(ABC):
    """Abstract base class for document operations.
    
    Handles CRUD operations for documents and their relationships to entities.
    """
    
    @abstractmethod
    def create_document(
        self,
        namespace: str,
        doc_id: str,
        source_path: str,
        content_hash: str,
        **metadata
    ) -> Dict[str, Any]:
        """Create a new document node.
        
        Args:
            namespace: Namespace for isolation
            doc_id: Unique document identifier
            source_path: Source file path
            content_hash: MD5 hash of content
            **metadata: Additional document metadata
            
        Returns:
            dict: Created document data
        """
        pass
    
    @abstractmethod
    def get_document(
        self,
        namespace: str,
        doc_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get a document by ID.
        
        Args:
            namespace: Namespace for isolation
            doc_id: Document identifier
            
        Returns:
            dict: Document data, or None if not found
        """
        pass
    
    @abstractmethod
    def document_exists(
        self,
        namespace: str,
        doc_id: str
    ) -> bool:
        """Check if a document exists.
        
        Args:
            namespace: Namespace for isolation
            doc_id: Document identifier
            
        Returns:
            bool: True if document exists
        """
        pass
    
    @abstractmethod
    def document_hash_exists(
        self,
        namespace: str,
        content_hash: str
    ) -> bool:
        """Check if a document with given hash exists.
        
        Args:
            namespace: Namespace for isolation
            content_hash: MD5 hash to check
            
        Returns:
            bool: True if document with hash exists
        """
        pass
    
    @abstractmethod
    def list_documents(
        self,
        namespace: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """List all documents in namespace.
        
        Args:
            namespace: Namespace for isolation
            limit: Maximum number of results
            
        Returns:
            list: List of document dictionaries
        """
        pass
    
    @abstractmethod
    def add_mention(
        self,
        namespace: str,
        doc_id: str,
        entity_type: str,
        entity_name: str,
        **properties
    ) -> Dict[str, Any]:
        """Create a MENTIONS relationship from document to entity.
        
        Args:
            namespace: Namespace for isolation
            doc_id: Document identifier
            entity_type: Entity type
            entity_name: Entity name
            **properties: Relationship properties (e.g., confidence)
            
        Returns:
            dict: Created relationship data
        """
        pass
    
    @abstractmethod
    def get_document_entities(
        self,
        namespace: str,
        doc_id: str
    ) -> List[Dict[str, Any]]:
        """Get all entities mentioned in a document.
        
        Args:
            namespace: Namespace for isolation
            doc_id: Document identifier
            
        Returns:
            list: List of entities with relationship data
        """
        pass
    
    @abstractmethod
    def find_related_documents(
        self,
        namespace: str,
        entity_type: str,
        entity_name: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Find documents that mention a specific entity.
        
        Args:
            namespace: Namespace for isolation
            entity_type: Entity type
            entity_name: Entity name
            limit: Maximum number of results
            
        Returns:
            list: List of related documents
        """
        pass
