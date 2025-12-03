"""Neo4j document repository implementation."""

import logging
from typing import Dict, Any, Optional, List

from kg_forge.graph.base import DocumentRepository
from kg_forge.graph.neo4j.client import Neo4jClient
from kg_forge.graph.exceptions import (
    DocumentNotFoundError,
    EntityNotFoundError,
    GraphError
)

logger = logging.getLogger(__name__)


class Neo4jDocumentRepository(DocumentRepository):
    """Neo4j implementation of DocumentRepository.
    
    Handles CRUD operations for Doc nodes and their relationships to entities.
    """
    
    def __init__(self, client: Neo4jClient):
        """Initialize document repository.
        
        Args:
            client: Neo4j client instance
        """
        self.client = client
    
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
        query = """
        MERGE (d:Doc {namespace: $namespace, doc_id: $doc_id})
        ON CREATE SET
            d.source_path = $source_path,
            d.content_hash = $content_hash,
            d.created_at = timestamp()
        ON MATCH SET
            d.source_path = $source_path,
            d.content_hash = $content_hash,
            d.updated_at = timestamp()
        SET d += $metadata
        RETURN d
        """
        
        params = {
            "namespace": namespace,
            "doc_id": doc_id,
            "source_path": source_path,
            "content_hash": content_hash,
            "metadata": metadata
        }
        
        try:
            result = self.client.execute_write_tx(query, params)
            if result and result[0].get('d'):
                doc_data = dict(result[0]['d'])
                logger.info(f"Created/updated document: '{doc_id}' in namespace '{namespace}'")
                return doc_data
            
            raise GraphError("Failed to create document")
            
        except Exception as e:
            logger.error(f"Failed to create document: {e}")
            raise GraphError(f"Failed to create document: {e}")
    
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
        query = """
        MATCH (d:Doc {namespace: $namespace, doc_id: $doc_id})
        RETURN d
        """
        
        params = {
            "namespace": namespace,
            "doc_id": doc_id
        }
        
        try:
            result = self.client.execute_query(query, params)
            if result and result[0].get('d'):
                return dict(result[0]['d'])
            return None
        except Exception as e:
            logger.error(f"Failed to get document: {e}")
            return None
    
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
        query = """
        MATCH (d:Doc {namespace: $namespace, doc_id: $doc_id})
        RETURN count(d) as count
        """
        
        params = {
            "namespace": namespace,
            "doc_id": doc_id
        }
        
        try:
            result = self.client.execute_query(query, params)
            return result[0]['count'] > 0 if result else False
        except Exception as e:
            logger.error(f"Failed to check document existence: {e}")
            return False
    
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
        query = """
        MATCH (d:Doc {namespace: $namespace, content_hash: $content_hash})
        RETURN count(d) as count
        """
        
        params = {
            "namespace": namespace,
            "content_hash": content_hash
        }
        
        try:
            result = self.client.execute_query(query, params)
            return result[0]['count'] > 0 if result else False
        except Exception as e:
            logger.error(f"Failed to check document hash: {e}")
            return False
    
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
        query = """
        MATCH (d:Doc {namespace: $namespace})
        RETURN d
        ORDER BY d.doc_id
        LIMIT $limit
        """
        
        params = {
            "namespace": namespace,
            "limit": limit
        }
        
        try:
            result = self.client.execute_query(query, params)
            return [dict(r['d']) for r in result]
        except Exception as e:
            logger.error(f"Failed to list documents: {e}")
            return []
    
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
            
        Raises:
            DocumentNotFoundError: If document doesn't exist
            EntityNotFoundError: If entity doesn't exist
        """
        # Normalize entity name for lookup
        from kg_forge.graph.neo4j.entity_repo import Neo4jEntityRepository
        repo = Neo4jEntityRepository(self.client)
        normalized_name = repo.normalize_name(entity_name)
        
        query = """
        MATCH (d:Doc {namespace: $namespace, doc_id: $doc_id})
        MATCH (e:Entity {
            namespace: $namespace,
            entity_type: $entity_type,
            normalized_name: $normalized_name
        })
        MERGE (d)-[r:MENTIONS]->(e)
        ON CREATE SET
            r.namespace = $namespace,
            r.created_at = timestamp()
        SET r += $properties
        RETURN r, d, e
        """
        
        params = {
            "namespace": namespace,
            "doc_id": doc_id,
            "entity_type": entity_type,
            "normalized_name": normalized_name,
            "properties": properties
        }
        
        try:
            result = self.client.execute_write_tx(query, params)
            
            if not result:
                # Check which node is missing
                doc_exists = self.document_exists(namespace, doc_id)
                if not doc_exists:
                    raise DocumentNotFoundError(namespace, doc_id)
                raise EntityNotFoundError(namespace, entity_type, entity_name)
            
            rel_data = dict(result[0]['r'])
            logger.info(
                f"Created MENTIONS: Doc '{doc_id}' -> {entity_type}='{entity_name}'"
            )
            return rel_data
            
        except (DocumentNotFoundError, EntityNotFoundError):
            raise
        except Exception as e:
            logger.error(f"Failed to add mention: {e}")
            raise GraphError(f"Failed to add mention: {e}")
    
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
        query = """
        MATCH (d:Doc {namespace: $namespace, doc_id: $doc_id})-[r:MENTIONS]->(e:Entity)
        RETURN e, r
        ORDER BY e.entity_type, e.name
        """
        
        params = {
            "namespace": namespace,
            "doc_id": doc_id
        }
        
        try:
            result = self.client.execute_query(query, params)
            entities = []
            for r in result:
                entity = dict(r['e'])
                relationship = dict(r['r'])
                entity['mention_properties'] = relationship
                entities.append(entity)
            return entities
        except Exception as e:
            logger.error(f"Failed to get document entities: {e}")
            return []
    
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
        # Normalize entity name for lookup
        from kg_forge.graph.neo4j.entity_repo import Neo4jEntityRepository
        repo = Neo4jEntityRepository(self.client)
        normalized_name = repo.normalize_name(entity_name)
        
        query = """
        MATCH (d:Doc {namespace: $namespace})-[r:MENTIONS]->(e:Entity {
            namespace: $namespace,
            entity_type: $entity_type,
            normalized_name: $normalized_name
        })
        RETURN d, r
        ORDER BY d.doc_id
        LIMIT $limit
        """
        
        params = {
            "namespace": namespace,
            "entity_type": entity_type,
            "normalized_name": normalized_name,
            "limit": limit
        }
        
        try:
            result = self.client.execute_query(query, params)
            documents = []
            for r in result:
                doc = dict(r['d'])
                relationship = dict(r['r'])
                doc['mention_properties'] = relationship
                documents.append(doc)
            return documents
        except Exception as e:
            logger.error(f"Failed to find related documents: {e}")
            return []
