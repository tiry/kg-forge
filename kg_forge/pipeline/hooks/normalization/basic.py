"""Basic text normalization for entity names."""

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kg_forge.pipeline.orchestrator import PipelineContext
    from kg_forge.models.extraction import ExtractionResult


def normalize_text(text: str) -> str:
    """
    Apply basic text normalization.
    
    Transformations applied:
    - Convert to lowercase
    - Remove special characters (keep alphanumeric, spaces, hyphens)
    - Trim leading/trailing whitespace
    - Collapse multiple spaces to single space
    
    Args:
        text: Text to normalize
        
    Returns:
        Normalized text
        
    Examples:
        >>> normalize_text("Knowledge Discovery")
        'knowledge discovery'
        >>> normalize_text("  K8S  (Kubernetes)  ")
        'k8s kubernetes'
        >>> normalize_text("AI/ML Domain")
        'aiml domain'
    """
    if not text:
        return ""
    
    # Lowercase
    text = text.lower()
    
    # Remove special characters (keep alphanumeric, space, hyphen)
    text = re.sub(r'[^a-z0-9\s-]', ' ', text)
    
    # Trim and collapse spaces
    text = ' '.join(text.split())
    
    return text


def basic_normalize_entities(
    context: "PipelineContext",
    extraction_result: "ExtractionResult"
) -> "ExtractionResult":
    """
    Normalize entity names using basic text cleaning.
    
    This hook applies standard text normalization to entity names:
    - Lowercase conversion
    - Special character removal
    - Whitespace trimming and collapsing
    
    The original name is preserved in the Entity object, and the
    normalized version is stored in the normalized_name field.
    
    Args:
        context: Pipeline context with logger and settings
        extraction_result: Extraction result containing entities
        
    Returns:
        Modified extraction result with normalized entity names
    """
    if not extraction_result.entities:
        return extraction_result
    
    normalized_count = 0
    
    for entity in extraction_result.entities:
        original_name = entity.name
        normalized = normalize_text(original_name)
        
        # Update the entity name and store normalized version in properties
        entity.name = normalized
        entity.properties['normalized_name'] = normalized
        
        # Track changes
        if original_name != normalized:
            normalized_count += 1
            context.logger.debug(
                f"Basic normalization: '{original_name}' → '{normalized}'"
            )
    
    if normalized_count > 0:
        context.logger.info(
            f"Basic normalization applied to {normalized_count} entities"
        )
    
    return extraction_result
