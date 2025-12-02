"""Tests for prompt template builder."""

import pytest
from pathlib import Path
from kg_forge.entities.template import PromptTemplateBuilder
from kg_forge.entities.models import (
    EntityDefinitions,
    EntityDefinition,
    EntityRelation,
    EntityExample,
)


@pytest.fixture
def sample_definitions():
    """Create sample entity definitions."""
    definitions = EntityDefinitions()
    
    # Add product definition
    definitions.definitions["product"] = EntityDefinition(
        entity_type_id="product",
        name="Product",
        description="A software product.",
        relations=[
            EntityRelation(
                target_entity_type="component",
                forward_label="uses",
                reverse_label="used_by"
            )
        ],
        examples=[
            EntityExample(
                name="Example Product",
                description="Test product description."
            )
        ],
        source_file="product.md"
    )
    
    # Add component definition
    definitions.definitions["component"] = EntityDefinition(
        entity_type_id="component",
        name="Component",
        description="A component.",
        relations=[],
        examples=[],
        source_file="component.md"
    )
    
    return definitions


@pytest.fixture
def template_file(tmp_path):
    """Create a test template file."""
    template = tmp_path / "template.md"
    template.write_text("""# Entity Extraction Template

## Entity Definitions

{{ENTITY_TYPE_DEFINITIONS}}

## Input Text

{{TEXT}}

## Output

Return JSON with extracted entities.
""")
    return template


def test_builder_initialization():
    """Test builder initialization."""
    builder = PromptTemplateBuilder()
    assert builder.ENTITY_DEFINITIONS_PLACEHOLDER == "{{ENTITY_TYPE_DEFINITIONS}}"
    assert builder.TEXT_PLACEHOLDER == "{{TEXT}}"


def test_merge_definitions_success(template_file, sample_definitions):
    """Test merging entity definitions into template."""
    builder = PromptTemplateBuilder()
    
    result = builder.merge_definitions(template_file, sample_definitions)
    
    # Check template structure is preserved
    assert "# Entity Extraction Template" in result
    assert "## Entity Definitions" in result
    assert "## Input Text" in result
    assert "## Output" in result
    
    # Check placeholder was replaced
    assert "{{ENTITY_TYPE_DEFINITIONS}}" not in result
    
    # Check entity definitions are present
    assert "# ID: component" in result
    assert "# ID: product" in result
    assert "## Name: Product" in result
    assert "## Name: Component" in result


def test_merge_definitions_file_not_found(sample_definitions):
    """Test merge with non-existent template file."""
    builder = PromptTemplateBuilder()
    non_existent = Path("/nonexistent/template.md")
    
    with pytest.raises(FileNotFoundError, match="Template file not found"):
        builder.merge_definitions(non_existent, sample_definitions)


def test_merge_definitions_preserves_order(template_file, sample_definitions):
    """Test that definitions are in sorted order."""
    builder = PromptTemplateBuilder()
    result = builder.merge_definitions(template_file, sample_definitions)
    
    # component should come before product (alphabetical)
    component_pos = result.find("# ID: component")
    product_pos = result.find("# ID: product")
    
    assert component_pos < product_pos


def test_prepare_extraction_prompt(template_file, sample_definitions):
    """Test preparing complete extraction prompt."""
    builder = PromptTemplateBuilder()
    input_text = "This is test input text about products."
    
    result = builder.prepare_extraction_prompt(
        template_file,
        sample_definitions,
        input_text
    )
    
    # Check both placeholders were replaced
    assert "{{ENTITY_TYPE_DEFINITIONS}}" not in result
    assert "{{TEXT}}" not in result
    
    # Check content is present
    assert "# ID: product" in result
    assert input_text in result
    assert "## Output" in result


def test_prepare_extraction_prompt_with_special_chars():
    """Test prompt preparation with special characters in text."""
    builder = PromptTemplateBuilder()
    
    # Create minimal template
    template_path = Path("/tmp/test_template.md")
    template_path.write_text("Entities: {{ENTITY_TYPE_DEFINITIONS}}\nText: {{TEXT}}")
    
    definitions = EntityDefinitions()
    definitions.definitions["test"] = EntityDefinition(
        entity_type_id="test",
        name="Test",
        description="Test",
        relations=[],
        examples=[],
        source_file="test.md"
    )
    
    # Text with special characters
    special_text = "Text with $pecial ch@rs & symbols!"
    
    result = builder.prepare_extraction_prompt(
        template_path,
        definitions,
        special_text
    )
    
    assert special_text in result
    assert "# ID: test" in result
    

def test_get_default_template_path_no_arg():
    """Test getting default template path without argument."""
    builder = PromptTemplateBuilder()
    path = builder.get_default_template_path()
    
    assert path.name == "prompt_template.md"
    assert "entities_extract" in str(path)


def test_get_default_template_path_with_custom_dir(tmp_path):
    """Test getting template path with custom directory."""
    builder = PromptTemplateBuilder()
    custom_dir = tmp_path / "custom_entities"
    custom_dir.mkdir()
    
    path = builder.get_default_template_path(custom_dir)
    
    assert path.name == "prompt_template.md"
    assert path.parent == custom_dir


def test_merge_empty_definitions(template_file):
    """Test merging with empty definitions."""
    builder = PromptTemplateBuilder()
    empty_defs = EntityDefinitions()
    
    result = builder.merge_definitions(template_file, empty_defs)
    
    # Template structure should be preserved
    assert "# Entity Extraction Template" in result
    # Placeholder should be replaced (even if with empty content)
    assert "{{ENTITY_TYPE_DEFINITIONS}}" not in result


def test_merged_content_includes_all_fields(template_file, sample_definitions):
    """Test that merged content includes all entity fields."""
    builder = PromptTemplateBuilder()
    result = builder.merge_definitions(template_file, sample_definitions)
    
    # Check product definition fields
    assert "# ID: product" in result
    assert "## Name: Product" in result
    assert "## Description:" in result
    assert "A software product." in result
    assert "## Relations" in result
    assert "component : uses : used_by" in result
    assert "## Examples:" in result
    assert "### Example Product" in result


def test_prepare_extraction_prompt_preserves_template_structure(
    template_file, sample_definitions
):
    """Test that template structure is preserved after both replacements."""
    builder = PromptTemplateBuilder()
    input_text = "Sample input"
    
    result = builder.prepare_extraction_prompt(
        template_file,
        sample_definitions,
        input_text
    )
    
    # Original template sections should still be there
    lines = result.split('\n')
    assert any("# Entity Extraction Template" in line for line in lines)
    assert any("## Entity Definitions" in line for line in lines)
    assert any("## Input Text" in line for line in lines)
    assert any("## Output" in line for line in lines)
    assert any("Return JSON with extracted entities" in line for line in lines)
