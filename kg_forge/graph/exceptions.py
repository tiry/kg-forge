"""Custom exceptions for graph database operations."""


class GraphDatabaseError(Exception):
    """Base exception for graph database operations."""
    pass


class Neo4jConnectionError(GraphDatabaseError):
    """Exception raised when Neo4j connection fails."""
    pass


class SchemaError(GraphDatabaseError):
    """Exception raised when schema operations fail."""
    pass


class QueryError(GraphDatabaseError):
    """Exception raised when query execution fails."""
    pass
