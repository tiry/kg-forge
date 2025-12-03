# Step 4: Neo4j Bootstrap and Basic Operations

## Overview

Implement Neo4j database connectivity, schema initialization, and basic graph operations. This step establishes the foundation for storing and querying the knowledge graph.

## Goals

1. Connect to Neo4j database with configuration
2. Initialize database schema (constraints, indexes)
3. Implement entity CRUD operations
4. Add CLI commands for database management
5. Implement basic query operations
6. Set up testing with Docker/pytest fixtures

## Architecture: Graph Backend Abstraction

To avoid Neo4j dependencies throughout the codebase and enable future backend swapping, we'll use an abstraction layer:

**Design Pattern**: Repository pattern with abstract base classes

**Structure**:
```
kg_forge/graph/
├── __init__.py
├── base.py                    # Abstract base classes
├── exceptions.py              # Graph-specific exceptions
├── neo4j/                     # Neo4j implementation (isolated)
│   ├── __init__.py
│   ├── client.py              # Neo4j connection manager
│   ├── entity_repo.py         # Neo4j entity repository impl
│   ├── document_repo.py       # Neo4j document repository impl
│   └── schema.py              # Neo4j schema manager
└── factory.py                 # Factory to get implementations
```

**Key Principles**:
- CLI and business logic only import from `kg_forge.graph` (not `kg_forge.graph.neo4j`)
- Abstract base classes define the interface
- Factory provides concrete implementations
- Neo4j-specific code isolated in `neo4j/` subdirectory

## Components to Implement

### 1. Abstract Base Classes

**Location**: `kg_forge/graph/base.py`

**Responsibilities**:
- Define interfaces for graph operations
- No Neo4j dependencies
- Can be implemented by different backends

**Key Classes**:
```python
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any

class GraphClient(ABC):
    """Abstract base for graph database client."""
    
    @abstractmethod
    def connect(self) -> bool:
        """Connect to the graph database."""
        pass
    
    @abstractmethod
    def close(self):
        """Close connection."""
        pass
    
    @abstractmethod
    def verify_connectivity(self) -> bool:
        """Verify database is accessible."""
        pass

class EntityRepository(ABC):
    """Abstract base for entity operations."""
    
    @abstractmethod
    def create_entity(self, namespace: str, entity_type: str, 
                     name: str, **properties) -> dict:
        pass
    
    @abstractmethod
    def get_entity(self, namespace: str, entity_type: str, 
                  name: str) -> Optional[dict]:
        pass
    
    @abstractmethod
    def list_entities(self, namespace: str, 
                     entity_type: Optional[str] = None,
                     limit: int = 100) -> List[dict]:
        pass
    
    @abstractmethod
    def list_entity_types(self, namespace: str) -> List[str]:
        pass
    
    # ... other methods

class DocumentRepository(ABC):
    """Abstract base for document operations."""
    
    @abstractmethod
    def create_document(self, namespace: str, doc_id: str, 
                       source_path: str, content_hash: str,
                       **metadata) -> dict:
        pass
    
    @abstractmethod
    def get_document(self, namespace: str, doc_id: str) -> Optional[dict]:
        pass
    
    # ... other methods

class SchemaManager(ABC):
    """Abstract base for schema operations."""
    
    @abstractmethod
    def create_schema(self):
        """Create necessary constraints and indexes."""
        pass
    
    @abstractmethod
    def verify_schema(self) -> bool:
        """Verify schema is correctly set up."""
        pass
    
    # ... other methods
```

### 2. Graph Factory

**Location**: `kg_forge/graph/factory.py`

**Responsibilities**:
- Instantiate concrete implementations based on configuration
- Hide implementation details from consumers

**Key Function**:
```python
def get_graph_client(config) -> GraphClient:
    """Get graph client based on configuration."""
    backend = config.graph.backend  # e.g., "neo4j"
    if backend == "neo4j":
        from kg_forge.graph.neo4j.client import Neo4jClient
        return Neo4jClient(
            uri=config.neo4j.uri,
            username=config.neo4j.username,
            password=config.neo4j.password
        )
    else:
        raise ValueError(f"Unsupported backend: {backend}")

def get_entity_repository(client: GraphClient) -> EntityRepository:
    """Get entity repository for the client."""
    if isinstance(client, Neo4jClient):
        from kg_forge.graph.neo4j.entity_repo import Neo4jEntityRepository
        return Neo4jEntityRepository(client)
    else:
        raise ValueError(f"No repository for client type: {type(client)}")

# Similar for DocumentRepository, SchemaManager
```

### 3. Neo4j Connection Manager

**Location**: `kg_forge/graph/neo4j/client.py`

**Responsibilities**:
- Establish connection to Neo4j using credentials from config
- Provide context manager for session handling
- Handle connection errors gracefully
- Support namespace isolation

**Key Methods**:
```python
class Neo4jClient(GraphClient):
    """Neo4j implementation of GraphClient."""
    
    def __init__(self, uri, username, password, database="neo4j")
    def connect() -> bool
    def close()
    def execute_query(query: str, params: dict) -> list
    def execute_write(query: str, params: dict)
    def verify_connectivity() -> bool
```

### 4. Neo4j Schema Manager

**Location**: `kg_forge/graph/neo4j/schema.py`

**Responsibilities**:
- Create constraints for uniqueness
- Create indexes for performance
- Validate schema exists
- Reset/clear namespace data

**Schema Requirements**:

**Constraints**:
- `:Doc` nodes: unique on `(namespace, doc_id)`
- `:Entity` nodes: unique on `(namespace, entity_type, normalized_name)`

**Indexes**:
- `:Doc(namespace)`
- `:Doc(content_hash)`
- `:Entity(namespace)`
- `:Entity(entity_type)`
- `:Entity(name)`

**Key Methods**:
```python
class Neo4jSchemaManager(SchemaManager):
    """Neo4j implementation of SchemaManager."""
    
    def create_schema()
    def create_constraints()
    def create_indexes()
    def verify_schema() -> bool
    def clear_namespace(namespace: str)
```

### 5. Neo4j Entity Repository

**Location**: `kg_forge/graph/neo4j/entity_repo.py`

**Responsibilities**:
- CRUD operations for Entity nodes
- Query entities by type, name, namespace
- Handle entity normalization
- Manage entity relationships

**Key Methods**:
```python
class Neo4jEntityRepository(EntityRepository):
    """Neo4j implementation of EntityRepository."""
    
    def __init__(self, client: Neo4jClient)
    
    def create_entity(namespace: str, entity_type: str, 
                     name: str, **properties) -> dict
    
    def get_entity(namespace: str, entity_type: str, 
                  name: str) -> Optional[dict]
    
    def list_entities(namespace: str, entity_type: Optional[str] = None,
                     limit: int = 100) -> list[dict]
    
    def list_entity_types(namespace: str) -> list[str]
    
    def update_entity(namespace: str, entity_type: str, name: str,
                     **properties) -> dict
    
    def delete_entity(namespace: str, entity_type: str, name: str) -> bool
    
    def create_relationship(namespace: str, 
                          from_entity: dict, 
                          to_entity: dict,
                          rel_type: str,
                          **properties)
    
    def normalize_name(name: str) -> str
```

### 6. Neo4j Document Repository

**Location**: `kg_forge/graph/neo4j/document_repo.py`

**Responsibilities**:
- CRUD operations for Doc nodes
- Link documents to entities (MENTIONS relationships)
- Check for existing documents by hash
- Query documents

**Key Methods**:
```python
class Neo4jDocumentRepository(DocumentRepository):
    """Neo4j implementation of DocumentRepository."""
    
    def __init__(self, client: Neo4jClient)
    
    def create_document(namespace: str, doc_id: str, 
                       source_path: str, content_hash: str,
                       **metadata) -> dict
    
    def get_document(namespace: str, doc_id: str) -> Optional[dict]
    
    def document_exists(namespace: str, doc_id: str) -> bool
    
    def document_hash_exists(namespace: str, content_hash: str) -> bool
    
    def list_documents(namespace: str, limit: int = 100) -> list[dict]
    
    def add_mention(namespace: str, doc_id: str, 
                   entity_type: str, entity_name: str,
                   **properties)
    
    def get_document_entities(namespace: str, doc_id: str) -> list[dict]
    
    def find_related_documents(namespace: str, entity_type: str,
                              entity_name: str, limit: int = 10) -> list[dict]
```

### 7. CLI Integration (No Neo4j Dependencies!)

**Important**: CLI code should only import from `kg_forge.graph`, never from `kg_forge.graph.neo4j`

**Usage Pattern in CLI**:
```python
from kg_forge.graph.factory import (
    get_graph_client,
    get_entity_repository,
    get_document_repository,
    get_schema_manager
)
from kg_forge.config.settings import get_settings

# Get implementations without knowing they're Neo4j
config = get_settings()
client = get_graph_client(config)
entity_repo = get_entity_repository(client)
document_repo = get_document_repository(client)
schema_mgr = get_schema_manager(client)

# Use abstract interfaces
entities = entity_repo.list_entities(namespace="default")
```

### 8. CLI Commands Updates

**Extend existing commands**:

**`kg-forge neo4j-start`** (already exists)
- Enhance to wait for Neo4j to be ready
- Verify connectivity before returning

**`kg-forge neo4j-stop`** (already exists)
- Add graceful shutdown

**New commands**:

**`kg-forge db init`**
```bash
kg-forge db init [--namespace default] [--drop-existing]
```
- Create schema (constraints, indexes)
- Optionally drop existing data for namespace

**`kg-forge db status`**
```bash
kg-forge db status
```
- Show connection status
- Display schema status (constraints, indexes)
- Show statistics (nodes, relationships by namespace)

**`kg-forge db clear`**
```bash
kg-forge db clear --namespace <namespace> [--confirm]
```
- Clear all data for a namespace
- Require confirmation flag

**Update existing query commands**:

**`kg-forge query list-types`**
- Now actually queries Neo4j for entity types in namespace

**`kg-forge query list-entities --type <type>`**
- Query Neo4j for entities of specified type

**`kg-forge query list-docs`**
- Query Neo4j for documents in namespace

**`kg-forge query show-doc --id <doc-id>`**
- Show document details and related entities

**`kg-forge query find-related --entity <name> --type <type>`**
- Find documents that mention the entity

### 9. Testing Strategy

**Test Infrastructure**:
- Use pytest fixtures for Neo4j Docker container
- Use `testcontainers` Python library for Docker management
- Create test fixtures for sample graph data

**Test Coverage**:
- Connection management
- Schema creation
- Entity CRUD operations
- Document CRUD operations
- Relationship creation
- Query operations
- Namespace isolation
- Error handling

**Test Structure**:
```
tests/test_graph/
├── __init__.py
├── conftest.py              # Shared fixtures
├── test_neo4j_client.py
├── test_schema.py
├── test_entity_repository.py
├── test_document_repository.py
└── test_cli_db.py
```

## Implementation Plan

### Phase 1: Abstraction Layer
1. Create `kg_forge/graph/` package structure
2. Implement abstract base classes in `base.py`
3. Implement factory in `factory.py`
4. Create exceptions in `exceptions.py`
5. Write tests for factory pattern

### Phase 2: Neo4j Implementation
1. Create `kg_forge/graph/neo4j/` package
2. Implement `Neo4jClient`
3. Implement `Neo4jSchemaManager`
4. Add neo4j-driver to requirements.txt
5. Write unit tests with mocked Neo4j driver

### Phase 3: Neo4j Repositories
1. Implement `Neo4jEntityRepository`
2. Implement `Neo4jDocumentRepository`
3. Add relationship management
4. Write repository tests (mocked + integration)

### Phase 4: CLI Integration
1. Implement `db` command group
2. Update existing `query` commands to use Neo4j
3. Enhance `neo4j-start/stop` commands
4. Write CLI integration tests

### Phase 5: Integration Testing
1. Add testcontainers to dev dependencies
2. Create pytest fixtures for Neo4j container
3. Create fixtures for sample graph data
4. Write integration tests

## Design Decisions

The following design decisions have been made for this implementation:

### 1. Neo4j Deployment Strategy

**Decision**: Use Docker for both development and testing.

**Rationale**: 
- Provides consistent environment across development and CI
- `neo4j-start` command will manage Docker container lifecycle
- Testcontainers will be used for integration tests
- Simplifies setup - no manual Neo4j installation required

**Implementation**:
- `neo4j-start` launches Neo4j in Docker container
- `neo4j-stop` stops and removes the container
- Wait for Neo4j readiness before returning from start command
- Use same Docker approach in test fixtures

### 2. Entity Node Labeling

**Decision**: Use single `:Entity` label only, with `entity_type` as property.

**Rationale**:
- Simpler schema to start with
- Easier querying with consistent label
- Type stored in `entity_type` property
- Can add type-specific labels later if needed without breaking changes

**Schema**:
```cypher
(:Entity {
  namespace: "default",
  entity_type: "Product",
  name: "Knowledge Discovery",
  normalized_name: "knowledge discovery"
})
```

### 3. Relationship Direction

**Decision**: Create relationships in canonical direction only.

**Rationale**:
- The entity type whose markdown file defines the relation is the source
- Prevents duplicate bidirectional relationships
- Simpler to reason about and maintain
- Example: If `team.md` has `product : works_on : worked_on_by`
  - Creates: `(Team)-[:WORKS_ON]->(Product)`
  - Does NOT create reverse: `(Product)-[:WORKED_ON_BY]->(Team)`

**Note**: Relationship labels will be uppercase (Neo4j convention).

### 4. Testing Strategy

**Decision**: Hybrid approach - mocks for unit tests, Docker for integration tests.

**Rationale**:
- Unit tests with mocked Neo4j driver are fast and don't require infrastructure
- Integration tests with testcontainers verify real Neo4j functionality
- Best of both worlds: speed for TDD, confidence from real tests

**Implementation**:
- Unit tests: Mock `neo4j.Driver` for fast feedback
- Integration tests: Use `testcontainers` with real Neo4j
- Shared fixtures in `conftest.py` for both approaches

### 5. Name Normalization Rules

**Decision**: Remove content in parentheses, lowercase, preserve spaces between words.

**Normalization Algorithm**:
1. Remove parenthetical content (e.g., "(KD)", "(v2)")
2. Convert to lowercase
3. Trim whitespace
4. Collapse multiple spaces to single space
5. Keep alphanumeric characters and spaces

**Examples**:
- `"Knowledge Discovery (KD)"` → `"knowledge discovery"`
- `"Platform  Engineering"` → `"platform engineering"`
- `"AI/ML Platform"` → `"ai ml platform"`
- `"Team-Alpha"` → `"team alpha"`

**Rationale**: Balances readability with normalization needs for matching.

### 6. Database Initialization Strategy

**Decision**: `db init` creates schema only (constraints, indexes), no entity instances.

**Rationale**:
- Separation of concerns: schema vs data
- Entity instances come from ingestion (Step 6)
- Cleaner, more predictable initialization
- Easier to reset and re-initialize

**What `db init` Does**:
- Create uniqueness constraints
- Create performance indexes
- Verify connectivity
- Optionally clear existing namespace data (with `--drop-existing`)

**What `db init` Does NOT Do**:
- Create entity type nodes
- Create entity instances
- Import markdown definitions

## Dependencies to Add

```txt
neo4j>=5.14.0              # Neo4j Python driver
testcontainers>=3.7.0      # For Neo4j testing (dev dependency)
```

## Success Criteria

- [ ] Can connect to Neo4j with configuration
- [ ] Schema (constraints, indexes) created successfully
- [ ] Can create, read, update, delete entities
- [ ] Can create, read documents
- [ ] Can create MENTIONS relationships
- [ ] Can query by namespace (isolation works)
- [ ] All CLI commands work as specified
- [ ] Tests pass with Neo4j testcontainer
- [ ] Test coverage > 80% for graph module
- [ ] Documentation updated

## Answers Summary

Based on your feedback, here are the confirmed decisions:

1. **Neo4j Deployment**: Docker for both dev and tests
2. **Entity Labels**: Single `:Entity` label only (no type-specific labels)
3. **Relationships**: Canonical direction only (from .md file owner)
4. **Testing**: Mocks for unit tests, Docker for integration tests
5. **Name Normalization**: "Knowledge Discovery (KD)" → "knowledge discovery" (removes acronyms in parentheses)
6. **Initial Population**: Schema only, no entity instances

## Files to Create/Modify

**New files** (~16):
```
kg_forge/graph/
├── __init__.py               # Package exports
├── base.py                   # Abstract base classes
├── factory.py                # Factory functions
├── exceptions.py             # Graph exceptions
└── neo4j/                    # Neo4j implementation (isolated)
    ├── __init__.py
    ├── client.py             # Neo4jClient
    ├── schema.py             # Neo4jSchemaManager
    ├── entity_repo.py        # Neo4jEntityRepository
    └── document_repo.py      # Neo4jDocumentRepository

kg_forge/cli/
└── db.py                     # DB command group

tests/test_graph/
├── __init__.py
├── conftest.py               # Shared fixtures (Neo4j testcontainer)
├── test_factory.py           # Factory tests
├── test_neo4j_client.py      # Client tests (mocked + integration)
├── test_schema.py            # Schema tests
├── test_entity_repository.py # Entity repo tests
├── test_document_repository.py # Document repo tests
└── test_cli_db.py            # CLI integration tests
```

**Modified files** (~6):
```
kg_forge/cli/main.py          # Add db command group
kg_forge/cli/query.py         # Use graph factory (no Neo4j imports!)
kg_forge/cli/neo4j_ops.py     # Enhance start/stop with Docker
kg_forge/config/settings.py   # Add graph.backend config
kg_forge/requirements.txt     # Add neo4j driver + testcontainers
README.md                     # Update documentation
```

---

**Specification complete and ready for implementation!**
