"""
Fake LLM implementation for testing.
"""

import json
import hashlib
from pathlib import Path
from typing import Optional, List, Dict, Any
from .client import BaseLLMExtractor
from .exceptions import LLMError
from ..ontology_manager import get_ontology_manager


class FakeLLMExtractor(BaseLLMExtractor):
    """Fake LLM extractor that returns deterministic responses for testing."""
    
    def __init__(self, responses_dir: Path = None, fail_mode: str = None, ontology_id: Optional[str] = None):
        """
        Initialize fake LLM extractor.
        
        Args:
            responses_dir: Directory containing canned response files
            fail_mode: Optional failure mode for testing ('parse_error', 'network_error', etc.)
            ontology_id: Ontology pack to use for generating fake entities
        """
        super().__init__()
        self.responses_dir = responses_dir or Path(__file__).parent.parent.parent / "tests" / "data" / "llm_responses"
        self.fail_mode = fail_mode
        self.ontology_id = ontology_id
        self.ontology_manager = get_ontology_manager()
        self._call_count = 0
        self._entity_types_cache: Optional[List[str]] = None
    
    def _call_llm(self, prompt: str) -> str:
        """
        Return canned response based on prompt hash.
        
        Args:
            prompt: Input prompt (used to select response)
            
        Returns:
            Deterministic response text
            
        Raises:
            LLMError: If in failure mode
        """
        self._call_count += 1
        
        # Handle failure modes for testing
        if self.fail_mode:
            if self.fail_mode == 'network_error':
                raise LLMError("Simulated network error")
            elif self.fail_mode == 'parse_error':
                return "This is not valid JSON"
            elif self.fail_mode == 'malformed_json':
                return '{"entities": [{"type": "Product", "name": "Test"}'  # Missing closing brackets
        
        # Generate deterministic response based on prompt content
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]
        
        # Try to load specific response file first
        specific_response_file = self.responses_dir / f"{prompt_hash}.json"
        if specific_response_file.exists():
            return specific_response_file.read_text(encoding='utf-8')
        
        # Fall back to default response based on prompt content
        return self._generate_default_response(prompt)
    
    def _generate_default_response(self, prompt: str) -> str:
        """Generate a default response based on prompt analysis and active ontology."""
        # Get entity types from active ontology
        entity_types = self._get_available_entity_types()
        
        entities = []
        
        # Generate fake entities based on available types and prompt content
        for entity_type in entity_types:
            # Check if entity type is mentioned in prompt (case insensitive)
            if entity_type.lower() in prompt.lower():
                fake_entity = self._generate_fake_entity(entity_type)
                if fake_entity:
                    entities.append(fake_entity)
        
        # If no entity types matched, generate a few random ones for testing
        if not entities and entity_types:
            for i, entity_type in enumerate(entity_types[:3]):  # Max 3 random entities
                fake_entity = self._generate_fake_entity(entity_type, confidence=0.7 - i*0.1)
                if fake_entity:
                    entities.append(fake_entity)
        
        response = {"entities": entities}
        return json.dumps(response, indent=2)
    
    def _get_available_entity_types(self) -> List[str]:
        """Get list of available entity types from active ontology."""
        if self._entity_types_cache is None:
            try:
                definitions = self.ontology_manager.get_entity_definitions(self.ontology_id)
                self._entity_types_cache = [d.id for d in definitions]
            except Exception:
                # Fallback to hardcoded types for compatibility
                self._entity_types_cache = ["Product", "Component", "EngineeringTeam", "Technology", "Workstream"]
        
        return self._entity_types_cache
    
    def _generate_fake_entity(self, entity_type: str, confidence: float = 0.85) -> Optional[Dict[str, Any]]:
        """
        Generate a fake entity of the specified type.
        
        Args:
            entity_type: Type of entity to generate
            confidence: Confidence score for the fake entity
            
        Returns:
            Fake entity dictionary or None if type not supported
        """
        # Generic names based on entity type
        fake_names = {
            "Product": ["TestProduct", "SampleProduct", "MockProduct"],
            "Component": ["TestComponent", "SampleComponent", "MockComponent"], 
            "EngineeringTeam": ["TestTeam", "SampleTeam", "MockTeam"],
            "Technology": ["TestTech", "SampleTech", "MockTech"],
            "Workstream": ["TestWorkstream", "SampleWorkstream", "MockWorkstream"],
            "AiMlDomain": ["TestDomain", "SampleDomain", "MockDomain"]
        }
        
        # Use entity type as key, fallback to generic naming
        names = fake_names.get(entity_type, [f"Test{entity_type}", f"Sample{entity_type}", f"Mock{entity_type}"])
        
        # Pick first name for deterministic results
        name = names[0] if names else f"Test{entity_type}"
        
        return {
            "type_id": entity_type.lower().replace(" ", "_"),
            "name": name,
            "confidence": confidence
        }
    
    def reset_call_count(self):
        """Reset call counter for testing."""
        self._call_count = 0
    
    @property
    def call_count(self) -> int:
        """Get number of LLM calls made."""
        return self._call_count