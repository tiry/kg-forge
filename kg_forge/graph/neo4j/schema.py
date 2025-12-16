"""Neo4j schema management implementation."""

import logging
from typing import Dict, Any, Optional, List

from kg_forge.graph.base import SchemaManager
from kg_forge.graph.neo4j.client import Neo4jClient
from kg_forge.graph.exceptions import SchemaError

logger = logging.getLogger(__name__)


class Neo4jSchemaManager(SchemaManager):
    """Neo4j implementation of SchemaManager.
    
    Manages database schema including constraints and indexes.
    """
    
    def __init__(self, client: Neo4jClient):
        """Initialize schema manager.
        
        Args:
            client: Neo4j client instance
        """
        self.client = client
    
    def create_schema(self) -> None:
        """Create complete schema (constraints and indexes).
        
        Idempotent - safe to call multiple times.
        
        Raises:
            SchemaError: If schema creation fails
        """
        try:
            logger.info("Creating database schema...")
            self.create_constraints()
            self.create_indexes()
            logger.info("Database schema created successfully")
        except Exception as e:
            raise SchemaError(f"Failed to create schema: {e}")
    
    def create_constraints(self) -> None:
        """Create uniqueness constraints for nodes.
        
        Creates:
        - Doc nodes: unique on (namespace, doc_id)
        - Entity nodes: unique on (namespace, entity_type, normalized_name)
        """
        logger.info("Creating constraints...")
        
        # Constraint for Doc nodes
        doc_constraint = """
        CREATE CONSTRAINT doc_unique IF NOT EXISTS
        FOR (d:Doc)
        REQUIRE (d.namespace, d.doc_id) IS UNIQUE
        """
        
        # Constraint for Entity nodes
        entity_constraint = """
        CREATE CONSTRAINT entity_unique IF NOT EXISTS
        FOR (e:Entity)
        REQUIRE (e.namespace, e.entity_type, e.normalized_name) IS UNIQUE
        """
        
        try:
            self.client.execute_write(doc_constraint)
            logger.info("Created Doc uniqueness constraint")
            
            self.client.execute_write(entity_constraint)
            logger.info("Created Entity uniqueness constraint")
        except Exception as e:
            raise SchemaError(f"Failed to create constraints: {e}")
    
    def create_indexes(self) -> None:
        """Create performance indexes.
        
        Creates indexes on:
        - Doc: namespace, content_hash
        - Entity: namespace, entity_type, name
        """
        logger.info("Creating indexes...")
        
        indexes = [
            # Doc indexes
            "CREATE INDEX doc_namespace IF NOT EXISTS FOR (d:Doc) ON (d.namespace)",
            "CREATE INDEX doc_content_hash IF NOT EXISTS FOR (d:Doc) ON (d.content_hash)",
            
            # Entity indexes
            "CREATE INDEX entity_namespace IF NOT EXISTS FOR (e:Entity) ON (e.namespace)",
            "CREATE INDEX entity_type IF NOT EXISTS FOR (e:Entity) ON (e.entity_type)",
            "CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name)",
        ]
        
        try:
            for index_query in indexes:
                self.client.execute_write(index_query)
                logger.debug(f"Created index: {index_query[:50]}...")
            
            logger.info(f"Created {len(indexes)} indexes")
        except Exception as e:
            raise SchemaError(f"Failed to create indexes: {e}")
    
    def create_vector_index(self) -> None:
        """
        Create vector index for entity embeddings.
        
        This creates a vector index using cosine similarity for
        384-dimensional BERT embeddings (all-MiniLM-L6-v2).
        """
        logger.info("Creating vector index...")
        
        query = """
        CREATE VECTOR INDEX entity_embeddings IF NOT EXISTS
        FOR (e:Entity)
        ON e.embedding
        OPTIONS {indexConfig: {
            `vector.dimensions`: 384,
            `vector.similarity_function`: 'cosine'
        }}
        """
        
        try:
            self.client.execute_write(query)
            logger.info("Created vector index: entity_embeddings (384 dimensions, cosine similarity)")
        except Exception as e:
            # Vector indexes are only available in Neo4j Enterprise Edition or AuraDB
            logger.warning(
                f"Vector index creation skipped - requires Neo4j Enterprise Edition or AuraDB "
                f"(currently using Community Edition). Vector-based deduplication will be disabled. "
                f"Fuzzy and dictionary-based deduplication will still work. Error: {e}"
            )
    
    def verify_schema(self) -> bool:
        """Verify schema is correctly set up.
        
        Returns:
            bool: True if all constraints and indexes exist
        """
        try:
            # Check constraints
            constraints_query = "SHOW CONSTRAINTS"
            constraints = self.client.execute_query(constraints_query)
            
            constraint_names = {c.get('name', '') for c in constraints}
            required_constraints = {'doc_unique', 'entity_unique'}
            
            missing_constraints = required_constraints - constraint_names
            if missing_constraints:
                logger.warning(f"Missing constraints: {missing_constraints}")
                return False
            
            # Check indexes
            indexes_query = "SHOW INDEXES"
            indexes = self.client.execute_query(indexes_query)
            
            index_names = {idx.get('name', '') for idx in indexes}
            required_indexes = {
                'doc_namespace', 'doc_content_hash',
                'entity_namespace', 'entity_type', 'entity_name'
            }
            
            missing_indexes = required_indexes - index_names
            if missing_indexes:
                logger.warning(f"Missing indexes: {missing_indexes}")
                return False
            
            logger.info("Schema verification passed")
            return True
            
        except Exception as e:
            logger.error(f"Schema verification failed: {e}")
            return False
    
    def clear_namespace(self, namespace: str) -> int:
        """Clear all data for a specific namespace.
        
        Args:
            namespace: The namespace to clear
            
        Returns:
            int: Number of nodes deleted
        """
        logger.info(f"Clearing namespace: {namespace}")
        
        # Delete all relationships first
        delete_rels_query = """
        MATCH (n {namespace: $namespace})-[r]-()
        DELETE r
        """
        
        # Then delete all nodes
        delete_nodes_query = """
        MATCH (n {namespace: $namespace})
        DELETE n
        RETURN count(n) as deleted_count
        """
        
        try:
            # Delete relationships
            self.client.execute_write(delete_rels_query, {"namespace": namespace})
            
            # Delete nodes and get count
            result = self.client.execute_write_tx(delete_nodes_query, {"namespace": namespace})
            deleted_count = result[0]['deleted_count'] if result else 0
            
            logger.info(f"Deleted {deleted_count} nodes from namespace '{namespace}'")
            return deleted_count
            
        except Exception as e:
            raise SchemaError(f"Failed to clear namespace '{namespace}': {e}")
    
    def get_statistics(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """Get database statistics.
        
        Args:
            namespace: Optional namespace to filter by
            
        Returns:
            dict: Statistics (node counts, relationship counts, etc.)
        """
        try:
            if namespace:
                # Statistics for specific namespace
                stats_query = """
                MATCH (n {namespace: $namespace})
                WITH count(n) as total_nodes, labels(n) as node_labels
                UNWIND node_labels as label
                RETURN label, count(*) as count
                """
                
                node_results = self.client.execute_query(
                    stats_query,
                    {"namespace": namespace}
                )
                
                # Count relationships
                rel_query = """
                MATCH (n {namespace: $namespace})-[r]-()
                RETURN type(r) as rel_type, count(r) as count
                """
                
                rel_results = self.client.execute_query(
                    rel_query,
                    {"namespace": namespace}
                )
                
                return {
                    "namespace": namespace,
                    "nodes": {r['label']: r['count'] for r in node_results},
                    "relationships": {r['rel_type']: r['count'] for r in rel_results},
                }
            else:
                # Global statistics
                global_query = """
                MATCH (n)
                RETURN count(n) as total_nodes
                """
                
                result = self.client.execute_query(global_query)
                total_nodes = result[0]['total_nodes'] if result else 0
                
                return {
                    "total_nodes": total_nodes,
                    "message": "Use namespace parameter for detailed statistics"
                }
                
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {"error": str(e)}
