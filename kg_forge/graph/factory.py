"""Factory for creating graph database clients and repositories.

This module provides factory functions to instantiate concrete implementations
of the graph abstraction layer based on configuration.

The factory ensures that consumers (CLI, business logic) only depend on abstract
interfaces, not concrete implementations.
"""

from typing import TYPE_CHECKING
from kg_forge.graph.base import (
    GraphClient,
    EntityRepository,
    DocumentRepository,
    SchemaManager,
)
from kg_forge.graph.exceptions import GraphError

if TYPE_CHECKING:
    from kg_forge.config.settings import Settings


def get_graph_client(config: "Settings") -> GraphClient:
    """Get graph client based on configuration.
    
    Args:
        config: Application settings
        
    Returns:
        GraphClient: Configured graph client instance
        
    Raises:
        GraphError: If backend type is not supported
    """
    # Note: backend defaults to "neo4j" if not specified
    backend = getattr(config, 'graph', None)
    backend_type = getattr(backend, 'backend', 'neo4j') if backend else 'neo4j'
    
    if backend_type == "neo4j":
        from kg_forge.graph.neo4j.client import Neo4jClient
        return Neo4jClient(
            uri=config.neo4j.uri,
            username=config.neo4j.username,
            password=config.neo4j.password
        )
    else:
        raise GraphError(f"Unsupported graph backend: {backend_type}")


def get_entity_repository(client: GraphClient) -> EntityRepository:
    """Get entity repository for the given client.
    
    Args:
        client: Graph client instance
        
    Returns:
        EntityRepository: Entity repository instance
        
    Raises:
        GraphError: If client type is not supported
    """
    # Import here to avoid circular dependencies
    from kg_forge.graph.neo4j.client import Neo4jClient
    from kg_forge.graph.neo4j.entity_repo import Neo4jEntityRepository
    
    if isinstance(client, Neo4jClient):
        return Neo4jEntityRepository(client)
    else:
        raise GraphError(f"No entity repository available for client type: {type(client).__name__}")


def get_document_repository(client: GraphClient) -> DocumentRepository:
    """Get document repository for the given client.
    
    Args:
        client: Graph client instance
        
    Returns:
        DocumentRepository: Document repository instance
        
    Raises:
        GraphError: If client type is not supported
    """
    # Import here to avoid circular dependencies
    from kg_forge.graph.neo4j.client import Neo4jClient
    from kg_forge.graph.neo4j.document_repo import Neo4jDocumentRepository
    
    if isinstance(client, Neo4jClient):
        return Neo4jDocumentRepository(client)
    else:
        raise GraphError(f"No document repository available for client type: {type(client).__name__}")


def get_schema_manager(client: GraphClient) -> SchemaManager:
    """Get schema manager for the given client.
    
    Args:
        client: Graph client instance
        
    Returns:
        SchemaManager: Schema manager instance
        
    Raises:
        GraphError: If client type is not supported
    """
    # Import here to avoid circular dependencies
    from kg_forge.graph.neo4j.client import Neo4jClient
    from kg_forge.graph.neo4j.schema import Neo4jSchemaManager
    
    if isinstance(client, Neo4jClient):
        return Neo4jSchemaManager(client)
    else:
        raise GraphError(f"No schema manager available for client type: {type(client).__name__}")
