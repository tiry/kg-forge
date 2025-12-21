"""Tests for response parser."""

import pytest
from pathlib import Path

from kg_forge.extractors.parser import ResponseParser
from kg_forge.extractors.base import ParseError


class TestResponseParser:
    """Test ResponseParser class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = ResponseParser()
        self.test_data_dir = Path(__file__).parent.parent / "test_data" / "llm_responses"
    
    def test_parse_valid_json(self):
        """Test parsing valid JSON response."""
        response = self.test_data_dir / "valid_response.json"
        with open(response, 'r') as f:
            response_text = f.read()
        
        entities, relationships = self.parser.parse(response_text)
        
        assert len(entities) == 3
        assert entities[0].entity_type == "product"
        assert entities[0].name == "Knowledge Discovery"
        assert entities[0].properties.get("aliases") == ["KD"]
        
        assert entities[1].entity_type == "technology"
        assert entities[1].name == "Python"
        
        assert entities[2].entity_type == "engineering_team"
        assert entities[2].name == "Platform Engineering"
    
    def test_parse_markdown_wrapped(self):
        """Test parsing JSON wrapped in markdown code blocks."""
        response = self.test_data_dir / "markdown_wrapped.txt"
        with open(response, 'r') as f:
            response_text = f.read()
        
        entities, relationships = self.parser.parse(response_text)
        
        assert len(entities) == 1
        assert entities[0].entity_type == "product"
        assert entities[0].name == "Content Lake"
    
    def test_parse_missing_confidence(self):
        """Test parsing response without confidence scores."""
        response_text = """
        {
          "entities": [
            {
              "type_id": "product",
              "name": "Test Product"
            }
          ]
        }
        """
        
        entities, relationships = self.parser.parse(response_text)
        
        assert len(entities) == 1
        assert entities[0].confidence == 1.0  # Default value
    
    def test_parse_empty_entities(self):
        """Test parsing response with no entities."""
        response_text = '{"entities": []}'
        
        entities, relationships = self.parser.parse(response_text)
        
        assert len(entities) == 0
    
    def test_parse_empty_string(self):
        """Test parsing empty response."""
        entities, relationships = self.parser.parse("")
        
        assert len(entities) == 0
    
    def test_parse_malformed_json(self):
        """Test parsing malformed JSON raises error."""
        response_text = "{entities: [invalid json}"
        
        with pytest.raises(ParseError) as exc_info:
            self.parser.parse(response_text)
        
        assert "Invalid JSON" in str(exc_info.value)
    
    def test_parse_missing_entities_field(self):
        """Test parsing JSON without 'entities' field."""
        response_text = '{"results": []}'
        
        with pytest.raises(ParseError) as exc_info:
            self.parser.parse(response_text)
        
        assert "missing 'entities' field" in str(exc_info.value)
    
    def test_parse_entities_not_list(self):
        """Test parsing when entities is not a list."""
        response_text = '{"entities": "not a list"}'
        
        with pytest.raises(ParseError) as exc_info:
            self.parser.parse(response_text)
        
        assert "Expected entities to be list" in str(exc_info.value)
    
    def test_parse_entity_missing_type(self):
        """Test parsing entity without type field."""
        response_text = """
        {
          "entities": [
            {
              "name": "Test"
            }
          ]
        }
        """
        
        # Parser should skip invalid entities and continue
        entities, relationships = self.parser.parse(response_text)
        assert len(entities) == 0
    
    def test_parse_entity_missing_name(self):
        """Test parsing entity without name field."""
        response_text = """
        {
          "entities": [
            {
              "type_id": "product"
            }
          ]
        }
        """
        
        # Parser should skip invalid entities
        entities, relationships = self.parser.parse(response_text)
        assert len(entities) == 0
    
    def test_parse_with_additional_properties(self):
        """Test parsing entities with extra properties."""
        response_text = """
        {
          "entities": [
            {
              "type_id": "product",
              "name": "Test Product",
              "description": "A test product",
              "version": "1.0",
              "tags": ["test", "demo"]
            }
          ]
        }
        """
        
        entities, relationships = self.parser.parse(response_text)
        
        assert len(entities) == 1
        assert entities[0].properties.get("description") == "A test product"
        assert entities[0].properties.get("version") == "1.0"
        assert entities[0].properties.get("tags") == ["test", "demo"]
    
    def test_parse_confidence_out_of_range(self):
        """Test parsing entity with invalid confidence value."""
        response_text = """
        {
          "entities": [
            {
              "type_id": "product",
              "name": "Test",
              "confidence": 1.5
            }
          ]
        }
        """
        
        # Parser should skip invalid entities and log warning
        entities, relationships = self.parser.parse(response_text)
        
        # Entity with invalid confidence should be skipped
        assert len(entities) == 0
    
    def test_parse_different_type_field_names(self):
        """Test parsing with different type field names."""
        # Test "type"
        response1 = '{"entities": [{"type": "product", "name": "Test1"}]}'
        entities1, relationships1 = self.parser.parse(response1)
        assert entities1[0].entity_type == "product"
        
        # Test "entity_type"
        response2 = '{"entities": [{"entity_type": "product", "name": "Test2"}]}'
        entities2, relationships2 = self.parser.parse(response2)
        assert entities2[0].entity_type == "product"
        
        # Test "type_id"
        response3 = '{"entities": [{"type_id": "product", "name": "Test3"}]}'
        entities3, relationships3 = self.parser.parse(response3)
        assert entities3[0].entity_type == "product"
