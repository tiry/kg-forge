"""
Fake LLM implementation for testing.
"""

import json
import hashlib
from pathlib import Path
from .client import BaseLLMExtractor
from .exceptions import LLMError


class FakeLLMExtractor(BaseLLMExtractor):
    """Fake LLM extractor that returns deterministic responses for testing."""
    
    def __init__(self, responses_dir: Path = None, fail_mode: str = None):
        """
        Initialize fake LLM extractor.
        
        Args:
            responses_dir: Directory containing canned response files
            fail_mode: Optional failure mode for testing ('parse_error', 'network_error', etc.)
        """
        super().__init__()
        self.responses_dir = responses_dir or Path(__file__).parent.parent.parent / "tests" / "data" / "llm_responses"
        self.fail_mode = fail_mode
        self._call_count = 0
    
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
        """Generate a default response based on prompt analysis."""
        # Simple pattern matching to create realistic responses
        entities = []
        
        # Look for common entity type patterns in the prompt
        if "product" in prompt.lower():
            entities.append({"type_id": "product", "name": "Knowledge Discovery", "confidence": 0.92})
        
        if "engineering_team" in prompt.lower() or "team" in prompt.lower():
            entities.append({"type_id": "engineering_team", "name": "Platform Engineering", "confidence": 0.89})
            
        if "technology" in prompt.lower():
            entities.append({"type_id": "technology", "name": "Python", "confidence": 0.85})
        
        if "component" in prompt.lower():
            entities.append({"type_id": "component", "name": "API Gateway", "confidence": 0.78})
        
        # If no patterns matched, return empty result
        if not entities:
            entities = []
        
        response = {"entities": entities}
        return json.dumps(response, indent=2)
    
    def reset_call_count(self):
        """Reset call counter for testing."""
        self._call_count = 0
    
    @property
    def call_count(self) -> int:
        """Get number of LLM calls made."""
        return self._call_count