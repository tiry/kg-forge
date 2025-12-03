"""
Abstract base class for entity extractors.
"""

from abc import ABC, abstractmethod
from kg_forge.models.extraction import ExtractionRequest, ExtractionResult


class ExtractionError(Exception):
    """Base exception for extraction errors."""
    pass


class ConfigurationError(ExtractionError):
    """Configuration error (missing credentials, invalid settings)."""
    pass


class ParseError(ExtractionError):
    """Error parsing LLM response."""
    pass


class APIError(ExtractionError):
    """Error calling LLM API."""
    pass


class EntityExtractor(ABC):
    """Abstract base class for entity extraction from documents.
    
    Implementations should handle:
    - Building prompts from content and entity definitions
    - Calling LLM API
    - Parsing responses into structured entities
    - Error handling and retries
    """
    
    @abstractmethod
    def extract(self, request: ExtractionRequest) -> ExtractionResult:
        """Extract entities from content.
        
        Args:
            request: Extraction request with content and configuration
            
        Returns:
            Extraction result with entities or error information
            
        Raises:
            ExtractionError: On unrecoverable extraction failure
        """
        pass
    
    @abstractmethod
    def get_model_name(self) -> str:
        """Get the model/service name being used.
        
        Returns:
            Model identifier (e.g., 'anthropic/claude-3-haiku', 'anthropic.claude-3-haiku-20240307-v1:0')
        """
        pass
