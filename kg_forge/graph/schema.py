"""Schema management utilities for Neo4j database."""

import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from .neo4j_client import Neo4jClient
from .exceptions import SchemaError

logger = logging.getLogger(__name__)


@dataclass
class SchemaConstraint:
    """Database constraint definition."""
    name: str
    node_label: str
    properties: List[str]
    constraint_type: str = "UNIQUE"
    
    def to_cypher(self) -> str:
        """Convert to Cypher CREATE CONSTRAINT statement."""
        props = ", ".join([f"n.{prop}" for prop in self.properties])
        return (
            f"CREATE CONSTRAINT {self.name} IF NOT EXISTS "
            f"FOR (n:{self.node_label}) "
            f"REQUIRE ({props}) IS {self.constraint_type}"
        )


@dataclass  
class SchemaIndex:
    """Database index definition."""
    name: str
    node_label: str
    properties: List[str]
    
    def to_cypher(self) -> str:
        """Convert to Cypher CREATE INDEX statement."""
        if len(self.properties) == 1:
            return (
                f"CREATE INDEX {self.name} IF NOT EXISTS "
                f"FOR (n:{self.node_label}) ON (n.{self.properties[0]})"
            )
        else:
            props = ", ".join([f"n.{prop}" for prop in self.properties])
            return (
                f"CREATE INDEX {self.name} IF NOT EXISTS "
                f"FOR (n:{self.node_label}) ON ({props})"
            )


class SchemaManager:
    """Manages Neo4j schema initialization and validation."""
    
    def __init__(self, client: Neo4jClient):
        """Initialize with Neo4j client."""
        self.client = client
        
    def get_required_constraints(self) -> List[SchemaConstraint]:
        """Return list of constraints required for KG Forge schema."""
        return [
            SchemaConstraint(
                name="doc_unique",
                node_label="Doc", 
                properties=["namespace", "doc_id"],
                constraint_type="UNIQUE"
            ),
            SchemaConstraint(
                name="entity_unique",
                node_label="Entity",
                properties=["namespace", "entity_type", "normalized_name"],
                constraint_type="UNIQUE"
            )
        ]
        
    def get_required_indexes(self) -> List[SchemaIndex]:
        """Return list of indexes required for KG Forge schema."""
        return [
            SchemaIndex(
                name="doc_namespace",
                node_label="Doc",
                properties=["namespace"]
            ),
            SchemaIndex(
                name="doc_content_hash", 
                node_label="Doc",
                properties=["content_hash"]
            ),
            SchemaIndex(
                name="entity_namespace",
                node_label="Entity", 
                properties=["namespace"]
            ),
            SchemaIndex(
                name="entity_type",
                node_label="Entity",
                properties=["entity_type"]
            ),
            SchemaIndex(
                name="entity_name",
                node_label="Entity",
                properties=["name"]
            )
        ]
        
    def create_constraints(self, constraints: Optional[List[SchemaConstraint]] = None) -> None:
        """
        Create database constraints, handling existing ones gracefully.
        
        Args:
            constraints: List of constraints to create. If None, creates all required constraints.
            
        Raises:
            SchemaError: If constraint creation fails
        """
        if constraints is None:
            constraints = self.get_required_constraints()
            
        logger.info(f"Creating {len(constraints)} constraints")
        
        for constraint in constraints:
            try:
                cypher = constraint.to_cypher()
                logger.debug(f"Creating constraint: {cypher}")
                
                self.client.execute_query(cypher)
                logger.info(f"Created constraint: {constraint.name}")
                
            except Exception as e:
                error_msg = str(e).lower()
                if "already exists" in error_msg or "equivalent constraint" in error_msg:
                    logger.debug(f"Constraint {constraint.name} already exists")
                else:
                    logger.error(f"Failed to create constraint {constraint.name}: {e}")
                    raise SchemaError(f"Constraint creation failed for {constraint.name}: {e}")
                    
    def create_indexes(self, indexes: Optional[List[SchemaIndex]] = None) -> None:
        """
        Create database indexes, handling existing ones gracefully.
        
        Args:
            indexes: List of indexes to create. If None, creates all required indexes.
            
        Raises:
            SchemaError: If index creation fails
        """
        if indexes is None:
            indexes = self.get_required_indexes()
            
        logger.info(f"Creating {len(indexes)} indexes")
        
        for index in indexes:
            try:
                cypher = index.to_cypher()
                logger.debug(f"Creating index: {cypher}")
                
                self.client.execute_query(cypher)
                logger.info(f"Created index: {index.name}")
                
            except Exception as e:
                error_msg = str(e).lower()
                if "already exists" in error_msg or "equivalent index" in error_msg:
                    logger.debug(f"Index {index.name} already exists")
                else:
                    logger.error(f"Failed to create index {index.name}: {e}")
                    raise SchemaError(f"Index creation failed for {index.name}: {e}")
                    
    def initialize_schema(self, force: bool = False) -> None:
        """
        Create all constraints and indexes for KG Forge schema.
        
        Args:
            force: If True, attempt to recreate existing constraints/indexes
            
        Raises:
            SchemaError: If schema initialization fails
        """
        logger.info("Initializing KG Forge schema")
        
        try:
            # Create constraints first (they also provide indexing)
            self.create_constraints()
            
            # Create additional performance indexes
            self.create_indexes()
            
            logger.info("Schema initialization completed successfully")
            
        except Exception as e:
            logger.error(f"Schema initialization failed: {e}")
            raise SchemaError(f"Schema initialization failed: {e}")
            
    def validate_schema(self) -> Dict[str, bool]:
        """
        Validate that all required constraints and indexes exist.
        
        Returns:
            Dictionary with validation results
        """
        logger.debug("Validating schema")
        
        try:
            schema_info = self.client.get_schema_info()
            
            # Get existing constraint and index names
            existing_constraints = set()
            existing_indexes = set()
            
            for constraint in schema_info.get("constraints", []):
                if "name" in constraint:
                    existing_constraints.add(constraint["name"])
                    
            for index in schema_info.get("indexes", []):
                if "name" in index:
                    existing_indexes.add(index["name"])
            
            # Check required constraints
            required_constraints = {c.name for c in self.get_required_constraints()}
            required_indexes = {i.name for i in self.get_required_indexes()}
            
            results = {
                "constraints_valid": required_constraints.issubset(existing_constraints),
                "indexes_valid": required_indexes.issubset(existing_indexes),
                "missing_constraints": list(required_constraints - existing_constraints),
                "missing_indexes": list(required_indexes - existing_indexes)
            }
            
            results["schema_valid"] = results["constraints_valid"] and results["indexes_valid"]
            
            logger.debug(f"Schema validation results: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Schema validation failed: {e}")
            raise SchemaError(f"Schema validation failed: {e}")
            
    def drop_schema(self) -> None:
        """
        Drop all KG Forge constraints and indexes.
        
        WARNING: This will remove all constraints and indexes!
        """
        logger.warning("Dropping KG Forge schema elements")
        
        try:
            # Drop constraints
            for constraint in self.get_required_constraints():
                try:
                    drop_query = f"DROP CONSTRAINT {constraint.name} IF EXISTS"
                    self.client.execute_query(drop_query)
                    logger.info(f"Dropped constraint: {constraint.name}")
                except Exception as e:
                    logger.warning(f"Failed to drop constraint {constraint.name}: {e}")
                    
            # Drop indexes  
            for index in self.get_required_indexes():
                try:
                    drop_query = f"DROP INDEX {index.name} IF EXISTS"
                    self.client.execute_query(drop_query)
                    logger.info(f"Dropped index: {index.name}")
                except Exception as e:
                    logger.warning(f"Failed to drop index {index.name}: {e}")
                    
            logger.info("Schema drop completed")
            
        except Exception as e:
            logger.error(f"Schema drop failed: {e}")
            raise SchemaError(f"Schema drop failed: {e}")
