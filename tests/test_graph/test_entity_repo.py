"""Unit tests for Neo4j entity repository.

These tests use mocks to test the repository logic without requiring a real Neo4j database.
For integration tests with real Neo4j, see test_integration.py.
"""

import pytest
from unittest.mock import Mock
from kg_forge.graph.neo4j.entity_repo import Neo4jEntityRepository
from kg_forge.graph.exceptions import EntityNotFoundError


class TestEntityNormalization:
    """Test entity name normalization."""
    
    def test_normalize_name_removes_parentheses(self, entity_repo):
        """Test that content in parentheses is removed."""
        result = entity_repo.normalize_name("Knowledge Discovery (KD)")
        assert result == "knowledge discovery"
    
    def test_normalize_name_lowercases(self, entity_repo):
        """Test that names are lowercased."""
        result = entity_repo.normalize_name("Platform Engineering")
        assert result == "platform engineering"
    
    def test_normalize_name_collapses_spaces(self, entity_repo):
        """Test that multiple spaces are collapsed."""
        result = entity_repo.normalize_name("AI  ML   Platform")
        assert result == "ai ml platform"
    
    def test_normalize_name_removes_special_chars(self, entity_repo):
        """Test that special characters are removed."""
        result = entity_repo.normalize_name("AI/ML-Platform")
        assert result == "ai ml platform"


class TestEntityList:
    """Test entity listing operations."""
    
    def test_list_entities_by_type(self, entity_repo, mock_neo4j_client):
        """Test listing entities filtered by type."""
        # Mock the client to return sample entities
        mock_neo4j_client.execute_query.return_value = [
            {'e': {'name': 'Product A', 'entity_type': 'Product'}},
            {'e': {'name': 'Product B', 'entity_type': 'Product'}}
        ]
        
        result = entity_repo.list_entities("default", entity_type="Product")
        
        assert len(result) == 2
        assert result[0]['name'] == 'Product A'
        assert result[1]['name'] == 'Product B'
    
    def test_list_entity_types(self, entity_repo, mock_neo4j_client):
        """Test listing all entity types in a namespace."""
        # Mock the client to return distinct types
        mock_neo4j_client.execute_query.return_value = [
            {'entity_type': 'Product'},
            {'entity_type': 'Team'},
            {'entity_type': 'Technology'}
        ]
        
        result = entity_repo.list_entity_types("default")
        
        assert len(result) == 3
        assert 'Product' in result
        assert 'Team' in result
        assert 'Technology' in result


class TestEntityGet:
    """Test entity retrieval operations."""
    
    def test_get_existing_entity(self, entity_repo, mock_neo4j_client, sample_entity):
        """Test getting an entity that exists."""
        mock_neo4j_client.execute_query.return_value = [{'e': sample_entity}]
        
        result = entity_repo.get_entity("default", "Product", "Knowledge Discovery")
        
        assert result is not None
        assert result['name'] == 'Knowledge Discovery'
        assert result['entity_type'] == 'Product'
    
    def test_get_nonexistent_entity(self, entity_repo, mock_neo4j_client):
        """Test getting an entity that doesn't exist."""
        mock_neo4j_client.execute_query.return_value = []
        
        result = entity_repo.get_entity("default", "Product", "NonExistent")
        
        assert result is None


# Note: Full test suite would include tests for:
# - create_entity
# - update_entity
# - delete_entity
# - create_relationship
# - Error handling
# 
# This is a demonstration of the testing approach.
# Complete tests can be added in subsequent iterations.
