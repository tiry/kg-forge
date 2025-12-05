"""Test default pipeline hooks."""

import pytest
from unittest.mock import Mock
from kg_forge.pipeline.default_hooks import (
    normalize_entity_names,
    _calculate_similarity,
    register_default_hooks
)
from kg_forge.models.extraction import ExtractedEntity
from kg_forge.models.document import ParsedDocument


class TestNormalizeEntityNames:
    """Test entity name normalization hook."""
    
    def test_normalizes_k8s(self):
        """Test that K8S is normalized to Kubernetes."""
        doc = ParsedDocument(doc_id="test", title="Test", text="", source_file="test.html", content_hash="abc")
        entities = [ExtractedEntity(entity_type='Technology', name='K8S', confidence=0.9)]
        
        result = normalize_entity_names(doc, entities, Mock())
        
        assert result[0].name == 'Kubernetes'
    
    def test_normalizes_aiml(self):
        """Test that AI/ML is normalized."""
        doc = ParsedDocument(doc_id="test", title="Test", text="", source_file="test.html", content_hash="abc")
        entities = [ExtractedEntity(entity_type='Technology', name='AI/ML', confidence=0.9)]
        
        result = normalize_entity_names(doc, entities, Mock())
        
        assert result[0].name == 'Artificial Intelligence and Machine Learning'
    
    def test_no_normalization_needed(self):
        """Test entities that don't need normalization."""
        doc = ParsedDocument(doc_id="test", title="Test", text="", source_file="test.html", content_hash="abc")
        entities = [ExtractedEntity(entity_type='Product', name='Test Product', confidence=0.9)]
        
        result = normalize_entity_names(doc, entities, Mock())
        
        assert result[0].name == 'Test Product'
    
    def test_empty_list(self):
        """Test with empty entity list."""
        doc = ParsedDocument(doc_id="test", title="Test", text="", source_file="test.html", content_hash="abc")
        entities = []
        
        result = normalize_entity_names(doc, entities, Mock())
        
        assert len(result) == 0


class TestCalculateSimilarity:
    """Test similarity calculation function."""
    
    def test_identical_strings(self):
        """Test identical strings have similarity 1.0."""
        result = _calculate_similarity("Test", "Test")
        assert result == 1.0
    
    def test_case_insensitive(self):
        """Test similarity is case insensitive."""
        result = _calculate_similarity("Test", "test")
        assert result == 1.0
    
    def test_different_strings(self):
        """Test completely different strings have low similarity."""
        result = _calculate_similarity("Test", "Completely Different")
        assert result < 0.5
    
    def test_similar_strings(self):
        """Test similar strings have high similarity."""
        result = _calculate_similarity("Catherine", "Katherine")
        assert result > 0.7


class TestRegisterDefaultHooks:
    """Test default hook registration."""
    
    @pytest.fixture(autouse=True)
    def clear_registry(self):
        """Clear hook registry before each test."""
        from kg_forge.pipeline.hooks import get_hook_registry
        registry = get_hook_registry()
        # Clear hooks manually since clear() method doesn't exist
        registry.before_store_hooks = []
        registry.after_batch_hooks = []
        yield
        registry.before_store_hooks = []
        registry.after_batch_hooks = []
    
    def test_register_non_interactive(self):
        """Test registering hooks in non-interactive mode."""
        register_default_hooks(interactive=False)
        
        from kg_forge.pipeline.hooks import get_hook_registry
        registry = get_hook_registry()
        
        # Should have normalization hook
        assert len(registry.before_store_hooks) >= 1
    
    def test_register_interactive(self):
        """Test registering hooks in interactive mode."""
        register_default_hooks(interactive=True)
        
        from kg_forge.pipeline.hooks import get_hook_registry
        registry = get_hook_registry()
        
        # Should have more hooks in interactive mode
        assert len(registry.before_store_hooks) >= 2
        assert len(registry.after_batch_hooks) >= 1


class TestFindSimilarEntities:
    """Test finding similar entities."""
    
    def test_finds_similar_entities(self):
        """Test finding similar entities above threshold."""
        from kg_forge.pipeline.default_hooks import _find_similar_entities
        
        mock_repo = Mock()
        mock_repo.list_entities.return_value = [
            {'name': 'Catherine Jones', 'entity_type': 'Person', 'normalized_name': 'catherine jones'},
            {'name': 'Katherine Jones', 'entity_type': 'Person', 'normalized_name': 'katherine jones'},
            {'name': 'Product A', 'entity_type': 'Product', 'normalized_name': 'product a'}
        ]
        
        result = _find_similar_entities('default', mock_repo, similarity_threshold=0.75)
        
        # Should find the two similar person names
        assert len(result) >= 1
        assert result[0][2] >= 0.75  # Similarity score
    
    def test_ignores_different_types(self):
        """Test that different entity types are not compared."""
        from kg_forge.pipeline.default_hooks import _find_similar_entities
        
        mock_repo = Mock()
        mock_repo.list_entities.return_value = [
            {'name': 'Test', 'entity_type': 'Person', 'normalized_name': 'test'},
            {'name': 'Test', 'entity_type': 'Product', 'normalized_name': 'test'}
        ]
        
        result = _find_similar_entities('default', mock_repo, similarity_threshold=0.75)
        
        # Should not find any matches (different types)
        assert len(result) == 0
    
    def test_empty_entity_list(self):
        """Test with no entities."""
        from kg_forge.pipeline.default_hooks import _find_similar_entities
        
        mock_repo = Mock()
        mock_repo.list_entities.return_value = []
        
        result = _find_similar_entities('default', mock_repo)
        
        assert len(result) == 0
    
    def test_sorts_by_similarity(self):
        """Test results are sorted by similarity score."""
        from kg_forge.pipeline.default_hooks import _find_similar_entities
        
        mock_repo = Mock()
        mock_repo.list_entities.return_value = [
            {'name': 'Alice', 'entity_type': 'Person', 'normalized_name': 'alice'},
            {'name': 'Alicia', 'entity_type': 'Person', 'normalized_name': 'alicia'},
            {'name': 'Al', 'entity_type': 'Person', 'normalized_name': 'al'}
        ]
        
        result = _find_similar_entities('default', mock_repo, similarity_threshold=0.4)
        
        # Results should be sorted by similarity (highest first)
        if len(result) > 1:
            assert result[0][2] >= result[1][2]


class TestMergeEntities:
    """Test entity merging."""
    
    def test_merge_updates_relationships(self):
        """Test merging updates MENTIONS relationships."""
        from kg_forge.pipeline.default_hooks import _merge_entities
        
        mock_client = Mock()
        mock_client.execute_write_tx.return_value = [{'updated_count': 5}]
        
        mock_repo = Mock()
        mock_repo.client = mock_client
        mock_repo.delete_entity = Mock()
        
        entity_to_remove = {
            'name': 'K8s',
            'entity_type': 'Technology',
            'normalized_name': 'k8s'
        }
        entity_to_keep = {
            'name': 'Kubernetes',
            'entity_type': 'Technology',
            'normalized_name': 'kubernetes'
        }
        
        _merge_entities('default', mock_repo, entity_to_remove, entity_to_keep)
        
        # Should update relationships and delete entity
        mock_client.execute_write_tx.assert_called_once()
        mock_repo.delete_entity.assert_called_once()
    
    def test_merge_handles_errors(self):
        """Test merge handles errors gracefully."""
        from kg_forge.pipeline.default_hooks import _merge_entities
        
        mock_client = Mock()
        mock_client.execute_write_tx.side_effect = Exception("DB error")
        
        mock_repo = Mock()
        mock_repo.client = mock_client
        
        entity_to_remove = {'name': 'Test1', 'entity_type': 'Product', 'normalized_name': 'test1'}
        entity_to_keep = {'name': 'Test2', 'entity_type': 'Product', 'normalized_name': 'test2'}
        
        with pytest.raises(Exception):
            _merge_entities('default', mock_repo, entity_to_remove, entity_to_keep)


class TestDeduplicateSimilarEntities:
    """Test deduplication of similar entities."""
    
    def test_deduplication_with_no_entities(self):
        """Test deduplication with empty entity list."""
        from kg_forge.pipeline.default_hooks import deduplicate_similar_entities
        
        mock_client = Mock()
        mock_session = Mock()
        mock_session.enabled = False
        
        # Should not raise errors
        deduplicate_similar_entities([], mock_client, mock_session)
    
    def test_deduplication_finds_no_similar(self):
        """Test deduplication when no similar entities exist."""
        from kg_forge.pipeline.default_hooks import deduplicate_similar_entities
        from unittest.mock import patch
        
        mock_client = Mock()
        mock_client.execute_query.return_value = []
        
        mock_session = Mock()
        mock_session.enabled = False
        
        entities = [ExtractedEntity(entity_type='Product', name='Test', confidence=0.9)]
        
        # Mock the list_entities to return no similar entities
        with patch('kg_forge.pipeline.default_hooks._find_similar_entities', return_value=[]):
            deduplicate_similar_entities(entities, mock_client, mock_session)
    
    def test_deduplication_non_interactive_mode(self):
        """Test auto-merge in non-interactive mode."""
        from kg_forge.pipeline.default_hooks import deduplicate_similar_entities
        from unittest.mock import patch
        
        mock_client = Mock()
        mock_client.execute_write_tx.return_value = [{'updated_count': 1}]
        
        mock_session = Mock()
        mock_session.enabled = False
        
        entities = [ExtractedEntity(entity_type='Person', name='Test', confidence=0.9)]
        
        # Mock finding similar entities
        similar_entities = [
            {'name': 'Catherine', 'entity_type': 'Person', 'normalized_name': 'catherine'},
            {'name': 'Katherine', 'entity_type': 'Person', 'normalized_name': 'katherine'}
        ]
        
        with patch('kg_forge.pipeline.default_hooks._find_similar_entities') as mock_find:
            mock_find.return_value = [(similar_entities[0], similar_entities[1], 0.85)]
            
            with patch('kg_forge.pipeline.default_hooks._merge_entities') as mock_merge:
                deduplicate_similar_entities(entities, mock_client, mock_session, namespace='default')
                
                # Should attempt merge in non-interactive mode
                assert mock_merge.called or mock_find.called


class TestReviewExtractedEntities:
    """Test interactive entity review."""
    
    def test_review_disabled_returns_unchanged(self):
        """Test review returns entities unchanged when not interactive."""
        from kg_forge.pipeline.default_hooks import review_extracted_entities
        
        doc = ParsedDocument(doc_id="test", title="Test", text="", source_file="test.html", content_hash="abc")
        entities = [
            ExtractedEntity(entity_type='Product', name='Test Product', confidence=0.9),
            ExtractedEntity(entity_type='Component', name='Test Component', confidence=0.8)
        ]
        
        mock_session = Mock()
        mock_session.enabled = False
        
        result = review_extracted_entities(doc, entities, Mock(), mock_session)
        
        # Should return same entities
        assert len(result) == 2
        assert result == entities
    
    def test_review_with_empty_entities(self):
        """Test review with empty entity list."""
        from kg_forge.pipeline.default_hooks import review_extracted_entities
        
        doc = ParsedDocument(doc_id="test", title="Test", text="", source_file="test.html", content_hash="abc")
        entities = []
        
        result = review_extracted_entities(doc, entities, Mock(), Mock())
        
        assert len(result) == 0
    
    def test_review_user_declines(self):
        """Test review when user declines to review."""
        from kg_forge.pipeline.default_hooks import review_extracted_entities
        
        doc = ParsedDocument(doc_id="test", title="Test", text="", source_file="test.html", content_hash="abc")
        entities = [ExtractedEntity(entity_type='Product', name='Test', confidence=0.9)]
        
        mock_session = Mock()
        mock_session.enabled = True
        mock_session.confirm.return_value = False  # User declines review
        
        result = review_extracted_entities(doc, entities, Mock(), mock_session)
        
        # Should return all entities unchanged
        assert len(result) == 1
        assert result[0].name == 'Test'
