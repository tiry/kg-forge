"""Tests for vector-based entity deduplication."""

import pytest
from unittest.mock import Mock, MagicMock
import numpy as np

from kg_forge.pipeline.hooks.deduplication.vector import (
    VectorDeduplicator,
    vector_deduplicate_entities
)
from kg_forge.models.extraction import ExtractedEntity, ExtractionResult


class TestVectorDeduplicator:
    """Test VectorDeduplicator class."""
    
    def test_get_embedding(self):
        """Test embedding generation."""
        dedup = VectorDeduplicator()
        
        embedding = dedup.get_embedding("kubernetes")
        
        # Should return 384-dimensional vector for all-MiniLM-L6-v2
        assert len(embedding) == 384
        assert all(isinstance(x, float) for x in embedding)
    
    def test_embedding_dimension_property(self):
        """Test that embedding_dim property is correctly set."""
        dedup = VectorDeduplicator()
        
        assert dedup.embedding_dim == 384
    
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
    
    def test_find_similar_with_matches(self):
        """Test finding similar entities when matches exist."""
        dedup = VectorDeduplicator()
        
        entity = ExtractedEntity(
            entity_type="Technology",
            name="k8s",
            properties={"normalized_name": "kubernetes"}
        )
        
        # Mock entity repo
        mock_repo = Mock()
        existing_entity = {
            "name": "Kubernetes",
            "entity_type": "Technology",
            "similarity_score": 0.92
        }
        mock_repo.vector_search.return_value = [existing_entity]
        
        # Find similar
        similar = dedup.find_similar(entity, mock_repo, "default", 0.85)
        
        assert similar is not None
        assert similar["name"] == "Kubernetes"
        assert similar["similarity_score"] == 0.92
        
        # Verify vector_search was called with correct params
        mock_repo.vector_search.assert_called_once()
        call_kwargs = mock_repo.vector_search.call_args[1]
        assert call_kwargs["entity_type"] == "Technology"
        assert call_kwargs["namespace"] == "default"
        assert call_kwargs["threshold"] == 0.85
        assert call_kwargs["limit"] == 5
        assert len(call_kwargs["embedding"]) == 384
    
    def test_find_similar_no_matches(self):
        """Test finding similar entities when no matches exist."""
        dedup = VectorDeduplicator()
        
        entity = ExtractedEntity(
            entity_type="Technology",
            name="unique_tech",
            properties={"normalized_name": "unique technology"}
        )
        
        # Mock entity repo with no results
        mock_repo = Mock()
        mock_repo.vector_search.return_value = []
        
        # Find similar
        similar = dedup.find_similar(entity, mock_repo, "default", 0.85)
        
        assert similar is None


class TestVectorDeduplicateEntitiesHook:
    """Test vector_deduplicate_entities hook."""
    
    def test_empty_extraction_result(self):
        """Test with empty extraction result."""
        context = Mock()
        context.logger = Mock()
        
        extraction_result = ExtractionResult(entities=[])
        
        result = vector_deduplicate_entities(context, extraction_result)
        
        assert result.entities == []
    
    def test_vector_dedup_marks_duplicates(self):
        """Test that vector dedup marks similar entities."""
        # Mock context
        context = Mock()
        context.logger = Mock()
        context.settings = Mock()
        context.settings.pipeline = Mock()
        context.settings.pipeline.vector_threshold = 0.85
        context.settings.pipeline.embedding_model = 'all-MiniLM-L6-v2'
        context.namespace = "default"
        
        # Mock entity repo
        mock_repo = Mock()
        existing = {
            "name": "Kubernetes",
            "entity_type": "Technology",
            "similarity_score": 0.92,
            "id": "existing-1"
        }
        mock_repo.vector_search.return_value = [existing]
        
        context.graph_client = Mock()
        context.graph_client.entity_repo = mock_repo
        
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
        
        # Verify
        assert hasattr(result.entities[0], 'duplicate_of')
        assert result.entities[0].duplicate_of == 'Kubernetes'
        assert result.entities[0].duplicate_of_id == 'existing-1'
    
    def test_vector_dedup_creates_embeddings_for_new_entities(self):
        """Test that new entities get embeddings created."""
        # Mock context
        context = Mock()
        context.logger = Mock()
        context.settings = Mock()
        context.settings.pipeline = Mock()
        context.settings.pipeline.vector_threshold = 0.85
        context.settings.pipeline.embedding_model = 'all-MiniLM-L6-v2'
        context.namespace = "default"
        
        # Mock entity repo with no matches
        mock_repo = Mock()
        mock_repo.vector_search.return_value = []
        
        context.graph_client = Mock()
        context.graph_client.entity_repo = mock_repo
        
        # New unique entity
        entities = [
            ExtractedEntity(
                entity_type="Technology",
                name="New Tech",
                properties={'normalized_name': 'new tech'}
            )
        ]
        
        extraction_result = ExtractionResult(entities=entities)
        
        # Run hook
        result = vector_deduplicate_entities(context, extraction_result)
        
        # Verify embedding was created
        assert hasattr(result.entities[0], 'embedding')
        assert len(result.entities[0].embedding) == 384
        assert all(isinstance(x, float) for x in result.entities[0].embedding)
    
    def test_vector_dedup_skips_already_merged_entities(self):
        """Test that entities already marked as duplicates are skipped."""
        # Mock context
        context = Mock()
        context.logger = Mock()
        context.settings = Mock()
        context.settings.pipeline = Mock()
        context.settings.pipeline.vector_threshold = 0.85
        context.settings.pipeline.embedding_model = 'all-MiniLM-L6-v2'
        context.namespace = "default"
        
        # Mock entity repo
        mock_repo = Mock()
        context.graph_client = Mock()
        context.graph_client.entity_repo = mock_repo
        
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
        
        # Verify vector_search was NOT called
        mock_repo.vector_search.assert_not_called()
    
    def test_vector_dedup_handles_model_load_failure(self):
        """Test graceful handling of model loading failures."""
        # Mock context with invalid model
        context = Mock()
        context.logger = Mock()
        context.settings = Mock()
        context.settings.pipeline = Mock()
        context.settings.pipeline.vector_threshold = 0.85
        context.settings.pipeline.embedding_model = 'invalid-model-name-that-does-not-exist'
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
    
    def test_vector_dedup_uses_default_config(self):
        """Test that default config values are used when settings not provided."""
        # Mock context without pipeline settings
        context = Mock()
        context.logger = Mock()
        context.settings = Mock(spec=[])  # No pipeline attribute
        context.namespace = "default"
        
        # Mock entity repo
        mock_repo = Mock()
        mock_repo.vector_search.return_value = []
        context.graph_client = Mock()
        context.graph_client.entity_repo = mock_repo
        
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
    
    def test_vector_dedup_handles_search_errors(self):
        """Test that search errors are handled gracefully."""
        # Mock context
        context = Mock()
        context.logger = Mock()
        context.settings = Mock()
        context.settings.pipeline = Mock()
        context.settings.pipeline.vector_threshold = 0.85
        context.settings.pipeline.embedding_model = 'all-MiniLM-L6-v2'
        context.namespace = "default"
        
        # Mock entity repo that raises exception
        mock_repo = Mock()
        mock_repo.vector_search.side_effect = Exception("Neo4j connection error")
        
        context.graph_client = Mock()
        context.graph_client.entity_repo = mock_repo
        
        entities = [
            ExtractedEntity(
                entity_type="Technology",
                name="Test",
                properties={'normalized_name': 'test'}
            )
        ]
        
        extraction_result = ExtractionResult(entities=entities)
        
        # Should handle error and continue
        result = vector_deduplicate_entities(context, extraction_result)
        
        # Entity should still be there (error was caught)
        assert len(result.entities) == 1
        assert context.logger.warning.called
