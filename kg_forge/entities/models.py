"""Data models for entity definitions."""

from dataclasses import dataclass, field
from typing import List, Optional
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class RelationDefinition:
    """Schema-level relation between entity types."""
    target_type: str      # Target entity type ID
    to_label: str        # Relation label from source to target  
    from_label: str      # Relation label from target to source
    
    @classmethod
    def parse(cls, relation_line: str) -> Optional['RelationDefinition']:
        """Parse relation from 'TargetType : TO_LABEL : FROM_LABEL' format."""
        # Remove leading dash and whitespace
        line = relation_line.strip().lstrip('-').strip()
        
        # Split by colons and clean up whitespace
        parts = [part.strip() for part in line.split(':')]
        
        if len(parts) != 3:
            logger.warning(f"Invalid relation format: '{relation_line}' - expected 'TargetType : TO_LABEL : FROM_LABEL'")
            return None
            
        target_type, to_label, from_label = parts
        
        if not all([target_type, to_label, from_label]):
            logger.warning(f"Empty fields in relation: '{relation_line}'")
            return None
            
        return cls(
            target_type=target_type,
            to_label=to_label,
            from_label=from_label
        )


@dataclass
class ExampleDefinition:
    """Example entity instance with title and description."""
    title: str           # Example title (from ### heading)
    description: str     # Example body text


@dataclass  
class EntityDefinition:
    """Complete entity type definition from markdown file."""
    id: str                                    # Entity type identifier
    name: Optional[str] = None                 # Human-friendly name
    description: Optional[str] = None          # LLM extraction guidance  
    relations: List[RelationDefinition] = field(default_factory=list)
    examples: List[ExampleDefinition] = field(default_factory=list)
    source_file: Optional[str] = None          # Origin filename
    raw_markdown: Optional[str] = None         # Original markdown content
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "relations": [
                {
                    "target_type": rel.target_type,
                    "to_label": rel.to_label,
                    "from_label": rel.from_label
                } for rel in self.relations
            ],
            "examples": [
                {
                    "title": ex.title,
                    "description": ex.description
                } for ex in self.examples
            ],
            "source_file": self.source_file
        }
