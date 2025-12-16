"""Tests for ChromaDB vector store implementation."""

import pytest
import tempfile
import shutil
from pathlib import Path

from kg_forge.vector.chroma import ChromaVectorStore


@pytest.fixture
def temp_chroma_dir():
    """Create temporary directory for ChromaDB."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def vector_store(temp_chroma_dir):
    """Create ChromaVectorStore instance with temp directory."""
    return ChromaVectorStore(persist_directory=temp_chroma_dir)


class TestChromaVectorStore:
    """Test ChromaVectorStore class."""
    
    def test_initialization(self, temp_chroma_dir):
        """Test ChromaDB initialization."""
        store = ChromaVectorStore(persist_directory=temp_chroma_dir)
        
        assert store.persist_directory == temp_chroma_dir
        assert store.client is not None
        assert store._collections == {}
    
    def test_add_entity(self, vector_store):
        """Test adding entity embedding."""
        embedding = [0.1] * 384  # 384-dimensional vector
        
        vector_store.add_entity(
            entity_id="test:Technology:kubernetes",
            entity_type="Technology",
            entity_name="Kubernetes",
            embedding=embedding,
            namespace="test",
            metadata={"normalized_name": "kubernetes"}
        )
        
        # Verify it was added (collection should exist)
        assert "test" in vector_store._collections
    
    def test_search_similar_finds_match(self, vector_store):
        """Test finding similar entities."""
        # Add an entity
        embedding1 = [0.5] * 384
        vector_store.add_entity(
            entity_id="test:Technology:k8s",
            entity_type="Technology",
            entity_name="Kubernetes",
            embedding=embedding1,
            namespace="test"
        )
        
        # Search with very similar embedding
        embedding2 = [0.51] * 384  # Very similar
        results = vector_store.search_similar(
            entity_type="Technology",
            embedding=embedding2,
            namespace="test",
            limit=5,
            threshold=0.5  # Low threshold for testing
        )
        
        # Should find the match
        assert len(results) > 0
        entity_id, score, metadata = results[0]
        assert entity_id == "test:Technology:k8s"
        assert metadata['entity_name'] == "Kubernetes"
    
    def test_search_similar_no_match(self, vector_store):
        """Test search with no similar entities."""
        # Add entity with one pattern
        embedding1 = [1.0] + [0.0] * 383
        vector_store.add_entity(
            entity_id="test:Technology:tech1",
            entity_type="Technology",
            entity_name="Tech1",
            embedding=embedding1,
            namespace="test"
        )
        
        # Search with very different embedding
        embedding2 = [0.0] * 383 + [1.0]
        results = vector_store.search_similar(
            entity_type="Technology",
            embedding=embedding2,
            namespace="test",
            limit=5,
            threshold=0.95  # High threshold
        )
        
        # Should find no matches
        assert len(results) == 0
    
    def test_search_filters_by_entity_type(self, vector_store):
        """Test that search filters by entity type."""
        embedding = [0.5] * 384
        
        # Add entities of different types
        vector_store.add_entity(
            entity_id="test:Technology:k8s",
            entity_type="Technology",
            entity_name="Kubernetes",
            embedding=embedding,
            namespace="test"
        )
        
        vector_store.add_entity(
            entity_id="test:Product:product1",
            entity_type="Product",
            entity_name="Product1",
            embedding=embedding,
            namespace="test"
        )
        
        # Search for Technology only
        results = vector_store.search_similar(
            entity_type="Technology",
            embedding=embedding,
            namespace="test",
            limit=10,
            threshold=0.5
        )
        
        # Should only find Technology
        assert len(results) == 1
        assert results[0][2]['entity_type'] == "Technology"
    
    def test_search_filters_by_namespace(self, vector_store):
        """Test namespace isolation."""
        embedding = [0.5] * 384
        
        # Add entities in different namespaces
        vector_store.add_entity(
            entity_id="ns1:Technology:k8s",
            entity_type="Technology",
            entity_name="Kubernetes",
            embedding=embedding,
            namespace="ns1"
        )
        
        vector_store.add_entity(
            entity_id="ns2:Technology:docker",
            entity_type="Technology",
            entity_name="Docker",
            embedding=embedding,
            namespace="ns2"
        )
        
        # Search in ns1
        results = vector_store.search_similar(
            entity_type="Technology",
            embedding=embedding,
            namespace="ns1",
            limit=10,
            threshold=0.5
        )
        
        # Should only find entities from ns1
        assert len(results) == 1
        assert "ns1" in results[0][0]
    
    def test_delete_namespace(self, vector_store):
        """Test deleting entire namespace."""
        embedding = [0.5] * 384
        
        # Add entities
        vector_store.add_entity(
            entity_id="test:Technology:k8s",
            entity_type="Technology",
            entity_name="Kubernetes",
            embedding=embedding,
            namespace="test"
        )
        
        # Delete namespace
        count = vector_store.delete_namespace("test")
        
        assert count == 1
        
        # Verify collection is gone
        results = vector_store.search_similar(
            entity_type="Technology",
            embedding=embedding,
            namespace="test",
            limit=10,
            threshold=0.5
        )
        assert len(results) == 0
    
    def test_get_stats_for_namespace(self, vector_store):
        """Test getting stats for specific namespace."""
        embedding = [0.5] * 384
        
        # Add some entities
        for i in range(3):
            vector_store.add_entity(
                entity_id=f"test:Technology:tech{i}",
                entity_type="Technology",
                entity_name=f"Tech{i}",
                embedding=embedding,
                namespace="test"
            )
        
        stats = vector_store.get_stats("test")
        
        assert stats['namespace'] == "test"
        assert stats['entity_count'] == 3
        assert 'collection_name' in stats
    
    def test_get_stats_global(self, vector_store):
        """Test getting global stats."""
        embedding = [0.5] * 384
        
        # Add entities in different namespaces
        vector_store.add_entity(
            entity_id="ns1:Technology:k8s",
            entity_type="Technology",
            entity_name="Kubernetes",
            embedding=embedding,
            namespace="ns1"
        )
        
        vector_store.add_entity(
            entity_id="ns2:Technology:docker",
            entity_type="Technology",
            entity_name="Docker",
            embedding=embedding,
            namespace="ns2"
        )
        
        stats = vector_store.get_stats()
        
        assert 'total_collections' in stats
        assert stats['total_collections'] >= 2
        assert 'collections' in stats
    
    def test_persistence(self, temp_chroma_dir):
        """Test that data persists across instances."""
        embedding = [0.5] * 384
        
        # Create first instance and add data
        store1 = ChromaVectorStore(persist_directory=temp_chroma_dir)
        store1.add_entity(
            entity_id="test:Technology:k8s",
            entity_type="Technology",
            entity_name="Kubernetes",
            embedding=embedding,
            namespace="test"
        )
        
        # Create second instance (should load persisted data)
        store2 = ChromaVectorStore(persist_directory=temp_chroma_dir)
        results = store2.search_similar(
            entity_type="Technology",
            embedding=embedding,
            namespace="test",
            limit=5,
            threshold=0.5
        )
        
        # Should find the persisted entity
        assert len(results) > 0
        assert results[0][2]['entity_name'] == "Kubernetes"
    
    def test_multiple_entities_same_type(self, vector_store):
        """Test adding and searching multiple entities of same type."""
        base_embedding = [0.5] * 384
        
        # Add multiple similar entities
        for i in range(5):
            embedding = [0.5 + (i * 0.01)] + [0.5] * 383
            vector_store.add_entity(
                entity_id=f"test:Technology:tech{i}",
                entity_type="Technology",
                entity_name=f"Tech{i}",
                embedding=embedding,
                namespace="test"
            )
        
        # Search
        results = vector_store.search_similar(
            entity_type="Technology",
            embedding=base_embedding,
            namespace="test",
            limit=3,
            threshold=0.8
        )
        
        # Should find up to 3 results
        assert len(results) <= 3
        assert len(results) > 0
