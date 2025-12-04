"""
Default hook implementations for the pipeline.

These hooks are registered by default and provide:
- Entity name normalization (before_store)
- Interactive entity deduplication (after_batch)

Users can disable these by clearing the hook registry or
not importing the pipeline module.
"""

import logging
from typing import List

from kg_forge.models.extraction import ExtractedEntity
from kg_forge.models.document import ParsedDocument
from kg_forge.graph.base import GraphClient
from kg_forge.pipeline.hooks import InteractiveSession, get_hook_registry

logger = logging.getLogger(__name__)


def normalize_entity_names(
    doc: ParsedDocument,
    entities: List[ExtractedEntity],
    graph_client: GraphClient
) -> List[ExtractedEntity]:
    """
    Normalize entity names before storing.
    
    Example transformations:
    - "K8S" → "Kubernetes"
    - "AI/ML" → "Artificial Intelligence and Machine Learning"
    - "CICD" → "CI/CD"
    
    Args:
        doc: Source document (not used in basic implementation)
        entities: Extracted entities to normalize
        graph_client: Graph client (for future lookup-based normalization)
        
    Returns:
        Entities with normalized names
    """
    # Define normalization rules
    # Users can extend this by adding their own rules
    abbreviations = {
        "k8s": "Kubernetes",
        "ai/ml": "Artificial Intelligence and Machine Learning",
        "cicd": "CI/CD",
        "ml": "Machine Learning",
        "ai": "Artificial Intelligence",
    }
    
    normalized_count = 0
    
    for entity in entities:
        # Normalize for comparison
        normalized_key = entity.name.lower().strip()
        
        if normalized_key in abbreviations:
            original_name = entity.name
            entity.name = abbreviations[normalized_key]
            logger.info(f"Normalized entity: '{original_name}' → '{entity.name}'")
            normalized_count += 1
    
    if normalized_count > 0:
        logger.info(f"Normalized {normalized_count} entity name(s) in document {doc.doc_id}")
    
    return entities


def deduplicate_similar_entities(
    entities: List[ExtractedEntity],
    graph_client: GraphClient,
    interactive: InteractiveSession
):
    """
    Find and merge similar entities in the graph.
    
    Uses interactive prompts to confirm merges when interactive mode is enabled.
    In non-interactive mode, uses heuristics to auto-merge.
    
    Examples of similar entities that might be detected:
    - "Catherine J." vs "Katherine Jones"
    - "James Earl Jones" vs "James Jones"
    - "K8s" vs "Kubernetes" (if not caught by normalization)
    
    Args:
        entities: Entities from current batch
        graph_client: Graph client for querying existing entities
        interactive: Interactive session for user prompts
    """
    logger.info("Running entity deduplication check...")
    
    # TODO: Implement actual similarity detection
    # This is a placeholder implementation for now
    
    # In a real implementation, you would:
    # 1. Query the graph for existing entities
    # 2. Compare new entities with existing ones using similarity algorithms
    #    (e.g., Levenshtein distance, fuzzy matching, etc.)
    # 3. Present candidates for merging
    
    # Placeholder example of what interactive merging would look like
    similar_pairs = []  # Would be populated by similarity detection
    
    # Example: similar_pairs = find_similar_entities(entities, graph_client)
    
    merge_count = 0
    
    for name1, name2 in similar_pairs:
        if interactive and interactive.enabled:
            # Interactive mode: ask user
            should_merge = interactive.confirm(
                f"Found similar entities: '{name1}' and '{name2}'. Merge them?",
                default=True
            )
            
            if should_merge:
                canonical = interactive.choose(
                    "Which name should be the canonical version?",
                    choices=[name1, name2],
                    default=name2
                )
                logger.info(f"User chose to merge '{name1}' and '{name2}' → '{canonical}'")
                # TODO: Implement actual merge in graph_client
                merge_count += 1
        else:
            # Non-interactive mode: use heuristics
            # For example, prefer the longer name as more complete
            canonical = name2 if len(name2) >= len(name1) else name1
            logger.info(f"Auto-merging '{name1}' and '{name2}' → '{canonical}'")
            # TODO: Implement actual merge in graph_client
            merge_count += 1
    
    if merge_count > 0:
        logger.info(f"Completed entity deduplication: {merge_count} merge(s) performed")
    else:
        logger.debug("No similar entities detected for merging")


def review_extracted_entities(
    doc: ParsedDocument,
    entities: List[ExtractedEntity],
    graph_client: GraphClient
) -> List[ExtractedEntity]:
    """
    Interactive hook: review entities before storing.
    
    In interactive mode, shows extracted entities and allows user to:
    - Accept all entities
    - Skip specific entities
    - Edit entity names
    
    Args:
        doc: Source document
        entities: Extracted entities
        graph_client: Graph client (unused in basic implementation)
        
    Returns:
        Filtered list of entities to store
    """
    from kg_forge.pipeline.hooks import get_hook_registry
    
    # Get the interactive session from the registry
    # Note: This only works if called from orchestrator context
    # For now, we'll just log what we would show
 
    if not entities:
        return entities
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Document: {doc.doc_id} - {doc.title}")
    logger.info(f"Extracted {len(entities)} entities:")
    logger.info(f"{'='*60}")

       
    for i, entity in enumerate(entities, 1):
        logger.info(f"{i}. [{entity.entity_type}] {entity.name}")
        if entity.properties.get('aliases'):
            logger.info(f"   Aliases: {', '.join(entity.properties['aliases'])}")
        logger.info(f"   Confidence: {entity.confidence:.2f}")
    
    logger.info(f"{'='*60}\n")
    
    # In interactive mode, user could filter here
    # For now, just return all entities
    return entities


def register_default_hooks(interactive: bool = False):
    """
    Register default hooks for the pipeline.
    
    Args:
        interactive: If True, also register interactive hooks for user feedback
    
    Always registered:
    - before_store: normalize_entity_names - Normalizes common abbreviations
    
    Only registered when interactive=True:
    - before_store: review_extracted_entities - Shows extracted entities
    - after_batch: deduplicate_similar_entities - Merges similar entities
    
    Users can clear the registry to disable these hooks, or add their own
    hooks alongside the defaults.
    """
    registry = get_hook_registry()
    
    # Always register normalization hook
    registry.register_before_store(normalize_entity_names)
    
    hooks_registered = ["normalize_entity_names"]
    
    # Only register interactive hooks if interactive mode is enabled
    if interactive:
        registry.register_before_store(review_extracted_entities)
        registry.register_after_batch(deduplicate_similar_entities)
        hooks_registered.extend(["review_extracted_entities", "deduplicate_similar_entities"])
        logger.info(f"Default pipeline hooks registered (interactive mode): {', '.join(hooks_registered)}")
    else:
        logger.info(f"Default pipeline hooks registered: {', '.join(hooks_registered)}")
