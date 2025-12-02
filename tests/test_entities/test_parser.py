"""Tests for entity markdown parser."""

import pytest
from kg_forge.entities.parser import EntityMarkdownParser
from kg_forge.entities.models import EntityRelation, EntityExample


@pytest.fixture
def parser():
    """Create parser instance."""
    return EntityMarkdownParser()


def test_parse_complete_entity(parser):
    """Test parsing entity with all fields."""
    content = """# ID: test_type
## Name: Test Type
## Description:
This is a test description.
It has multiple lines.
## Relations
  - other_type : links_to : linked_by
  - another_type : uses : used_by
## Examples:
### Example 1
This is example 1 description.
### Example 2
This is example 2 description.
"""
    
    result = parser.parse(content, "test.md")
    
    assert result.entity_type_id == "test_type"
    assert result.name == "Test Type"
    assert "test description" in result.description
    assert len(result.relations) == 2
    assert len(result.examples) == 2
    assert result.source_file == "test.md"


def test_parse_minimal_entity(parser):
    """Test parsing entity with only ID (from filename)."""
    content = "Some content without ID heading"
    
    result = parser.parse(content, "minimal.md")
    
    assert result.entity_type_id == "minimal"  # From filename
    assert result.name is None
    assert result.description is None
    assert len(result.relations) == 0
    assert len(result.examples) == 0


def test_extract_id_from_heading(parser):
    """Test ID extraction from markdown."""
    content = "# ID: my_entity\n"
    result = parser._extract_id(content, "fallback")
    assert result == "my_entity"


def test_extract_id_fallback_to_filename(parser):
    """Test ID defaults to filename."""
    content = "No ID here"
    result = parser._extract_id(content, "filename_id")
    assert result == "filename_id"


def test_extract_id_handles_variations(parser):
    """Test ID extraction handles spacing variations."""
    variations = [
        "#ID:product",
        "# ID:product",
        "#  ID  :  product",
        "# id: product",  # Case insensitive
    ]
    
    for content in variations:
        result = parser._extract_id(content, "fallback")
        assert result == "product"


def test_extract_relations(parser):
    """Test relations parsing."""
    content = """## Relations
  - target1 : forward1 : reverse1
  - target2 : forward2 : reverse2
"""
    
    relations = parser._extract_relations(content)
    
    assert len(relations) == 2
    assert relations[0].target_entity_type == "target1"
    assert relations[0].forward_label == "forward1"
    assert relations[0].reverse_label == "reverse1"


def test_extract_examples(parser):
    """Test examples parsing."""
    content = """## Examples:
### Example One
Description for example one.
### Example Two  
Description for example two.
"""
    
    examples = parser._extract_examples(content)
    
    assert len(examples) == 2
    assert examples[0].name == "Example One"
    assert "example one" in examples[0].description
    assert examples[1].name == "Example Two"
