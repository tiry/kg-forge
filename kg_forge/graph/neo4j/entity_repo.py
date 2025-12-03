"""Neo4j entity repository implementation."""

import logging
import re
from typing import Dict, Any, Optional, List

from kg_forge.graph.base import EntityRepository
from kg_forge.graph.neo4j.client import Neo4jClient
from kg_forge.graph.exceptions import (
    EntityNotFoundError,
    DuplicateEntityError,
    GraphError
)

logger = logging.getLogger(__name__)


class Neo4jEntityRepository(EntityRepository):
    """Neo4j implementation of EntityRepository.
    
    Handles CRUD operations for Entity nodes in Neo4j.
    """
    
    def __init__(self, client: Neo4jClient):
        """Initialize entity repository.
        
        Args:
            client: Neo4j client instance
        """
        self.client = client
    
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
            
        Raises:
            DuplicateEntityError: If entity already exists
        """
        normalized_name = self.normalize_name(name)
        
        query = """
        MERGE (e:Entity {
            namespace: $namespace,
            entity_type: $entity_type,
            normalized_name: $normalized_name
        })
        ON CREATE SET
            e.name = $name,
            e.created_at = timestamp()
        ON MATCH SET
            e = e
        WITH e, (e.created_at = timestamp()) as is_new
        WHERE is_new = false
        RETURN null as entity, 'exists' as status
        
        UNION
        
        MATCH (e:Entity {
            namespace: $namespace,
            entity_type: $entity_type,
            normalized_name: $normalized_name
        })
        WHERE e.created_at = timestamp()
        SET e += $properties
        RETURN e as entity, 'created' as status
        """
        
        params = {
            "namespace": namespace,
            "entity_type": entity_type,
            "name": name,
            "normalized_name": normalized_name,
            "properties": properties
        }
        
        try:
            result = self.client.execute_write_tx(query, params)
            
            if result and result[0].get('status') == 'exists':
                raise DuplicateEntityError(namespace, entity_type, name)
            
            if result and result[0].get('entity'):
                entity_data = dict(result[0]['entity'])
                logger.info(f"Created entity: {entity_type}='{name}' in namespace '{namespace}'")
                return entity_data
            
            raise GraphError("Failed to create entity")
            
        except DuplicateEntityError:
            raise
        except Exception as e:
            logger.error(f"Failed to create entity: {e}")
            raise GraphError(f"Failed to create entity: {e}")
    
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
        normalized_name = self.normalize_name(name)
        
        query = """
        MATCH (e:Entity {
            namespace: $namespace,
            entity_type: $entity_type,
            normalized_name: $normalized_name
        })
        RETURN e
        """
        
        params = {
            "namespace": namespace,
            "entity_type": entity_type,
            "normalized_name": normalized_name
        }
        
        try:
            result = self.client.execute_query(query, params)
            if result and result[0].get('e'):
                return dict(result[0]['e'])
            return None
        except Exception as e:
            logger.error(f"Failed to get entity: {e}")
            return None
    
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
        if entity_type:
            query = """
            MATCH (e:Entity {namespace: $namespace, entity_type: $entity_type})
            RETURN e
            ORDER BY e.name
            LIMIT $limit
            """
            params = {
                "namespace": namespace,
                "entity_type": entity_type,
                "limit": limit
            }
        else:
            query = """
            MATCH (e:Entity {namespace: $namespace})
            RETURN e
            ORDER BY e.entity_type, e.name
            LIMIT $limit
            """
            params = {
                "namespace": namespace,
                "limit": limit
            }
        
        try:
            result = self.client.execute_query(query, params)
            return [dict(r['e']) for r in result]
        except Exception as e:
            logger.error(f"Failed to list entities: {e}")
            return []
    
    def list_entity_types(self, namespace: str) -> List[str]:
        """List all entity types in namespace.
        
        Args:
            namespace: Namespace for isolation
            
        Returns:
            list: Sorted list of unique entity types
        """
        query = """
        MATCH (e:Entity {namespace: $namespace})
        RETURN DISTINCT e.entity_type as entity_type
        ORDER BY entity_type
        """
        
        params = {"namespace": namespace}
        
        try:
            result = self.client.execute_query(query, params)
            return [r['entity_type'] for r in result if r.get('entity_type')]
        except Exception as e:
            logger.error(f"Failed to list entity types: {e}")
            return []
    
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
            
        Raises:
            EntityNotFoundError: If entity doesn't exist
        """
        normalized_name = self.normalize_name(name)
        
        query = """
        MATCH (e:Entity {
            namespace: $namespace,
            entity_type: $entity_type,
            normalized_name: $normalized_name
        })
        SET e += $properties, e.updated_at = timestamp()
        RETURN e
        """
        
        params = {
            "namespace": namespace,
            "entity_type": entity_type,
            "normalized_name": normalized_name,
            "properties": properties
        }
        
        try:
            result = self.client.execute_write_tx(query, params)
            if result and result[0].get('e'):
                entity_data = dict(result[0]['e'])
                logger.info(f"Updated entity: {entity_type}='{name}' in namespace '{namespace}'")
                return entity_data
            
            raise EntityNotFoundError(namespace, entity_type, name)
            
        except EntityNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to update entity: {e}")
            raise GraphError(f"Failed to update entity: {e}")
    
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
        normalized_name = self.normalize_name(name)
        
        query = """
        MATCH (e:Entity {
            namespace: $namespace,
            entity_type: $entity_type,
            normalized_name: $normalized_name
        })
        DETACH DELETE e
        RETURN count(e) as deleted_count
        """
        
        params = {
            "namespace": namespace,
            "entity_type": entity_type,
            "normalized_name": normalized_name
        }
        
        try:
            result = self.client.execute_write_tx(query, params)
            deleted = result[0]['deleted_count'] > 0 if result else False
            
            if deleted:
                logger.info(f"Deleted entity: {entity_type}='{name}' from namespace '{namespace}'")
            
            return deleted
            
        except Exception as e:
            logger.error(f"Failed to delete entity: {e}")
            return False
    
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
            rel_type: Relationship type (will be uppercased)
            **properties: Relationship properties
            
        Returns:
            dict: Created relationship data
            
        Raises:
            EntityNotFoundError: If either entity doesn't exist
        """
        from_normalized = self.normalize_name(from_entity_name)
        to_normalized = self.normalize_name(to_entity_name)
        rel_type_upper = rel_type.upper()
        
        # Build dynamic query with relationship type
        query = f"""
        MATCH (from:Entity {{
            namespace: $namespace,
            entity_type: $from_entity_type,
            normalized_name: $from_normalized
        }})
        MATCH (to:Entity {{
            namespace: $namespace,
            entity_type: $to_entity_type,
            normalized_name: $to_normalized
        }})
        MERGE (from)-[r:{rel_type_upper}]->(to)
        ON CREATE SET
            r.namespace = $namespace,
            r.created_at = timestamp()
        SET r += $properties
        RETURN r, from, to
        """
        
        params = {
            "namespace": namespace,
            "from_entity_type": from_entity_type,
            "from_normalized": from_normalized,
            "to_entity_type": to_entity_type,
            "to_normalized": to_normalized,
            "properties": properties
        }
        
        try:
            result = self.client.execute_write_tx(query, params)
            
            if not result:
                # Check which entity is missing
                from_exists = self.get_entity(namespace, from_entity_type, from_entity_name)
                if not from_exists:
                    raise EntityNotFoundError(namespace, from_entity_type, from_entity_name)
                raise EntityNotFoundError(namespace, to_entity_type, to_entity_name)
            
            rel_data = dict(result[0]['r'])
            logger.info(
                f"Created relationship: {from_entity_type}='{from_entity_name}' "
                f"-[{rel_type_upper}]-> {to_entity_type}='{to_entity_name}'"
            )
            return rel_data
            
        except EntityNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to create relationship: {e}")
            raise GraphError(f"Failed to create relationship: {e}")
    
    def normalize_name(self, name: str) -> str:
        """Normalize an entity name for matching.
        
        Normalization rules:
        1. Remove content in parentheses (e.g., "(KD)", "(v2)")
        2. Convert to lowercase
        3. Trim and collapse whitespace
        4. Keep only alphanumeric and spaces
        
        Args:
            name: Original name
            
        Returns:
            str: Normalized name
            
        Examples:
            "Knowledge Discovery (KD)" -> "knowledge discovery"
            "Platform  Engineering" -> "platform engineering"
            "AI/ML Platform" -> "ai ml platform"
        """
        # Remove content in parentheses
        normalized = re.sub(r'\([^)]*\)', '', name)
        
        # Convert to lowercase
        normalized = normalized.lower()
        
        # Keep only alphanumeric and spaces
        normalized = re.sub(r'[^a-z0-9\s]', ' ', normalized)
        
        # Collapse multiple spaces to single space and trim
        normalized = ' '.join(normalized.split())
        
        return normalized
