"""Custom exceptions for graph database operations."""


class GraphError(Exception):
    """Base exception for graph database errors."""
    pass


class ConnectionError(GraphError):
    """Error connecting to graph database."""
    pass


class SchemaError(GraphError):
    """Error related to database schema."""
    pass


class EntityNotFoundError(GraphError):
    """Entity not found in graph."""
    
    def __init__(self, namespace: str, entity_type: str, name: str):
        self.namespace = namespace
        self.entity_type = entity_type
        self.name = name
        super().__init__(
            f"Entity not found: {entity_type}='{name}' in namespace '{namespace}'"
        )


class DocumentNotFoundError(GraphError):
    """Document not found in graph."""
    
    def __init__(self, namespace: str, doc_id: str):
        self.namespace = namespace
        self.doc_id = doc_id
        super().__init__(
            f"Document not found: '{doc_id}' in namespace '{namespace}'"
        )


class DuplicateEntityError(GraphError):
    """Entity already exists in graph."""
    
    def __init__(self, namespace: str, entity_type: str, name: str):
        self.namespace = namespace
        self.entity_type = entity_type
        self.name = name
        super().__init__(
            f"Entity already exists: {entity_type}='{name}' in namespace '{namespace}'"
        )


class InvalidNamespaceError(GraphError):
    """Invalid namespace name."""
    
    def __init__(self, namespace: str, reason: str = ""):
        self.namespace = namespace
        msg = f"Invalid namespace: '{namespace}'"
        if reason:
            msg += f" - {reason}"
        super().__init__(msg)
