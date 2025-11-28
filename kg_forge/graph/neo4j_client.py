"""Neo4j database client with schema management."""

import logging
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

try:
    from neo4j import GraphDatabase, Driver, Session
    from neo4j.exceptions import ServiceUnavailable, AuthError, ClientError
except ImportError:
    raise ImportError(
        "Neo4j driver is required but not installed. "
        "Run: pip install neo4j>=5.0.0"
    )

from ..config.settings import Settings
from .exceptions import Neo4jConnectionError, QueryError

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Neo4j database client with connection management and basic operations."""
    
    def __init__(self, settings: Optional[Settings] = None):
        """Initialize client with configuration."""
        if settings is None:
            from ..config.settings import get_settings
            settings = get_settings()
            
        self.config = settings.neo4j
        self.driver: Optional[Driver] = None
        self._connected = False
        
    def connect(self) -> None:
        """
        Establish connection to Neo4j database.
        
        Raises:
            Neo4jConnectionError: If connection fails
        """
        if self._connected:
            logger.debug("Already connected to Neo4j")
            return
            
        try:
            logger.info(f"Connecting to Neo4j at {self.config.uri}")
            
            self.driver = GraphDatabase.driver(
                self.config.uri,
                auth=(self.config.username, self.config.password)
            )
            
            # Test the connection
            with self.driver.session(database=self.config.database) as session:
                result = session.run("RETURN 1 as test")
                test_value = result.single()["test"]
                if test_value != 1:
                    raise Neo4jConnectionError("Connection test failed")
            
            self._connected = True
            logger.info(f"Successfully connected to Neo4j database '{self.config.database}'")
            
        except ServiceUnavailable as e:
            raise Neo4jConnectionError(
                f"Cannot connect to Neo4j at {self.config.uri}. "
                f"Is Neo4j running? Error: {e}"
            )
        except AuthError as e:
            raise Neo4jConnectionError(
                f"Authentication failed for user '{self.config.username}'. "
                f"Check your credentials. Error: {e}"
            )
        except Exception as e:
            raise Neo4jConnectionError(f"Failed to connect to Neo4j: {e}")
            
    def disconnect(self) -> None:
        """Close database connection and clean up resources."""
        if self.driver:
            logger.debug("Closing Neo4j connection")
            self.driver.close()
            self.driver = None
            self._connected = False
            
    def test_connection(self) -> bool:
        """Test database connectivity and return status."""
        try:
            if not self._connected:
                self.connect()
                
            with self.driver.session(database=self.config.database) as session:
                result = session.run(
                    "CALL dbms.components() YIELD name, versions "
                    "WHERE name = 'Neo4j Kernel' "
                    "RETURN versions[0] as version"
                )
                version_record = result.single()
                if version_record:
                    version = version_record["version"]
                    logger.info(f"Neo4j connection successful, version: {version}")
                else:
                    logger.info("Neo4j connection successful")
                    
                return True
                
        except Exception as e:
            logger.error(f"Neo4j connection test failed: {e}")
            return False
    
    @contextmanager
    def session(self):
        """Context manager for database sessions."""
        if not self._connected:
            self.connect()
            
        session = self.driver.session(database=self.config.database)
        try:
            yield session
        finally:
            session.close()
            
    def execute_query(self, query: str, parameters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Execute arbitrary Cypher query and return results.
        
        Args:
            query: Cypher query string
            parameters: Query parameters
            
        Returns:
            List of result records as dictionaries
            
        Raises:
            QueryError: If query execution fails
        """
        if parameters is None:
            parameters = {}
            
        try:
            with self.session() as session:
                logger.debug(f"Executing query: {query}")
                logger.debug(f"Parameters: {parameters}")
                
                result = session.run(query, parameters)
                records = [record.data() for record in result]
                
                logger.debug(f"Query returned {len(records)} records")
                return records
                
        except ClientError as e:
            raise QueryError(f"Query execution failed: {e}")
        except Exception as e:
            raise QueryError(f"Unexpected error during query execution: {e}")
            
    def clear_database(self, namespace: Optional[str] = None) -> int:
        """
        Clear all nodes and relationships, optionally filtered by namespace.
        
        Args:
            namespace: If provided, only clear nodes in this namespace
            
        Returns:
            Number of nodes deleted
        """
        if namespace:
            # Clear specific namespace
            query = """
            MATCH (n)
            WHERE n.namespace = $namespace
            DETACH DELETE n
            RETURN count(n) as deleted_count
            """
            parameters = {"namespace": namespace}
            logger.info(f"Clearing namespace: {namespace}")
        else:
            # Clear entire database
            query = """
            MATCH (n)
            DETACH DELETE n  
            RETURN count(n) as deleted_count
            """
            parameters = {}
            logger.info("Clearing entire database")
            
        try:
            result = self.execute_query(query, parameters)
            deleted_count = result[0]["deleted_count"] if result else 0
            
            logger.info(f"Deleted {deleted_count} nodes")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to clear database: {e}")
            raise QueryError(f"Database clear operation failed: {e}")
            
    def get_schema_info(self) -> Dict[str, Any]:
        """Return current database schema information (constraints, indexes)."""
        try:
            # Get constraints
            constraints_query = "SHOW CONSTRAINTS"
            constraints = self.execute_query(constraints_query)
            
            # Get indexes  
            indexes_query = "SHOW INDEXES"
            indexes = self.execute_query(indexes_query)
            
            return {
                "constraints": constraints,
                "indexes": indexes
            }
            
        except Exception as e:
            logger.error(f"Failed to get schema info: {e}")
            raise QueryError(f"Schema info retrieval failed: {e}")
            
    def get_entity_types(self, namespace: str = "default") -> List[str]:
        """Get list of distinct entity_type values in namespace."""
        query = """
        MATCH (e:Entity)
        WHERE e.namespace = $namespace
        RETURN DISTINCT e.entity_type as entity_type
        ORDER BY entity_type
        """
        
        try:
            result = self.execute_query(query, {"namespace": namespace})
            return [record["entity_type"] for record in result]
            
        except Exception as e:
            logger.error(f"Failed to get entity types: {e}")
            raise QueryError(f"Entity types retrieval failed: {e}")
            
    def get_node_counts(self, namespace: str = "default") -> Dict[str, int]:
        """Get count of Doc and Entity nodes by namespace."""
        queries = {
            "docs": "MATCH (d:Doc) WHERE d.namespace = $namespace RETURN count(d) as count",
            "entities": "MATCH (e:Entity) WHERE e.namespace = $namespace RETURN count(e) as count"
        }
        
        try:
            counts = {}
            for label, query in queries.items():
                result = self.execute_query(query, {"namespace": namespace})
                counts[label] = result[0]["count"] if result else 0
                
            return counts
            
        except Exception as e:
            logger.error(f"Failed to get node counts: {e}")
            raise QueryError(f"Node counts retrieval failed: {e}")
            
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
