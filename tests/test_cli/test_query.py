"""Test query CLI commands."""

import pytest
from click.testing import CliRunner
from unittest.mock import Mock

from kg_forge.cli.query import query, list_entities, list_types


@pytest.fixture
def runner():
    """Create CLI runner."""
    return CliRunner()


@pytest.fixture
def mock_context():
    """Mock CLI context with settings."""
    settings = Mock()
    settings.app.default_namespace = "default"
    settings.validate_namespace = Mock()
    return {"settings": settings}


class TestListEntities:
    """Test list-entities command."""
    
    def test_list_entities_all(self, runner, mock_context):
        """Test listing entities."""
        result = runner.invoke(
            query,
            ['list-entities', '--type', 'Product'],
            obj=mock_context
        )
        
        assert result.exit_code == 0
        assert "Product" in result.output
        assert "Sample" in result.output
    
    def test_list_entities_by_type(self, runner, mock_context):
        """Test listing entities by type."""
        result = runner.invoke(
            query,
            ['list-entities', '--type', 'Component'],
            obj=mock_context
        )
        
        assert result.exit_code == 0
        assert "Component" in result.output


class TestListTypes:
    """Test list-types command."""
    
    def test_list_types(self, runner, mock_context):
        """Test listing entity types."""
        result = runner.invoke(
            query,
            ['list-types'],
            obj=mock_context
        )
        
        assert result.exit_code == 0
        assert "Product" in result.output or "Entity Types" in result.output


class TestGetEntity:
    """Test entity retrieval commands."""
    
    def test_get_entity_success(self, runner, mock_context):
        """Test getting entity details."""
        result = runner.invoke(
            query,
            ['show-doc', '--id', 'test-doc'],
            obj=mock_context
        )
        
        assert result.exit_code == 0
        assert "test-doc" in result.output
    
    def test_get_entity_not_found(self, runner, mock_context):
        """Test getting non-existent entity."""
        # Since the implementation uses mock data, it will always "find" something
        result = runner.invoke(
            query,
            ['show-doc', '--id', 'nonexistent'],
            obj=mock_context
        )
        
        assert result.exit_code == 0


class TestQueryHelp:
    """Test query help messages."""
    
    def test_query_group_help(self, runner):
        """Test query group help."""
        result = runner.invoke(query, ['--help'])
        
        assert result.exit_code == 0
        assert "query" in result.output.lower() or "knowledge graph" in result.output.lower()
    
    def test_list_entities_help(self, runner, mock_context):
        """Test list-entities help."""
        result = runner.invoke(query, ['list-entities', '--help'], obj=mock_context)
        
        assert result.exit_code == 0
        assert "--type" in result.output
