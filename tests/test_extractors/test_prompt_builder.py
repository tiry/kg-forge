"""Tests for prompt builder."""

import pytest
from pathlib import Path

from kg_forge.extractors.prompt_builder import PromptBuilder


class TestPromptBuilder:
    """Test PromptBuilder class."""
    
    def test_initialization_success(self):
        """Test successful initialization with valid entities directory."""
        builder = PromptBuilder(entities_dir=Path("entities_extract"))
        
        assert builder.entities_dir == Path("entities_extract")
        assert builder.template_path == Path("entities_extract/prompt_template.md")
        assert builder.template is not None
        assert len(builder.template) > 0
    
    def test_initialization_missing_template(self, tmp_path):
        """Test initialization fails if template is missing."""
        # Create empty entities directory
        entities_dir = tmp_path / "entities"
        entities_dir.mkdir()
        
        with pytest.raises(FileNotFoundError) as exc_info:
            PromptBuilder(entities_dir=entities_dir)
        
        assert "Template not found" in str(exc_info.value)
    
    def test_build_extraction_prompt_all_types(self):
        """Test building prompt with all entity types."""
        builder = PromptBuilder(entities_dir=Path("entities_extract"))
        
        content = "This is a test document about Knowledge Discovery."
        
        prompt = builder.build_extraction_prompt(content)
        
        # Check prompt includes content
        assert content in prompt
        
        # Check prompt includes placeholders replaced
        assert "{{TEXT}}" not in prompt
        assert "{{ENTITY_TYPE_DEFINITIONS}}" not in prompt
        
        # Check prompt includes entity type information
        assert "product" in prompt.lower() or "Product" in prompt
    
    def test_build_extraction_prompt_specific_types(self):
        """Test building prompt with specific entity types."""
        builder = PromptBuilder(entities_dir=Path("entities_extract"))
        
        content = "Test content"
        entity_types = ["product", "technology"]
        
        prompt = builder.build_extraction_prompt(content, entity_types=entity_types)
        
        assert content in prompt
        # Should include requested types
        assert "product" in prompt.lower()
    
    def test_build_extraction_prompt_truncates_long_content(self):
        """Test that long content is truncated."""
        builder = PromptBuilder(entities_dir=Path("entities_extract"))
        
        # Create content longer than max_content_length
        long_content = "A" * 150000
        max_length = 100000
        
        prompt = builder.build_extraction_prompt(
            long_content,
            max_content_length=max_length
        )
        
        # Prompt should not contain full content
        assert len(prompt) < len(long_content) + 10000  # Allow for template overhead
        assert "[... content truncated ...]" in prompt
    
    def test_build_extraction_prompt_unknown_types(self):
        """Test building prompt with unknown entity types falls back to all."""
        builder = PromptBuilder(entities_dir=Path("entities_extract"))
        
        content = "Test content"
        entity_types = ["unknown_type", "nonexistent"]
        
        # Should not raise error, should fall back to all types
        prompt = builder.build_extraction_prompt(content, entity_types=entity_types)
        
        assert content in prompt
        # Should still have some entity definitions
        assert len(prompt) > len(content)
    
    def test_get_loaded_types(self):
        """Test getting list of loaded entity types."""
        builder = PromptBuilder(entities_dir=Path("entities_extract"))
        
        types = builder.get_loaded_types()
        
        assert isinstance(types, list)
        assert len(types) > 0
        # Should include at least some expected types
        assert any(t in ["product", "technology", "component", "workstream"] for t in types)
    
    def test_build_entity_definitions_formatting(self):
        """Test that entity definitions are properly formatted."""
        builder = PromptBuilder(entities_dir=Path("entities_extract"))
        
        content = "Test"
        prompt = builder.build_extraction_prompt(content)
        
        # Check formatting elements are present
        assert "##" in prompt  # Markdown headers
        assert "**" in prompt  # Bold formatting
        assert "ID" in prompt or "id" in prompt.lower()
    
    def test_template_placeholders_replaced(self):
        """Test that all template placeholders are replaced."""
        builder = PromptBuilder(entities_dir=Path("entities_extract"))
        
        content = "Sample document text"
        prompt = builder.build_extraction_prompt(content)
        
        # No placeholders should remain
        assert "{{" not in prompt
        assert "}}" not in prompt
    
    def test_empty_content_handling(self):
        """Test handling of empty content."""
        builder = PromptBuilder(entities_dir=Path("entities_extract"))
        
        prompt = builder.build_extraction_prompt("")
        
        # Should still generate valid prompt
        assert len(prompt) > 0
        assert "{{TEXT}}" not in prompt
