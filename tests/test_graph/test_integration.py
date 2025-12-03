"""Integration tests for Neo4j database operations.

These tests use Docker (via docker-py) to spin up a real Neo4j instance and test
actual database operations end-to-end.

Compatible with both Docker Desktop and Rancher Desktop.

Run with:
  pytest tests/test_graph/test_integration.py -v -s                    # Docker Desktop
  pytest tests/test_graph/test_integration.py -v -s --rancher          # Rancher Desktop
  USE_RANCHER=true pytest tests/test_graph/test_integration.py -v -s  # Rancher via env
"""

import time
import pytest
import docker
from typing import Generator, Optional

from kg_forge.graph.neo4j.client import Neo4jClient
from kg_forge.graph.neo4j.schema import Neo4jSchemaManager
from kg_forge.graph.neo4j.entity_repo import Neo4jEntityRepository
from kg_forge.graph.neo4j.document_repo import Neo4jDocumentRepository
from kg_forge.graph.exceptions import (
    DuplicateEntityError,
    EntityNotFoundError,
    DocumentNotFoundError
)


@pytest.fixture(scope="module")
def neo4j_container(docker_client: docker.DockerClient):
    """Start a Neo4j container for integration tests.
    
    This fixture starts a Neo4j container using Docker directly,
    waits for it to be ready, and then yields the container.
    Module-scoped so the container is shared across all tests.
    """
    NEO4J_IMAGE = "neo4j:5.14.0"
    CONTAINER_NAME = "kg-forge-test-neo4j"
    
    # Pull image if needed
    try:
        docker_client.images.get(NEO4J_IMAGE)
        print(f"Neo4j image {NEO4J_IMAGE} already available")
    except docker.errors.ImageNotFound:
        print(f"Pulling Neo4j image {NEO4J_IMAGE}...")
        docker_client.images.pull(NEO4J_IMAGE)
    
    # Remove any existing container with the same name
    try:
        old_container = docker_client.containers.get(CONTAINER_NAME)
        print(f"Removing old container {CONTAINER_NAME}")
        old_container.remove(force=True)
    except docker.errors.NotFound:
        pass
    
    # Start the container
    print(f"Starting Neo4j container {CONTAINER_NAME}...")
    container = docker_client.containers.run(
        NEO4J_IMAGE,
        detach=True,
        name=CONTAINER_NAME,
        ports={"7687/tcp": 7687, "7474/tcp": 7474},
        environment={
            "NEO4J_AUTH": "neo4j/testpassword",
            "NEO4J_ACCEPT_LICENSE_AGREEMENT": "yes"
        },
        remove=True
    )
    
    # Wait for Neo4j to be ready
    max_retries = 30
    retry_interval = 2
    neo4j_ready = False
    
    print("Waiting for Neo4j to be ready...")
    for i in range(max_retries):
        try:
            # Try to connect to Neo4j
            test_client = Neo4jClient(
                uri="bolt://localhost:7687",
                username="neo4j",
                password="testpassword"
            )
            test_client.connect()
            test_client.close()
            neo4j_ready = True
            print(f"Neo4j is ready after {i * retry_interval} seconds")
            break
        except Exception as e:
            if i < max_retries - 1:
                time.sleep(retry_interval)
            else:
                print(f"Last attempt failed: {e}")
    
    if not neo4j_ready:
        container.stop()
        pytest.fail("Neo4j failed to start within the expected time")
    
    # Yield the container for tests to use
    yield container
    
    # Stop and remove the container after tests
    print("Stopping Neo4j container...")
    try:
        container.stop()
    except docker.errors.NotFound:
        print("Container already stopped")


@pytest.fixture(scope="module")
def neo4j_client(neo4j_container):
    """Create and connect a Neo4j client to the test container."""
    client = Neo4jClient(
        uri="bolt://localhost:7687",
        username="neo4j",
        password="testpassword"
    )
    client.connect()
    yield client
    client.close()


@pytest.fixture(scope="module")
def schema_manager(neo4j_client):
    """Create a schema manager with the test client."""
    manager = Neo4jSchemaManager(neo4j_client)
    # Create schema once for all tests
    manager.create_schema()
    return manager


@pytest.fixture
def entity_repo(neo4j_client):
    """Create an entity repository for each test."""
    return Neo4jEntityRepository(neo4j_client)


@pytest.fixture
def document_repo(neo4j_client):
    """Create a document repository for each test."""
    return Neo4jDocumentRepository(neo4j_client)


@pytest.fixture(autouse=True)
def cleanup_namespace(schema_manager):
    """Clean up test namespace before each test."""
    # Cleanup before test
    schema_manager.clear_namespace("test")
    yield
    # Cleanup after test
    schema_manager.clear_namespace("test")


# ============= TESTS =============

class TestSchemaManagement:
    """Test database schema operations."""
    
    def test_schema_creation(self, schema_manager):
        """Test that schema is created successfully."""
        assert schema_manager.verify_schema() is True
    
    def test_schema_verification(self, schema_manager):
        """Test schema verification detects required constraints and indexes."""
        result = schema_manager.verify_schema()
        assert result is True
    
    def test_namespace_statistics(self, schema_manager):
        """Test getting statistics for a namespace."""
        stats = schema_manager.get_statistics("test")
        assert "namespace" in stats
        assert stats["namespace"] == "test"


class TestEntityOperations:
    """Test entity CRUD operations with real database."""
    
    def test_create_entity(self, entity_repo):
        """Test creating a new entity."""
        entity = entity_repo.create_entity(
            namespace="test",
            entity_type="Product",
            name="Knowledge Discovery",
            description="AI-powered search platform"
        )
        
        assert entity is not None
        assert entity["name"] == "Knowledge Discovery"
        assert entity["entity_type"] == "Product"
        assert entity["normalized_name"] == "knowledge discovery"
        assert entity["description"] == "AI-powered search platform"
    
    def test_create_duplicate_entity_raises_error(self, entity_repo):
        """Test that creating a duplicate entity raises an error."""
        entity_repo.create_entity(namespace="test", entity_type="Product", name="Test Product")
        
        with pytest.raises(DuplicateEntityError):
            entity_repo.create_entity(namespace="test", entity_type="Product", name="Test Product")
    
    def test_get_entity(self, entity_repo):
        """Test retrieving an entity."""
        entity_repo.create_entity(namespace="test", entity_type="Team", name="Platform Engineering")
        
        retrieved = entity_repo.get_entity(namespace="test", entity_type="Team", name="Platform Engineering")
        
        assert retrieved is not None
        assert retrieved["name"] == "Platform Engineering"
        assert retrieved["entity_type"] == "Team"
    
    def test_get_nonexistent_entity_returns_none(self, entity_repo):
        """Test that getting a nonexistent entity returns None."""
        result = entity_repo.get_entity(namespace="test", entity_type="Product", name="NonExistent")
        assert result is None
    
    def test_list_entities(self, entity_repo):
        """Test listing entities."""
        entity_repo.create_entity("test", "Product", "Product A")
        entity_repo.create_entity("test", "Product", "Product B")
        entity_repo.create_entity("test", "Team", "Team A")
        
        products = entity_repo.list_entities("test", entity_type="Product")
        assert len(products) == 2
        
        all_entities = entity_repo.list_entities("test")
        assert len(all_entities) == 3
    
    def test_list_entity_types(self, entity_repo):
        """Test listing entity types."""
        entity_repo.create_entity("test", "Product", "Product 1")
        entity_repo.create_entity("test", "Team", "Team 1")
        entity_repo.create_entity("test", "Technology", "Tech 1")
        
        types = entity_repo.list_entity_types("test")
        assert len(types) == 3
        assert "Product" in types
        assert "Team" in types
        assert "Technology" in types
    
    def test_update_entity(self, entity_repo):
        """Test updating an entity."""
        entity_repo.create_entity("test", "Product", "Test Product", description="Original description")
        
        updated = entity_repo.update_entity("test", "Product", "Test Product", description="Updated description", status="active")
        
        assert updated["description"] == "Updated description"
        assert updated["status"] == "active"
    
    def test_delete_entity(self, entity_repo):
        """Test deleting an entity."""
        entity_repo.create_entity("test", "Product", "To Delete")
        assert entity_repo.get_entity("test", "Product", "To Delete") is not None
        
        result = entity_repo.delete_entity("test", "Product", "To Delete")
        assert result is True
        
        assert entity_repo.get_entity("test", "Product", "To Delete") is None
    
    def test_entity_name_normalization(self, entity_repo):
        """Test that entity names are properly normalized."""
        entity_repo.create_entity("test", "Product", "Knowledge Discovery (KD)")
        
        result = entity_repo.get_entity("test", "Product", "knowledge discovery")
        assert result is not None
        assert result["name"] == "Knowledge Discovery (KD)"
        assert result["normalized_name"] == "knowledge discovery"


class TestEntityRelationships:
    """Test entity relationship operations."""
    
    def test_create_relationship(self, entity_repo):
        """Test creating a relationship between entities."""
        entity_repo.create_entity("test", "Product", "Product A")
        entity_repo.create_entity("test", "Technology", "Python")
        
        rel = entity_repo.create_relationship("test", "Product", "Product A", "Technology", "Python", "USES", version="3.11")
        
        assert rel is not None
        assert rel["namespace"] == "test"
        assert rel["version"] == "3.11"
    
    def test_create_relationship_missing_entity_raises_error(self, entity_repo):
        """Test that creating a relationship with missing entity raises error."""
        entity_repo.create_entity("test", "Product", "Product A")
        
        with pytest.raises(EntityNotFoundError):
            entity_repo.create_relationship("test", "Product", "Product A", "Technology", "NonExistent", "USES")


class TestDocumentOperations:
    """Test document CRUD operations with real database."""
    
    def test_create_document(self, document_repo):
        """Test creating a document."""
        doc = document_repo.create_document("test", "doc_001", "test/path/doc.html", "abc123", title="Test Document")
        
        assert doc is not None
        assert doc["doc_id"] == "doc_001"
        assert doc["source_path"] == "test/path/doc.html"
        assert doc["content_hash"] == "abc123"
        assert doc["title"] == "Test Document"
    
    def test_document_exists(self, document_repo):
        """Test checking if a document exists."""
        assert document_repo.document_exists("test", "doc_123") is False
        
        document_repo.create_document("test", "doc_123", "path", "hash")
        
        assert document_repo.document_exists("test", "doc_123") is True
    
    def test_document_hash_exists(self, document_repo):
        """Test checking if a document with a hash exists."""
        assert document_repo.document_hash_exists("test", "hash123") is False
        
        document_repo.create_document("test", "doc_001", "path", "hash123")
        
        assert document_repo.document_hash_exists("test", "hash123") is True


class TestDocumentEntityLinks:
    """Test linking documents to entities."""
    
    def test_add_mention(self, document_repo, entity_repo):
        """Test adding a mention from document to entity."""
        document_repo.create_document("test", "doc_001", "path", "hash")
        entity_repo.create_entity("test", "Product", "Knowledge Discovery")
        
        mention = document_repo.add_mention("test", "doc_001", "Product", "Knowledge Discovery", confidence=0.95)
        
        assert mention is not None
        assert mention["confidence"] == 0.95
    
    def test_get_document_entities(self, document_repo, entity_repo):
        """Test getting all entities mentioned in a document."""
        document_repo.create_document("test", "doc_001", "path", "hash")
        entity_repo.create_entity("test", "Product", "Product A")
        entity_repo.create_entity("test", "Product", "Product B")
        entity_repo.create_entity("test", "Team", "Team A")
        
        document_repo.add_mention("test", "doc_001", "Product", "Product A")
        document_repo.add_mention("test", "doc_001", "Product", "Product B")
        document_repo.add_mention("test", "doc_001", "Team", "Team A")
        
        entities = document_repo.get_document_entities("test", "doc_001")
        assert len(entities) == 3
    
    def test_find_related_documents(self, document_repo, entity_repo):
        """Test finding documents that mention a specific entity."""
        entity_repo.create_entity("test", "Product", "Knowledge Discovery")
        document_repo.create_document("test", "doc_001", "path1", "hash1")
        document_repo.create_document("test", "doc_002", "path2", "hash2")
        document_repo.create_document("test", "doc_003", "path3", "hash3")
        
        document_repo.add_mention("test", "doc_001", "Product", "Knowledge Discovery")
        document_repo.add_mention("test", "doc_002", "Product", "Knowledge Discovery")
        
        docs = document_repo.find_related_documents("test", "Product", "Knowledge Discovery")
        assert len(docs) == 2
        doc_ids = {doc["doc_id"] for doc in docs}
        assert "doc_001" in doc_ids
        assert "doc_002" in doc_ids
        assert "doc_003" not in doc_ids


class TestNamespaceIsolation:
    """Test that namespaces properly isolate data."""
    
    def test_entities_isolated_by_namespace(self, entity_repo, schema_manager):
        """Test that entities in different namespaces don't interfere."""
        entity_repo.create_entity("test", "Product", "Product A")
        
        schema_manager.clear_namespace("other")
        entity_repo.create_entity("other", "Product", "Product A")
        
        test_entities = entity_repo.list_entities("test")
        other_entities = entity_repo.list_entities("other")
        
        assert len(test_entities) == 1
        assert len(other_entities) == 1
        
        # Cleanup
        schema_manager.clear_namespace("other")
