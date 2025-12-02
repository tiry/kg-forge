"""Pydantic models for entity definitions."""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class EntityRelation(BaseModel):
    """Represents a relation from this entity type to another."""
    
    model_config = ConfigDict(frozen=True)  # Make immutable
    
    target_entity_type: str = Field(..., description="Target entity type (e.g., 'component')")
    forward_label: str = Field(..., description="Forward relation label (e.g., 'uses_component')")
    reverse_label: str = Field(..., description="Reverse relation label (e.g., 'component_used_by_product')")


class EntityExample(BaseModel):
    """Represents an example entity instance."""
    
    model_config = ConfigDict(frozen=True)  # Make immutable
    
    name: str = Field(..., description="Example heading text (e.g., 'Knowledge Discovery (KD)')")
    description: str = Field(..., description="Example description text")


class EntityDefinition(BaseModel):
    """Represents a complete entity type definition."""
    
    entity_type_id: str = Field(..., description="Entity type ID (e.g., 'product')")
    name: Optional[str] = Field(None, description="Human-readable name (e.g., 'Software Product')")
    description: Optional[str] = Field(None, description="Full description text")
    relations: List[EntityRelation] = Field(default_factory=list, description="Relations to other entity types")
    examples: List[EntityExample] = Field(default_factory=list, description="Example instances")
    source_file: str = Field(..., description="Original markdown filename")
    
    def to_markdown(self) -> str:
        """
        Convert entity definition back to markdown format.
        
        This is useful for prompt template merging and export.
        """
        lines = []
        
        # ID
        lines.append(f"# ID: {self.entity_type_id}")
        lines.append("")
        
        # Name
        if self.name:
            lines.append(f"## Name: {self.name}")
            lines.append("")
        
        # Description
        if self.description:
            lines.append("## Description:")
            lines.append(self.description.strip())
            lines.append("")
        
        # Relations
        if self.relations:
            lines.append("## Relations")
            for rel in self.relations:
                lines.append(f"  - {rel.target_entity_type} : {rel.forward_label} : {rel.reverse_label}")
            lines.append("")
        
        # Examples
        if self.examples:
            lines.append("## Examples:")
            lines.append("")
            for example in self.examples:
                lines.append(f"### {example.name}")
                lines.append(example.description.strip())
                lines.append("")
        
        return "\n".join(lines)


class EntityDefinitions(BaseModel):
    """Collection of all entity definitions."""
    
    definitions: Dict[str, EntityDefinition] = Field(
        default_factory=dict,
        description="Entity definitions keyed by entity_type_id"
    )
    
    def get_by_type(self, entity_type_id: str) -> Optional[EntityDefinition]:
        """
        Get definition by entity type ID.
        
        Args:
            entity_type_id: The entity type ID to look up
            
        Returns:
            EntityDefinition if found, None otherwise
        """
        return self.definitions.get(entity_type_id)
    
    def get_all_ids(self) -> List[str]:
        """
        Get list of all entity type IDs.
        
        Returns:
            Sorted list of entity type IDs
        """
        return sorted(self.definitions.keys())
    
    def get_all_markdown(self) -> str:
        """
        Get concatenated markdown of all definitions for prompt template.
        
        Returns:
            Concatenated markdown text
        """
        markdown_parts = []
        
        # Sort by entity_type_id for consistency
        for entity_id in self.get_all_ids():
            definition = self.definitions[entity_id]
            markdown_parts.append(definition.to_markdown())
            markdown_parts.append("---")  # Separator between entities
            markdown_parts.append("")
        
        return "\n".join(markdown_parts)
    
    def count(self) -> int:
        """
        Get total number of entity definitions.
        
        Returns:
            Count of definitions
        """
        return len(self.definitions)
    
    def validate_definitions(self) -> List[str]:
        """
        Validate all definitions and return list of warnings.
        
        Returns:
            List of warning messages (empty if all valid)
        """
        warnings = []
        
        for entity_id, definition in self.definitions.items():
            # Check for missing name
            if not definition.name:
                warnings.append(f"{entity_id}: Missing 'Name' field")
            
            # Check for missing description
            if not definition.description:
                warnings.append(f"{entity_id}: Missing 'Description' field")
            
            # Check for missing relations
            if not definition.relations:
                warnings.append(f"{entity_id}: No relations defined")
            
            # Check for missing examples
            if not definition.examples:
                warnings.append(f"{entity_id}: No examples provided")
        
        return warnings
