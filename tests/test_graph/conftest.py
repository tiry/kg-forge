"""Shared pytest fixtures for graph tests."""

import os
import time
import pytest
import docker
from pathlib import Path
from unittest.mock import Mock, MagicMock
from typing import Generator, Optional

from kg_forge.graph.neo4j.client import Neo4jClient
from kg_forge.graph.neo4j.entity_repo import Neo4jEntityRepository
from kg_forge.graph.neo4j.document_repo import Neo4jDocumentRepository
from kg_forge.graph.neo4j.schema import Neo4jSchemaManager


# Configure pytest to add --rancher option
def pytest_addoption(parser):
    """Add custom pytest command line options."""
    parser.addoption(
        "--rancher",
        action="store_true",
        default=False,
        help="Use Rancher Desktop Docker socket",
    )


@pytest.fixture(scope="session")
def docker_client(request: pytest.FixtureRequest) -> docker.DockerClient:
    """Create a Docker client compatible with both Docker and Rancher Desktop.
    
    This fixture auto-detects which Docker environment to use:
    1. Auto-detect: Check if ~/.rd/docker.sock exists (Rancher Desktop)
    2. --rancher flag: Force Rancher Desktop socket
    3. USE_RANCHER env var: Force Rancher Desktop socket
    4. Default: Use standard Docker socket
    """
    # Check explicit flags first
    explicit_rancher = request.config.getoption("--rancher") or os.environ.get("USE_RANCHER", "").lower() in ("true", "1", "yes")
    
    # Auto-detect Rancher Desktop by checking if socket exists
    home = Path.home()
    rancher_socket_path = home / ".rd" / "docker.sock"
    auto_detected_rancher = rancher_socket_path.exists()
    
    use_rancher = explicit_rancher or auto_detected_rancher
    
    if use_rancher:
        # Use the Docker socket location for Rancher Desktop
        socket_path = f"unix://{rancher_socket_path}"
        if auto_detected_rancher and not explicit_rancher:
            print(f"Auto-detected Rancher Desktop Docker socket: {socket_path}", flush=True)
        else:
            print(f"Using Rancher Desktop Docker socket: {socket_path}", flush=True)
        return docker.DockerClient(base_url=socket_path)
    else:
        # Use the default Docker socket location
        print("Using default Docker socket", flush=True)
        return docker.DockerClient()


# ============= MOCK FIXTURES (for unit tests) =============

@pytest.fixture
def mock_neo4j_client():
    """Create a mocked Neo4j client."""
    client = Mock(spec=Neo4jClient)
    client.uri = "bolt://localhost:7687"
    client.username = "neo4j"
    client.password = "password"
    client.database = "neo4j"
    client._driver = MagicMock()
    return client


@pytest.fixture
def entity_repo(mock_neo4j_client):
    """Create an entity repository with mocked client."""
    return Neo4jEntityRepository(mock_neo4j_client)


@pytest.fixture
def document_repo(mock_neo4j_client):
    """Create a document repository with mocked client."""
    return Neo4jDocumentRepository(mock_neo4j_client)


@pytest.fixture
def schema_manager(mock_neo4j_client):
    """Create a schema manager with mocked client."""
    return Neo4jSchemaManager(mock_neo4j_client)


@pytest.fixture
def sample_entity():
    """Sample entity data for testing."""
    return {
        "namespace": "default",
        "entity_type": "Product",
        "name": "Knowledge Discovery",
        "normalized_name": "knowledge discovery",
        "created_at": 1234567890
    }


@pytest.fixture
def sample_document():
    """Sample document data for testing."""
    return {
        "namespace": "default",
        "doc_id": "test_doc_123",
        "source_path": "test/path/doc.html",
        "content_hash": "abc123def456",
        "created_at": 1234567890
    }
