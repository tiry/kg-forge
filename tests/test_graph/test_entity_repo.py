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


class TestEntityCreate:
    """Test entity creation operations."""
    
    def test_create_entity_success(self, entity_repo, mock_neo4j_client):
        """Test successful entity creation."""
        created_entity = {
            'name': 'Test Product',
            'entity_type': 'Product',
            'namespace': 'default',
            'normalized_name': 'test product',
            'description': 'A test product'
        }
        mock_neo4j_client.execute_write_tx.return_value = [
            {'entity': created_entity, 'status': 'created'}
        ]
        
        result = entity_repo.create_entity(
            "default", "Product", "Test Product",
            description="A test product"
        )
        
        assert result['name'] == 'Test Product'
        assert result['entity_type'] == 'Product'
    
    def test_create_duplicate_entity_raises_error(self, entity_repo, mock_neo4j_client):
        """Test that creating duplicate entity raises error."""
        from kg_forge.graph.exceptions import DuplicateEntityError
        
        mock_neo4j_client.execute_write_tx.return_value = [
            {'entity': None, 'status': 'exists'}
        ]
        
        with pytest.raises(DuplicateEntityError):
            entity_repo.create_entity("default", "Product", "Existing Product")


class TestEntityUpdate:
    """Test entity update operations."""
    
    def test_update_entity_success(self, entity_repo, mock_neo4j_client):
        """Test successful entity update."""
        updated_entity = {
            'name': 'Updated Product',
            'entity_type': 'Product',
            'description': 'Updated description'
        }
        mock_neo4j_client.execute_write_tx.return_value = [{'e': updated_entity}]
        
        result = entity_repo.update_entity(
            "default", "Product", "Updated Product",
            description="Updated description"
        )
        
        assert result['description'] == 'Updated description'
    
    def test_update_nonexistent_entity_raises_error(self, entity_repo, mock_neo4j_client):
        """Test updating non-existent entity raises error."""
        mock_neo4j_client.execute_write_tx.return_value = []
        
        with pytest.raises(EntityNotFoundError):
            entity_repo.update_entity("default", "Product", "NonExistent", description="test")


class TestEntityDelete:
    """Test entity deletion operations."""
    
    def test_delete_entity_success(self, entity_repo, mock_neo4j_client):
        """Test successful entity deletion."""
        mock_neo4j_client.execute_write_tx.return_value = [{'deleted_count': 1}]
        
        result = entity_repo.delete_entity("default", "Product", "Test Product")
        
        assert result is True
    
    def test_delete_nonexistent_entity(self, entity_repo, mock_neo4j_client):
        """Test deleting non-existent entity returns False."""
        mock_neo4j_client.execute_write_tx.return_value = [{'deleted_count': 0}]
        
        result = entity_repo.delete_entity("default", "Product", "NonExistent")
        
        assert result is False


class TestEntityRelationships:
    """Test relationship operations."""
    
    def test_create_relationship_success(self, entity_repo, mock_neo4j_client):
        """Test successful relationship creation."""
        rel_data = {'namespace': 'default', 'type': 'USES'}
        mock_neo4j_client.execute_write_tx.return_value = [
            {'r': rel_data, 'from': {}, 'to': {}}
        ]
        
        result = entity_repo.create_relationship(
            "default", "Team", "Platform Team",
            "Technology", "Python", "USES"
        )
        
        assert result is not None
        assert result['type'] == 'USES'
    
    def test_create_relationship_missing_source(self, entity_repo, mock_neo4j_client):
        """Test creating relationship with missing source entity."""
        mock_neo4j_client.execute_write_tx.return_value = []
        mock_neo4j_client.execute_query.side_effect = [[], []]  # Both entities not found
        
        with pytest.raises(EntityNotFoundError):
            entity_repo.create_relationship(
                "default", "Team", "NonExistent",
                "Technology", "Python", "USES"
            )


class TestEntityErrorHandling:
    """Test error handling in entity operations."""
    
    def test_list_entities_handles_exception(self, entity_repo, mock_neo4j_client):
        """Test that list_entities handles exceptions gracefully."""
        mock_neo4j_client.execute_query.side_effect = Exception("Database error")
        
        result = entity_repo.list_entities("default")
        
        assert result == []
    
    def test_list_entity_types_handles_exception(self, entity_repo, mock_neo4j_client):
        """Test that list_entity_types handles exceptions gracefully."""
        mock_neo4j_client.execute_query.side_effect = Exception("Database error")
        
        result = entity_repo.list_entity_types("default")
        
        assert result == []
    
    def test_get_entity_handles_exception(self, entity_repo, mock_neo4j_client):
        """Test that get_entity handles exceptions gracefully."""
        mock_neo4j_client.execute_query.side_effect = Exception("Database error")
        
        result = entity_repo.get_entity("default", "Product", "Test")
        
        assert result is None
