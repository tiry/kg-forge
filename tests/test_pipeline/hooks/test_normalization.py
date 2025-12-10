"""Tests for normalization hooks."""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock
import tempfile

from kg_forge.pipeline.hooks.normalization.basic import (
    normalize_text,
    basic_normalize_entities,
)
from kg_forge.pipeline.hooks.normalization.dictionary import (
    DictionaryNormalizer,
    dictionary_normalize_entities,
)
from kg_forge.models.extraction import ExtractedEntity, ExtractionResult


class TestBasicNormalization:
    """Test basic text normalization."""
    
    def test_normalize_text_lowercase(self):
        """Test lowercase conversion."""
        assert normalize_text("UPPERCASE") == "uppercase"
        assert normalize_text("MixedCase") == "mixedcase"
    
    def test_normalize_text_trim(self):
        """Test whitespace trimming."""
        assert normalize_text("  spaces  ") == "spaces"
        assert normalize_text("\t\ntabs\n\t") == "tabs"
    
    def test_normalize_text_special_chars(self):
        """Test special character removal."""
        assert normalize_text("hello@world!") == "hello world"
        assert normalize_text("test#value$") == "test value"
        assert normalize_text("a&b|c") == "a b c"
    
    def test_normalize_text_multiple_spaces(self):
        """Test multiple spaces collapsed to single space."""
        assert normalize_text("too    many     spaces") == "too many spaces"
        assert normalize_text("a  b  c") == "a b c"
    
    def test_normalize_text_empty(self):
        """Test empty string handling."""
        assert normalize_text("") == ""
        assert normalize_text("   ") == ""


class TestBasicNormalizeEntitiesHook:
    """Test basic_normalize_entities hook."""
    
    def test_normalize_entities_basic(self):
        """Test basic entity normalization."""
        # Create mock context
        context = Mock()
        context.logger = Mock()
        context.settings = Mock()
        
        # Create entities with various names
        entities = [
            ExtractedEntity(
                entity_type="Technology",
                name="UPPERCASE"
            ),
            ExtractedEntity(
                entity_type="Product",
                name="  Spaces  "
            ),
            ExtractedEntity(
                entity_type="Component",
                name="Special@Chars!"
            ),
        ]
        
        extraction_result = ExtractionResult(entities=entities)
        
        # Run hook
        result = basic_normalize_entities(context, extraction_result)
        
        # Verify normalization
        assert result.entities[0].name == "uppercase"
        assert result.entities[0].properties.get("normalized_name") == "uppercase"
        
        assert result.entities[1].name == "spaces"
        assert result.entities[1].properties.get("normalized_name") == "spaces"
        
        assert result.entities[2].name == "special chars"
        assert result.entities[2].properties.get("normalized_name") == "special chars"
    
    def test_normalize_entities_empty_list(self):
        """Test with empty entity list."""
        context = Mock()
        context.logger = Mock()
        
        extraction_result = ExtractionResult(entities=[])
        
        result = basic_normalize_entities(context, extraction_result)
        
        assert result.entities == []
    
    def test_normalize_entities_preserves_type(self):
        """Test that entity type is preserved."""
        context = Mock()
        context.logger = Mock()
        context.settings = Mock()
        
        entities = [
            ExtractedEntity(
                entity_type="Technology",
                name="TEST"
            ),
        ]
        
        extraction_result = ExtractionResult(entities=entities)
        result = basic_normalize_entities(context, extraction_result)
        
        assert result.entities[0].entity_type == "Technology"


class TestDictionaryNormalizer:
    """Test DictionaryNormalizer class."""
    
    def test_load_dictionary_valid(self):
        """Test loading a valid dictionary file."""
        # Use test data file
        dict_file = Path(__file__).parent.parent.parent / "test_data" / "normalization" / "test_dict.txt"
        
        normalizer = DictionaryNormalizer(dict_file)
        
        # Check normalized keys are stored
        assert "k8s" in normalizer.dictionary
        assert normalizer.dictionary["k8s"] == "Kubernetes"
        
        assert "ml" in normalizer.dictionary
        assert normalizer.dictionary["ml"] == "Machine Learning"
        
        assert "ai" in normalizer.dictionary
        assert normalizer.dictionary["ai"] == "Artificial Intelligence"
    
    def test_load_dictionary_missing_file(self, tmp_path):
        """Test loading non-existent dictionary file."""
        dict_file = tmp_path / "missing.txt"
        
        normalizer = DictionaryNormalizer(dict_file)
        
        # Should create empty dictionary without error
        assert normalizer.dictionary == {}
    
    def test_normalize_with_dictionary(self, tmp_path):
        """Test normalization using dictionary."""
        dict_file = tmp_path / "test_dict.txt"
        dict_file.write_text("K8S : Kubernetes\nML : Machine Learning\n")
        
        normalizer = DictionaryNormalizer(dict_file)
        
        # Should expand abbreviations
        assert normalizer.normalize("K8S") == "kubernetes"
        assert normalizer.normalize("k8s") == "kubernetes"
        assert normalizer.normalize("ML") == "machine learning"
    
    def test_normalize_with_special_chars(self, tmp_path):
        """Test normalization with special characters."""
        dict_file = tmp_path / "test_dict.txt"
        dict_file.write_text("AI/ML : Artificial Intelligence Machine Learning\n")
        
        normalizer = DictionaryNormalizer(dict_file)
        
        # Should handle special chars in key
        assert normalizer.normalize("AI/ML") == "artificial intelligence machine learning"
        assert normalizer.normalize("ai ml") == "artificial intelligence machine learning"
    
    def test_normalize_unknown_term(self, tmp_path):
        """Test normalization of unknown term."""
        dict_file = tmp_path / "test_dict.txt"
        dict_file.write_text("K8S : Kubernetes\n")
        
        normalizer = DictionaryNormalizer(dict_file)
        
        # Should just apply basic normalization
        assert normalizer.normalize("Unknown") == "unknown"
        assert normalizer.normalize("Some@Thing!") == "some thing"
    
    def test_normalize_empty_string(self, tmp_path):
        """Test normalization of empty string."""
        dict_file = tmp_path / "test_dict.txt"
        dict_file.write_text("K8S : Kubernetes\n")
        
        normalizer = DictionaryNormalizer(dict_file)
        
        assert normalizer.normalize("") == ""
        assert normalizer.normalize("   ") == ""


class TestDictionaryNormalizeEntitiesHook:
    """Test dictionary_normalize_entities hook."""
    
    def test_dictionary_normalize_with_expansions(self, tmp_path):
        """Test entity normalization with dictionary expansions."""
        # Create test dictionary
        dict_file = tmp_path / "test_dict.txt"
        dict_file.write_text(
            "K8S : Kubernetes\n"
            "ML : Machine Learning\n"
            "CI/CD : Continuous Integration Continuous Deployment\n"
        )
        
        # Create mock context with settings
        context = Mock()
        context.logger = Mock()
        context.settings = Mock()
        context.settings.pipeline = Mock()
        context.settings.pipeline.normalization_dict_path = str(dict_file)
        
        # Create entities
        entities = [
            ExtractedEntity(entity_type="Technology", name="K8S"),
            ExtractedEntity(entity_type="Technology", name="ML"),
            ExtractedEntity(entity_type="Tool", name="CI/CD"),
            ExtractedEntity(entity_type="Product", name="Unknown"),
        ]
        
        extraction_result = ExtractionResult(entities=entities)
        
        # Run hook
        result = dictionary_normalize_entities(context, extraction_result)
        
        # Verify expansions
        assert result.entities[0].name == "kubernetes"
        assert result.entities[0].properties.get("normalized_name") == "kubernetes"
        
        assert result.entities[1].name == "machine learning"
        assert result.entities[1].properties.get("normalized_name") == "machine learning"
        
        assert result.entities[2].name == "continuous integration continuous deployment"
        assert result.entities[2].properties.get("normalized_name") == "continuous integration continuous deployment"
        
        # Unknown term should just be normalized
        assert result.entities[3].name == "unknown"
        assert result.entities[3].properties.get("normalized_name") == "unknown"
    
    def test_dictionary_normalize_empty_entities(self, tmp_path):
        """Test with empty entity list."""
        context = Mock()
        context.logger = Mock()
        
        extraction_result = ExtractionResult(entities=[])
        
        result = dictionary_normalize_entities(context, extraction_result)
        
        assert result.entities == []
    
    def test_dictionary_normalize_fallback_to_app_settings(self, tmp_path):
        """Test fallback to app.normalization_dict_path if pipeline not available."""
        # Create test dictionary
        dict_file = tmp_path / "test_dict.txt"
        dict_file.write_text("K8S : Kubernetes\n")
        
        # Create mock context without pipeline settings
        context = Mock()
        context.logger = Mock()
        context.settings = Mock()
        context.settings.app = Mock()
        context.settings.app.normalization_dict_path = str(dict_file)
        # No pipeline attribute
        del context.settings.pipeline
        
        entities = [
            ExtractedEntity(entity_type="Technology", name="K8S"),
        ]
        
        extraction_result = ExtractionResult(entities=entities)
        
        # Should use fallback path
        result = dictionary_normalize_entities(context, extraction_result)
        
        assert result.entities[0].name == "kubernetes"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
