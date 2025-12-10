"""Fuzzy string matching for entity deduplication."""

from typing import List, Optional, TYPE_CHECKING
import jellyfish

if TYPE_CHECKING:
    from kg_forge.pipeline.orchestrator import PipelineContext
    from kg_forge.models.extraction import ExtractionResult, Entity


def calculate_similarity(text1: str, text2: str) -> float:
    """
    Calculate similarity score between two text strings using Jaro-Winkler similarity.
    
    Args:
        text1: First text string
        text2: Second text string
        
    Returns:
        Similarity score between 0.0 and 1.0
    """
    if not text1 or not text2:
        return 0.0
    
    # Normalize for comparison
    t1 = text1.lower().strip()
    t2 = text2.lower().strip()
    
    if t1 == t2:
        return 1.0
    
    return jellyfish.jaro_winkler_similarity(t1, t2)


def find_similar_entity(
    entity: "Entity",
    existing_entities: List["Entity"],
    threshold: float = 0.85
) -> Optional["Entity"]:
    """
    Find similar entity in existing list.
    
    Args:
        entity: Entity to match
        existing_entities: List of existing entities to search
        threshold: Minimum similarity score (default: 0.85)
        
    Returns:
        Most similar entity if match found, None otherwise
    """
    best_match = None
    best_score = 0.0
    
    for existing in existing_entities:
        # Only compare same entity types
        if existing.entity_type != entity.entity_type:
            continue
        
        # Skip if same entity
        if hasattr(existing, 'id') and hasattr(entity, 'id'):
            if existing.id == entity.id:
                continue
        
        # Calculate similarity
        # Get normalized names from properties dict if available
        entity_norm = entity.properties.get('normalized_name') or entity.name
        existing_norm = existing.properties.get('normalized_name') or existing.name
        
        score = calculate_similarity(entity_norm, existing_norm)
        
        if score > best_score and score >= threshold:
            best_match = existing
            best_score = score
    
    return best_match if best_score >= threshold else None


def fuzzy_deduplicate_entities(
    context: "PipelineContext",
    extraction_result: "ExtractionResult"
) -> "ExtractionResult":
    """
    Deduplicate entities using fuzzy string matching.
    
    This hook identifies similar entity names using the Jaro-Winkler
    similarity algorithm. When a match is found (score >= threshold),
    the entity is marked as a duplicate.
    
    Note: This hook marks duplicates but does not merge them. The actual
    merge operation happens during storage in the graph.
    
    Configuration:
        settings.pipeline.fuzzy_threshold: float (default: 0.85)
    
    Args:
        context: Pipeline context with logger and settings
        extraction_result: Extraction result containing entities
        
    Returns:
        Modified extraction result with duplicates marked
    """
    if not extraction_result.entities:
        return extraction_result
    
    # Get threshold from settings
    threshold = 0.85
    if hasattr(context.settings, 'pipeline'):
        threshold = getattr(context.settings.pipeline, 'fuzzy_threshold', 0.85)
    
    # Get existing entities from graph for this namespace
    try:
        entity_repo = context.graph_client.entity_repo
        namespace = context.namespace
        
        # Group entities by type for efficient comparison
        from collections import defaultdict
        entities_by_type = defaultdict(list)
        
        for entity in extraction_result.entities:
            entities_by_type[entity.entity_type].append(entity)
        
        duplicate_count = 0
        
        # Process each entity type separately
        for entity_type, entities in entities_by_type.items():
            # Get existing entities of this type from graph
            try:
                existing = entity_repo.list_entities(
                    namespace=namespace,
                    entity_type=entity_type
                )
                
                if not existing:
                    continue
                
                context.logger.debug(
                    f"Checking {len(entities)} {entity_type} entities "
                    f"against {len(existing)} existing"
                )
                
                # Find duplicates
                for entity in entities:
                    match = find_similar_entity(entity, existing, threshold)
                    
                    if match:
                        # Mark as duplicate
                        entity.duplicate_of = match.name
                        entity.duplicate_of_id = getattr(match, 'id', None)
                        duplicate_count += 1
                        
                        context.logger.info(
                            f"Fuzzy match: '{entity.name}' → '{match.name}' "
                            f"(similarity: {calculate_similarity(entity.name, match.name):.2f})"
                        )
            
            except Exception as e:
                context.logger.warning(
                    f"Error querying existing {entity_type} entities: {e}"
                )
                continue
        
        if duplicate_count > 0:
            context.logger.info(
                f"Found {duplicate_count} fuzzy duplicates (threshold: {threshold})"
            )
    
    except Exception as e:
        context.logger.error(f"Error in fuzzy deduplication: {e}")
    
    return extraction_result
