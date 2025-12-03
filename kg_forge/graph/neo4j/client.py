"""Neo4j client implementation for graph database operations."""

import logging
from typing import List, Dict, Any, Optional
from neo4j import GraphDatabase, Driver, Session, Result
from neo4j.exceptions import ServiceUnavailable, AuthError

from kg_forge.graph.base import GraphClient
from kg_forge.graph.exceptions import ConnectionError as GraphConnectionError

logger = logging.getLogger(__name__)


class Neo4jClient(GraphClient):
    """Neo4j implementation of GraphClient.
    
    Manages connection to Neo4j database and provides low-level
    query execution capabilities.
    """
    
    def __init__(
        self,
        uri: str,
        username: str,
        password: str,
        database: str = "neo4j"
    ):
        """Initialize Neo4j client.
        
        Args:
            uri: Neo4j connection URI (e.g., bolt://localhost:7687)
            username: Database username
            password: Database password
            database: Database name (default: neo4j)
        """
        self.uri = uri
        self.username = username
        self.password = password
        self.database = database
        self._driver: Optional[Driver] = None
        
    def connect(self) -> bool:
        """Connect to Neo4j database.
        
        Returns:
            bool: True if connection successful
            
        Raises:
            GraphConnectionError: If connection fails
        """
        try:
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password)
            )
            # Verify connectivity
            self._driver.verify_connectivity()
            logger.info(f"Connected to Neo4j at {self.uri}")
            return True
        except AuthError as e:
            raise GraphConnectionError(f"Authentication failed: {e}")
        except ServiceUnavailable as e:
            raise GraphConnectionError(f"Neo4j service unavailable: {e}")
        except Exception as e:
            raise GraphConnectionError(f"Failed to connect to Neo4j: {e}")
    
    def close(self) -> None:
        """Close the database connection.
        
        Idempotent - safe to call multiple times.
        """
        if self._driver:
            self._driver.close()
            self._driver = None
            logger.info("Closed Neo4j connection")
    
    def verify_connectivity(self) -> bool:
        """Verify that the database is accessible.
        
        Returns:
            bool: True if database responds, False otherwise
        """
        if not self._driver:
            return False
        
        try:
            self._driver.verify_connectivity()
            return True
        except Exception as e:
            logger.error(f"Connectivity verification failed: {e}")
            return False
    
    def execute_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Execute a read query and return results.
        
        Args:
            query: Cypher query string
            parameters: Query parameters
            
        Returns:
            list: List of result records as dictionaries
            
        Raises:
            GraphConnectionError: If not connected or query fails
        """
        if not self._driver:
            raise GraphConnectionError("Not connected to database")
        
        parameters = parameters or {}
        
        try:
            with self._driver.session(database=self.database) as session:
                result = session.run(query, parameters)
                return [dict(record) for record in result]
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Parameters: {parameters}")
            raise GraphConnectionError(f"Query execution failed: {e}")
    
    def execute_write(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a write query and return summary.
        
        Args:
            query: Cypher query string
            parameters: Query parameters
            
        Returns:
            dict: Query execution summary
            
        Raises:
            GraphConnectionError: If not connected or query fails
        """
        if not self._driver:
            raise GraphConnectionError("Not connected to database")
        
        parameters = parameters or {}
        
        try:
            with self._driver.session(database=self.database) as session:
                result = session.run(query, parameters)
                summary = result.consume()
                return {
                    "nodes_created": summary.counters.nodes_created,
                    "nodes_deleted": summary.counters.nodes_deleted,
                    "relationships_created": summary.counters.relationships_created,
                    "relationships_deleted": summary.counters.relationships_deleted,
                    "properties_set": summary.counters.properties_set,
                }
        except Exception as e:
            logger.error(f"Write query execution failed: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Parameters: {parameters}")
            raise GraphConnectionError(f"Write query execution failed: {e}")
    
    def execute_write_tx(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Execute a write transaction and return results.
        
        Useful for write queries that also return data (e.g., MERGE ... RETURN).
        
        Args:
            query: Cypher query string
            parameters: Query parameters
            
        Returns:
            list: List of result records as dictionaries
            
        Raises:
            GraphConnectionError: If not connected or query fails
        """
        if not self._driver:
            raise GraphConnectionError("Not connected to database")
        
        parameters = parameters or {}
        
        def _tx_function(tx):
            result = tx.run(query, parameters)
            return [dict(record) for record in result]
        
        try:
            with self._driver.session(database=self.database) as session:
                return session.execute_write(_tx_function)
        except Exception as e:
            logger.error(f"Write transaction failed: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Parameters: {parameters}")
            raise GraphConnectionError(f"Write transaction failed: {e}")
    
    @property
    def driver(self) -> Optional[Driver]:
        """Get the underlying Neo4j driver.
        
        Returns:
            Driver: Neo4j driver instance, or None if not connected
        """
        return self._driver
