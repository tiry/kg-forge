"""
Response parser for LLM extraction results.
"""

import json
from .client import ExtractedEntity, ExtractionResult
from .exceptions import ParseError, ValidationError


class ResponseParser:
    """Parses and validates LLM responses into structured extraction results."""
    
    def _find_json_end(self, json_text: str) -> int:
        """Find the end position of JSON by counting braces/brackets."""
        brace_count = 0
        bracket_count = 0
        in_string = False
        escape_next = False
        
        for i, char in enumerate(json_text):
            if escape_next:
                escape_next = False
                continue
                
            if char == '\\' and in_string:
                escape_next = True
                continue
                
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
                
            if in_string:
                continue
                
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and bracket_count == 0:
                    return i + 1  # Include the closing brace
            elif char == '[':
                bracket_count += 1
            elif char == ']':
                bracket_count -= 1
                if brace_count == 0 and bracket_count == 0:
                    return i + 1  # Include the closing bracket
                    
        return -1  # No proper end found
    
    def parse_extraction_result(self, response_text: str) -> ExtractionResult:
        """
        Parse LLM response into structured ExtractionResult.
        
        Args:
            response_text: Raw response text from LLM
            
        Returns:
            Parsed and validated ExtractionResult
            
        Raises:
            ParseError: If response cannot be parsed as JSON
            ValidationError: If response doesn't match expected schema
        """
        try:
            # Extract JSON from response that might have preamble text
            stripped_text = response_text.strip()
            
            if not stripped_text:
                raise ParseError("Empty response text received")
            
            # Look for JSON starting with { or [
            json_start = -1
            for i, char in enumerate(stripped_text):
                if char in '{[':
                    json_start = i
                    break
            
            if json_start == -1:
                raise ParseError("No JSON found in response (no { or [ found)")
            
            # Find the end of JSON by counting braces/brackets
            json_text = stripped_text[json_start:]
            json_end = self._find_json_end(json_text)
            
            if json_end == -1:
                # Fallback: use the whole remaining text
                json_text = json_text.strip()
            else:
                json_text = json_text[:json_end].strip()
            
            data = json.loads(json_text)
            
            # Validate top-level structure
            if not isinstance(data, dict) or 'entities' not in data:
                raise ValidationError("Response missing 'entities' field")
            
            # Parse entities
            entities = []
            for entity_data in data['entities']:
                entity = self._parse_entity(entity_data)
                entities.append(entity)
            
            return ExtractionResult(entities=entities)
            
        except json.JSONDecodeError as e:
            raise ParseError(f"Invalid JSON response: {e}")
    
    def _parse_entity(self, entity_data: dict) -> ExtractedEntity:
        """
        Parse a single entity from JSON data.
        
        Args:
            entity_data: Dictionary containing entity fields
            
        Returns:
            Parsed ExtractedEntity
            
        Raises:
            ValidationError: If required fields are missing or invalid
        """
        # Validate required fields
        if not isinstance(entity_data, dict):
            raise ValidationError("Entity data must be a dictionary")
            
        if 'type_id' not in entity_data or 'name' not in entity_data:
            raise ValidationError("Entity missing required 'type_id' or 'name' field")
        
        # Validate field types
        entity_type = entity_data['type_id']
        entity_name = entity_data['name']
        
        if not isinstance(entity_type, str) or not entity_type.strip():
            raise ValidationError("Entity 'type' must be a non-empty string")
            
        if not isinstance(entity_name, str) or not entity_name.strip():
            raise ValidationError("Entity 'name' must be a non-empty string")
        
        # Parse optional confidence field
        confidence = entity_data.get('confidence', 1.0)
        if not isinstance(confidence, (int, float)) or not (0.0 <= confidence <= 1.0):
            raise ValidationError("Entity 'confidence' must be a number between 0.0 and 1.0")
        
        return ExtractedEntity(
            type=entity_type.strip(),
            name=entity_name.strip(),
            confidence=float(confidence)
        )