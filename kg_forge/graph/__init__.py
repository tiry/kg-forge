"""Graph database abstraction layer for kg-forge.

This package provides backend-agnostic interfaces for graph operations,
with concrete implementations for specific graph databases (e.g., Neo4j).

Usage:
    from kg_forge.graph.factory import (
        get_graph_client,
        get_entity_repository,
        get_document_repository,
        get_schema_manager
    )
    
    client = get_graph_client(config)
    entity_repo = get_entity_repository(client)
"""

from kg_forge.graph.base import (
    GraphClient,
    EntityRepository,
    DocumentRepository,
    SchemaManager,
)

__all__ = [
    "GraphClient",
    "EntityRepository", 
    "DocumentRepository",
    "SchemaManager",
]
