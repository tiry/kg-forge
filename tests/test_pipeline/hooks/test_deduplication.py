"""Tests for deduplication hooks."""

import pytest
from unittest.mock import Mock, MagicMock, patch

from kg_forge.pipeline.hooks.deduplication.fuzzy import (
    calculate_similarity,
    find_similar_entity,
    fuzzy_deduplicate_entities,
)
from kg_forge.models.extraction import ExtractedEntity, ExtractionResult


class TestCalculateSimilarity:
    """Test calculate_similarity function."""
    
    def test_exact_match(self):
        """Test exact string match returns 1.0."""
        assert calculate_similarity("test", "test") == 1.0
        assert calculate_similarity("hello world", "hello world") == 1.0
    
    def test_case_insensitive(self):
        """Test case insensitive matching."""
        assert calculate_similarity("TEST", "test") == 1.0
        assert calculate_similarity("Hello", "HELLO") == 1.0
    
    def test_empty_strings(self):
        """Test empty string handling."""
        assert calculate_similarity("", "") == 0.0
        assert calculate_similarity("test", "") == 0.0
        assert calculate_similarity("", "test") == 0.0
    
    def test_whitespace_differences(self):
        """Test handling of whitespace differences."""
        # These should be normalized before comparison
        score = calculate_similarity("  test  ", "test")
        assert score == 1.0  # Stripped in normalization
    
    @pytest.mark.parametrize("text1,text2,expected_min", [
        ("kubernetes", "k8s", 0.0),  #  Different strings
        ("similar", "similr", 0.8),  # Very similar (missing 'a')
        ("catherine", "katherine", 0.7),  # Similar names
        ("james jones", "james earl jones", 0.7),  # Partial match
    ])
    def test_similarity_scores(self, text1, text2, expected_min):
        """Test similarity calculation with various string pairs."""
        score = calculate_similarity(text1, text2)
        assert score >= expected_min


class TestFindSimilarEntity:
    """Test find_similar_entity function."""
    
    def test_find_exact_match(self):
        """Test finding exact match."""
        entity = ExtractedEntity(
            entity_type="Technology",
            name="kubernetes"
        )
        
        existing = [
            ExtractedEntity(
                entity_type="Technology",
                name="kubernetes"
           )
        ]
        
        match = find_similar_entity(entity, existing, threshold=0.85)
        assert match is not None
        assert match.name == "kubernetes"
    
    def test_no_match_different_type(self):
        """Test that entities of different types don't match."""
        entity = ExtractedEntity(
            entity_type="Technology",
            name="kubernetes"
        )
        
        existing = [
            ExtractedEntity(
                entity_type="Product",  # Different type
                name="kubernetes"
            )
        ]
        
        match = find_similar_entity(entity, existing, threshold=0.85)
        assert match is None
    
    def test_no_match_below_threshold(self):
        """Test that low similarity scores don't match."""
        entity = ExtractedEntity(
            entity_type="Technology",
            name="kubernetes"
        )
        
        existing = [
            ExtractedEntity(
                entity_type="Technology",
                name="completely different"
            )
        ]
        
        match = find_similar_entity(entity, existing, threshold=0.85)
        assert match is None
    
    def test_find_best_match(self):
        """Test finding the best match among multiple candidates."""
        entity = ExtractedEntity(
            entity_type="Technology",
            name="kubernetes",
            properties={"normalized_name": "kubernetes"}
        )
        
        existing = [
            ExtractedEntity(
                entity_type="Technology",
                name="kubernete",  # Close match
                properties={"normalized_name": "kubernete"}
            ),
            ExtractedEntity(
                entity_type="Technology",
                name="kubernetes platform",  # Also similar
                properties={"normalized_name": "kubernetes platform"}
            ),
        ]
        
        # Should find one of them (implementation dependent)
        match = find_similar_entity(entity, existing, threshold=0.80)
        assert match is not None
        assert match.entity_type == "Technology"
    
    def test_empty_existing_list(self):
        """Test with empty existing entities list."""
        entity = ExtractedEntity(
            entity_type="Technology",
            name="kubernetes"
        )
        
        match = find_similar_entity(entity, [], threshold=0.85)
        assert match is None


class TestFuzzyDeduplicateEntitiesHook:
    """Test fuzzy_deduplicate_entities hook."""
    
    def test_deduplicate_with_matches(self):
        """Test deduplication when matches are found."""
        # Create mock context
        context = Mock()
        context.logger = Mock()
        context.settings = Mock()
        context.settings.pipeline = Mock()
        context.settings.pipeline.fuzzy_threshold = 0.85
        context.namespace = "default"
        
        # Create mock graph client and entity repo
        mock_entity_repo = Mock()
        
        # Mock existing entity from graph (as ExtractedEntity)
        existing_entity = ExtractedEntity(
            entity_type="Technology",
            name="Kubernetes",
            properties={'normalized_name': 'kubernetes'}
        )
        existing_entity.id = 'existing-1'  # Add id attribute
        
        mock_entity_repo.list_entities.return_value = [existing_entity]
        
        context.graph_client = Mock()
        context.graph_client.entity_repo = mock_entity_repo
        
        # Create entities to deduplicate
        entities = [
            ExtractedEntity(
                entity_type="Technology",
                name="kubernetes",  # Exact match
                properties={'normalized_name': 'kubernetes'}
            ),
        ]
        
        extraction_result = ExtractionResult(entities=entities)
        
        # Run hook
        result = fuzzy_deduplicate_entities(context, extraction_result)
        
        # Verify deduplication
        assert hasattr(result.entities[0], 'duplicate_of')
        assert result.entities[0].duplicate_of == 'Kubernetes'
        assert result.entities[0].duplicate_of_id == 'existing-1'
    
    def test_deduplicate_no_matches(self):
        """Test deduplication when no matches found."""
        context = Mock()
        context.logger = Mock()
        context.settings = Mock()
        context.settings.pipeline = Mock()
        context.settings.pipeline.fuzzy_threshold = 0.85
        context.namespace = "default"
        
        # Mock entity repo with no similar entities
        mock_entity_repo = Mock()
        mock_entity_repo.list_entities.return_value = []
        
        context.graph_client = Mock()
        context.graph_client.entity_repo = mock_entity_repo
        
        entities = [
            ExtractedEntity(
                entity_type="Technology",
                name="kubernetes"
            ),
        ]
        
        extraction_result = ExtractionResult(entities=entities)
        
        result = fuzzy_deduplicate_entities(context, extraction_result)
        
        # No duplicates should be marked
        assert not hasattr(result.entities[0], 'duplicate_of')
    
    def test_deduplicate_empty_entities(self):
        """Test with empty entity list."""
        context = Mock()
        context.logger = Mock()
        
        extraction_result = ExtractionResult(entities=[])
        
        result = fuzzy_deduplicate_entities(context, extraction_result)
        
        assert result.entities == []
    
    def test_deduplicate_groups_by_type(self):
        """Test that deduplication groups entities by type."""
        context = Mock()
        context.logger = Mock()
        context.settings = Mock()
        context.settings.pipeline = Mock()
        context.settings.pipeline.fuzzy_threshold = 0.85
        context.namespace = "default"
        
        # Mock entity repo
        mock_entity_repo = Mock()
        
        def list_entities_side_effect(namespace, entity_type):
            """Return different results based on entity_type."""
            if entity_type == "Technology":
                return [ExtractedEntity(
                    entity_type='Technology',
                    name='K8S',
                    properties={'normalized_name': 'k8s'}
                )]
            elif entity_type == "Product":
                return [ExtractedEntity(
                    entity_type='Product',
                    name='Docker',
                    properties={'normalized_name': 'docker'}
                )]
            return []
        
        mock_entity_repo.list_entities.side_effect = list_entities_side_effect
        
        context.graph_client = Mock()
        context.graph_client.entity_repo = mock_entity_repo
        
        entities = [
            ExtractedEntity(entity_type="Technology", name="k8s"),
            ExtractedEntity(entity_type="Product", name="docker"),
        ]
        
        extraction_result = ExtractionResult(entities=entities)
        
        result = fuzzy_deduplicate_entities(context, extraction_result)
        
        # Should have called list_entities for each type
        assert mock_entity_repo.list_entities.call_count == 2
    
    def test_deduplicate_handles_exceptions(self):
        """Test that hook handles exceptions gracefully."""
        context = Mock()
        context.logger = Mock()
        context.settings = Mock()
        context.settings.pipeline = Mock()
        context.settings.pipeline.fuzzy_threshold = 0.85
        context.namespace = "default"
        
        # Mock entity repo that raises exception
        mock_entity_repo = Mock()
        mock_entity_repo.list_entities.side_effect = Exception("Database error")
        
        context.graph_client = Mock()
        context.graph_client.entity_repo = mock_entity_repo
        
        entities = [ExtractedEntity(entity_type="Technology", name="test")]
        extraction_result = ExtractionResult(entities=entities)
        
        # Should not raise exception
        result = fuzzy_deduplicate_entities(context, extraction_result)
        
        # Should log error
        assert context.logger.error.called or context.logger.warning.called


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
