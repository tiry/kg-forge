"""Tests for vector-based entity deduplication with ChromaDB."""

import pytest
import tempfile
import shutil
from unittest.mock import Mock
import numpy as np

from kg_forge.pipeline.hooks.deduplication.vector import (
    VectorDeduplicator,
    vector_deduplicate_entities
)
from kg_forge.models.extraction import ExtractedEntity, ExtractionResult
from kg_forge.vector.chroma import ChromaVectorStore


class TestVectorDeduplicator:
    """Test VectorDeduplicator class."""
    
    def test_get_embedding(self):
        """Test embedding generation."""
        dedup = VectorDeduplicator()
        
        embedding = dedup.get_embedding("kubernetes")
        
        # Should return 384-dimensional vector for all-MiniLM-L6-v2
        assert len(embedding) == 384
        assert all(isinstance(x, float) for x in embedding)
    
    def test_dimension_property(self):
        """Test that dimension property is correctly set."""
        dedup = VectorDeduplicator()
        
        assert dedup.dimension == 384
    
    def test_similar_texts_have_high_similarity(self):
        """Test that similar texts produce similar embeddings."""
        dedup = VectorDeduplicator()
        
        emb1 = np.array(dedup.get_embedding("machine learning"))
        emb2 = np.array(dedup.get_embedding("ML algorithms"))
        emb3 = np.array(dedup.get_embedding("database technology"))
        
        # Cosine similarity
        sim_ml = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
        sim_db = np.dot(emb1, emb3) / (np.linalg.norm(emb1) * np.linalg.norm(emb3))
        
        # ML terms should be more similar than ML vs database
        assert sim_ml > sim_db
        assert sim_ml > 0.5  # Reasonably high similarity


class TestVectorDeduplicatorWithChroma:
    """Test VectorDeduplicator with ChromaDB integration."""
    
    @pytest.fixture
    def temp_chroma_dir(self):
        """Create temporary directory for ChromaDB."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def vector_store(self, temp_chroma_dir):
        """Create ChromaVectorStore instance."""
        return ChromaVectorStore(persist_directory=temp_chroma_dir)
    
    def test_find_similar_with_matches(self, vector_store):
        """Test finding similar entities when matches exist."""
        dedup = VectorDeduplicator(vector_store=vector_store)
        
        # Add an existing entity to ChromaDB
        existing_embedding = dedup.get_embedding("kubernetes")
        vector_store.add_entity(
            entity_id="default:Technology:kubernetes",
            entity_type="Technology",
            entity_name="Kubernetes",
            embedding=existing_embedding,
            namespace="default"
        )
        
        # Entity to search for
        entity = ExtractedEntity(
            entity_type="Technology",
            name="k8s",
            properties={"normalized_name": "kubernetes"}
        )
        
        # Find similar
        similar = dedup.find_similar(entity, "default", 0.85)
        
        # Should find the match
        assert similar is not None
        assert similar["name"] == "Kubernetes"
        assert similar["score"] > 0.85
    
    def test_find_similar_no_matches(self, vector_store):
        """Test finding similar entities when no matches exist."""
        dedup = VectorDeduplicator(vector_store=vector_store)
        
        entity = ExtractedEntity(
            entity_type="Technology",
            name="unique_tech",
            properties={"normalized_name": "unique technology"}
        )
        
        # Find similar (empty ChromaDB)
        similar = dedup.find_similar(entity, "default", 0.85)
        
        assert similar is None


class TestVectorDeduplicateEntitiesHook:
    """Test vector_deduplicate_entities hook."""
    
    @pytest.fixture
    def temp_chroma_dir(self):
        """Create temporary directory for ChromaDB."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_empty_extraction_result(self):
        """Test with empty extraction result."""
        context = Mock()
        context.logger = Mock()
        
        extraction_result = ExtractionResult(entities=[])
        
        result = vector_deduplicate_entities(context, extraction_result)
        
        assert result.entities == []
    
    def test_vector_dedup_marks_duplicates(self, temp_chroma_dir):
        """Test that vector dedup marks similar entities."""
        # Mock context
        context = Mock()
        context.logger = Mock()
        context.settings = Mock()
        context.settings.vector = Mock()
        context.settings.vector.threshold = 0.85
        context.settings.vector.model_name = 'all-MiniLM-L6-v2'
        context.settings.vector.persist_dir = temp_chroma_dir
        context.namespace = "default"
        
        # Pre-populate ChromaDB with existing entity
        vector_store = ChromaVectorStore(persist_directory=temp_chroma_dir)
        dedup = VectorDeduplicator(vector_store=vector_store)
        existing_embedding = dedup.get_embedding("kubernetes")
        vector_store.add_entity(
            entity_id="default:Technology:kubernetes",
            entity_type="Technology",
            entity_name="Kubernetes",
            embedding=existing_embedding,
            namespace="default"
        )
        
        # Entity to deduplicate
        entities = [
            ExtractedEntity(
                entity_type="Technology",
                name="k8s",
                properties={'normalized_name': 'kubernetes'}
            )
        ]
        
        extraction_result = ExtractionResult(entities=entities)
        
        # Run hook
        result = vector_deduplicate_entities(context, extraction_result)
        
        # Verify duplicate was marked
        assert hasattr(result.entities[0], 'duplicate_of')
        assert result.entities[0].duplicate_of == 'Kubernetes'
    
    def test_vector_dedup_stores_new_entities(self, temp_chroma_dir):
        """Test that new unique entities are stored in ChromaDB."""
        # Mock context
        context = Mock()
        context.logger = Mock()
        context.settings = Mock()
        context.settings.vector = Mock()
        context.settings.vector.threshold = 0.85
        context.settings.vector.model_name = 'all-MiniLM-L6-v2'
        context.settings.vector.persist_dir = temp_chroma_dir
        context.namespace = "default"
        
        # New unique entity
        entities = [
            ExtractedEntity(
                entity_type="Technology",
                name="Brand New Tech",
                properties={'normalized_name': 'brand new tech'}
            )
        ]
        
        extraction_result = ExtractionResult(entities=entities)
        
        # Run hook
        result = vector_deduplicate_entities(context, extraction_result)
        
        # Verify it was NOT marked as duplicate
        assert not hasattr(result.entities[0], 'duplicate_of') or result.entities[0].duplicate_of is None
        
        # Verify it was stored in ChromaDB
        vector_store = ChromaVectorStore(persist_directory=temp_chroma_dir)
        stats = vector_store.get_stats("default")
        assert stats['entity_count'] == 1
    
    def test_vector_dedup_skips_already_merged_entities(self, temp_chroma_dir):
        """Test that entities already marked as duplicates are skipped."""
        # Mock context
        context = Mock()
        context.logger = Mock()
        context.settings = Mock()
        context.settings.vector = Mock()
        context.settings.vector.threshold = 0.85
        context.settings.vector.model_name = 'all-MiniLM-L6-v2'
        context.settings.vector.persist_dir = temp_chroma_dir
        context.namespace = "default"
        
        # Entity already marked as duplicate by fuzzy matching
        entities = [
            ExtractedEntity(
                entity_type="Technology",
                name="k8s",
                properties={'normalized_name': 'kubernetes'}
            )
        ]
        entities[0].duplicate_of = "Kubernetes"  # Already marked
        
        extraction_result = ExtractionResult(entities=entities)
        
        # Run hook
        result = vector_deduplicate_entities(context, extraction_result)
        
        # Verify ChromaDB was not used (no entities added)
        vector_store = ChromaVectorStore(persist_directory=temp_chroma_dir)
        collections = vector_store.get_stats()
        # Should have no collections (or empty collection)
        assert collections['total_collections'] == 0 or len(collections['collections']) == 0
    
    def test_vector_dedup_handles_model_load_failure(self):
        """Test graceful handling of model loading failures."""
        # Mock context with invalid model
        context = Mock()
        context.logger = Mock()
        context.settings = Mock()
        context.settings.vector = Mock()
        context.settings.vector.threshold = 0.85
        context.settings.vector.model_name = 'invalid-model-name-that-does-not-exist'
        context.settings.vector.persist_dir = './data/chroma_db'
        context.namespace = "default"
        
        entities = [
            ExtractedEntity(
                entity_type="Technology",
                name="Test",
                properties={}
            )
        ]
        
        extraction_result = ExtractionResult(entities=entities)
        
        # Should not crash, just return original result
        result = vector_deduplicate_entities(context, extraction_result)
        
        assert result.entities == entities
        assert context.logger.error.called
    
    def test_vector_dedup_uses_default_config(self, temp_chroma_dir):
        """Test that default config values are used when settings not provided."""
        # Mock context without vector settings
        context = Mock()
        context.logger = Mock()
        context.settings = Mock(spec=[])  # No vector attribute
        context.namespace = "default"
        
        entities = [
            ExtractedEntity(
                entity_type="Technology",
                name="Test",
                properties={}
            )
        ]
        
        extraction_result = ExtractionResult(entities=entities)
        
        # Should use defaults: threshold=0.85, model='all-MiniLM-L6-v2'
        result = vector_deduplicate_entities(context, extraction_result)
        
        # Verify it worked with defaults
        assert len(result.entities) == 1
