"""
Data models for entity extraction.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class ExtractionRequest:
    """Request for entity extraction from content."""
    
    content: str
    """Document text to analyze."""
    
    entity_types: List[str] = field(default_factory=list)
    """Entity types to extract. Empty list means extract all types."""
    
    namespace: str = "default"
    """Namespace for context (used in multi-tenant scenarios)."""
    
    max_tokens: int = 4000
    """Maximum tokens for LLM response."""
    
    min_confidence: float = 0.0
    """Minimum confidence threshold (0.0-1.0). Entities below this are filtered out."""


@dataclass
class ExtractedEntity:
    """Single entity extracted from content."""
    
    entity_type: str
    """Entity type (e.g., 'Product', 'Team', 'Technology')."""
    
    name: str
    """Entity name (e.g., 'Knowledge Discovery')."""
    
    confidence: float = 1.0
    """Confidence score from 0.0 to 1.0. Default 1.0 if not provided by LLM."""
    
    properties: Dict[str, Any] = field(default_factory=dict)
    """Additional properties extracted for this entity."""
    
    def __post_init__(self) -> None:
        """Validate confidence is in valid range."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")


@dataclass
class ExtractionResult:
    """Result of entity extraction operation."""
    
    entities: List[ExtractedEntity]
    """List of extracted entities."""
    
    raw_response: Optional[str] = None
    """Raw text response from LLM (for debugging)."""
    
    model_name: Optional[str] = None
    """Name of the model used for extraction."""
    
    tokens_used: Optional[int] = None
    """Total tokens used (input + output) for cost tracking."""
    
    extraction_time: Optional[float] = None
    """Time taken for extraction in seconds."""
    
    success: bool = True
    """Whether extraction succeeded."""
    
    error: Optional[str] = None
    """Error message if extraction failed."""
    
    def filter_by_confidence(self, min_confidence: float) -> "ExtractionResult":
        """Return new result with entities filtered by minimum confidence.
        
        Args:
            min_confidence: Minimum confidence threshold (0.0-1.0)
            
        Returns:
            New ExtractionResult with filtered entities
        """
        filtered_entities = [
            entity for entity in self.entities
            if entity.confidence >= min_confidence
        ]
        
        return ExtractionResult(
            entities=filtered_entities,
            raw_response=self.raw_response,
            model_name=self.model_name,
            tokens_used=self.tokens_used,
            extraction_time=self.extraction_time,
            success=self.success,
            error=self.error
        )
    
    def get_entities_by_type(self, entity_type: str) -> List[ExtractedEntity]:
        """Get all entities of a specific type.
        
        Args:
            entity_type: Entity type to filter by
            
        Returns:
            List of entities matching the type
        """
        return [entity for entity in self.entities if entity.entity_type == entity_type]
    
    def get_unique_types(self) -> List[str]:
        """Get list of unique entity types in result.
        
        Returns:
            Sorted list of unique entity types
        """
        return sorted(set(entity.entity_type for entity in self.entities))
