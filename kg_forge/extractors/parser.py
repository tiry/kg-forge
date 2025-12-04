"""
Parser for LLM responses into structured entities.
"""

import json
import re
import logging
from typing import List

from kg_forge.models.extraction import ExtractedEntity
from kg_forge.extractors.base import ParseError

logger = logging.getLogger(__name__)


class ResponseParser:
    """Parse LLM JSON responses into ExtractedEntity objects.
    
    Handles various response formats:
    - Plain JSON
    - JSON wrapped in markdown code blocks
    - Missing confidence scores
    - Unexpected fields
    """
    
    def parse(self, response_text: str) -> List[ExtractedEntity]:
        """Parse LLM response into list of ExtractedEntity objects.
        
        Args:
            response_text: Raw text response from LLM
            
        Returns:
            List of extracted entities
            
        Raises:
            ParseError: If response cannot be parsed
        """
        if not response_text or not response_text.strip():
            logger.warning("Empty response from LLM")
            return []
        
        # Extract JSON from markdown code blocks if present
        json_text = self._extract_json(response_text)
        
        # Parse JSON
        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as e:
            # Log the problematic text for debugging
            preview = json_text[:500] if len(json_text) > 500 else json_text
            logger.error(f"Failed to parse JSON. Error: {e}")
            logger.error(f"Response text (first 500 chars): {preview}")
            if len(json_text) > 500:
                logger.error(f"Full response length: {len(json_text)} characters")
            raise ParseError(f"Invalid JSON in LLM response: {e}")
        
        # Extract entities from parsed data
        return self._extract_entities(data)
    
    def _extract_json(self, text: str) -> str:
        """Extract JSON from text, handling markdown code blocks.
        
        Args:
            text: Text that may contain JSON
            
        Returns:
            Extracted JSON string
        """
        # Try to find JSON in markdown code block
        # Pattern: ```json\n{...}\n``` or ```\n{...}\n```
        code_block_pattern = r'```(?:json)?\s*\n(.*?)\n```'
        matches = re.findall(code_block_pattern, text, re.DOTALL)
        
        if matches:
            logger.debug("Found JSON in markdown code block")
            return matches[0].strip()
        
        # Try to find raw JSON object
        # Look for content between outermost { }
        json_pattern = r'\{.*\}'
        matches = re.findall(json_pattern, text, re.DOTALL)
        
        if matches:
            # Return the longest match (likely the complete JSON)
            return max(matches, key=len)
        
        # Return as-is if no patterns matched
        return text.strip()
    
    def _extract_entities(self, data: dict) -> List[ExtractedEntity]:
        """Extract entities from parsed JSON data.
        
        Args:
            data: Parsed JSON dictionary
            
        Returns:
            List of ExtractedEntity objects
            
        Raises:
            ParseError: If data structure is invalid
        """
        # Expect {"entities": [...]} structure
        if not isinstance(data, dict):
            raise ParseError(f"Expected dict, got {type(data).__name__}")
        
        if "entities" not in data:
            raise ParseError("Response missing 'entities' field")
        
        entities_data = data["entities"]
        if not isinstance(entities_data, list):
            raise ParseError(f"Expected entities to be list, got {type(entities_data).__name__}")
        
        entities = []
        for i, entity_data in enumerate(entities_data):
            try:
                entity = self._parse_entity(entity_data)
                entities.append(entity)
            except Exception as e:
                logger.warning(f"Failed to parse entity at index {i}: {e}")
                # Continue parsing other entities
                continue
        
        logger.info(f"Parsed {len(entities)} entities from response")
        return entities
    
    def _parse_entity(self, data: dict) -> ExtractedEntity:
        """Parse single entity from data.
        
        Args:
            data: Entity dictionary
            
        Returns:
            ExtractedEntity object
            
        Raises:
            ValueError: If required fields are missing
        """
        if not isinstance(data, dict):
            raise ValueError(f"Expected dict, got {type(data).__name__}")
        
        # Get entity_type (required)
        # LLM may use "type", "entity_type", or "type_id"
        entity_type = data.get("type") or data.get("entity_type") or data.get("type_id")
        if not entity_type:
            raise ValueError("Entity missing 'type', 'entity_type', or 'type_id' field")
        
        # Get name (required)
        name = data.get("name")
        if not name:
            raise ValueError("Entity missing 'name' field")
        
        # Get confidence (optional, default 1.0)
        confidence = float(data.get("confidence", 1.0))
        
        # Get any additional properties (including aliases, evidence, etc.)
        properties = {
            k: v for k, v in data.items()
            if k not in ("type", "entity_type", "type_id", "name", "confidence")
        }
        
        return ExtractedEntity(
            entity_type=str(entity_type),
            name=str(name),
            confidence=confidence,
            properties=properties
        )
