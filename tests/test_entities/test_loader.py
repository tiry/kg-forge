"""Tests for entity definitions loader."""

import pytest
from pathlib import Path
from kg_forge.entities.loader import EntityDefinitionsLoader
from kg_forge.entities.models import EntityDefinition


@pytest.fixture
def temp_entities_dir(tmp_path):
    """Create temporary directory with test entity files."""
    entities_dir = tmp_path / "entities"
    entities_dir.mkdir()
    
    # Create valid entity file
    product_file = entities_dir / "product.md"
    product_file.write_text("""# ID: product
## Name: Product
## Description:
A software product.
## Relations
  - component : uses : used_by
## Examples:
### Example Product
A test product.
""")
    
    # Create another entity file
    component_file = entities_dir / "component.md"
    component_file.write_text("""# ID: component
## Name: Component  
## Description:
A component.
""")
    
    # Create file that should be excluded
    readme = entities_dir / "README.md"
    readme.write_text("This should be excluded")
    
    template = entities_dir / "prompt_template.md"
    template.write_text("Template file")
    
    return entities_dir


def test_loader_initialization(temp_entities_dir):
    """Test loader initialization."""
    loader = EntityDefinitionsLoader(temp_entities_dir)
    assert loader.entities_dir == temp_entities_dir
    assert loader.parser is not None


def test_load_all_success(temp_entities_dir):
    """Test loading all entity definitions."""
    loader = EntityDefinitionsLoader(temp_entities_dir)
    definitions = loader.load_all()
    
    # Should load 2 files (product and component, excluding README and template)
    assert definitions.count() == 2
    assert "product" in definitions.definitions
    assert "component" in definitions.definitions


def test_load_all_excludes_template_files(temp_entities_dir):
    """Test that template and readme files are excluded."""
    loader = EntityDefinitionsLoader(temp_entities_dir)
    definitions = loader.load_all()
    
    # Check excluded files are not loaded
    assert "readme" not in definitions.definitions
    assert "prompt_template" not in definitions.definitions


def test_loader_nonexistent_directory():
    """Test loader with non-existent directory."""
    loader = EntityDefinitionsLoader(Path("/nonexistent/path"))
    
    with pytest.raises(FileNotFoundError, match="Entities directory not found"):
        loader.load_all()


def test_loader_file_instead_of_directory(tmp_path):
    """Test loader with file instead of directory."""
    file_path = tmp_path / "file.txt"
    file_path.write_text("not a directory")
    
    loader = EntityDefinitionsLoader(file_path)
    
    with pytest.raises(NotADirectoryError, match="Not a directory"):
        loader.load_all()


def test_should_process_file_excludes_correctly(temp_entities_dir):
    """Test file filtering logic."""
    loader = EntityDefinitionsLoader(temp_entities_dir)
    
    # Should process
    assert loader._should_process_file(Path("product.md")) is True
    assert loader._should_process_file(Path("component.md")) is True
    
    # Should exclude (case insensitive)
    assert loader._should_process_file(Path("README.md")) is False
    assert loader._should_process_file(Path("readme.md")) is False
    assert loader._should_process_file(Path("prompt_template.md")) is False
    assert loader._should_process_file(Path("Prompt_Template.md")) is False


def test_load_file_success(temp_entities_dir):
    """Test loading a single file."""
    loader = EntityDefinitionsLoader(temp_entities_dir)
    product_file = temp_entities_dir / "product.md"
    
    definition = loader._load_file(product_file)
    
    assert isinstance(definition, EntityDefinition)
    assert definition.entity_type_id == "product"
    assert definition.name == "Product"


def test_load_all_handles_malformed_files(temp_entities_dir):
    """Test that loader continues on error."""
    # Create a malformed file
    bad_file = temp_entities_dir / "bad.md"
    bad_file.write_text("")  # Empty file
    
    loader = EntityDefinitionsLoader(temp_entities_dir)
    
    # Should still load valid files
    definitions = loader.load_all()
    assert definitions.count() >= 2  # At least product and component


def test_load_all_empty_directory(tmp_path):
    """Test loading from empty directory."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    
    loader = EntityDefinitionsLoader(empty_dir)
    definitions = loader.load_all()
    
    assert definitions.count() == 0


def test_loaded_definitions_are_valid(temp_entities_dir):
    """Test that loaded definitions have correct structure."""
    loader = EntityDefinitionsLoader(temp_entities_dir)
    definitions = loader.load_all()
    
    product = definitions.get_by_type("product")
    assert product is not None
    assert product.entity_type_id == "product"
    assert product.name == "Product"
    assert product.description is not None
    assert len(product.relations) == 1
    assert len(product.examples) == 1
    assert product.source_file == "product.md"
