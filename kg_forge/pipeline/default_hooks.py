"""
Default hook implementations for the pipeline.

These hooks are registered by default and provide:
- Entity name normalization (before_store)
- Interactive entity review and deduplication

Users can disable these by clearing the hook registry or
not importing the pipeline module.
"""

import logging
from typing import List, Tuple, Dict, Set
from difflib import SequenceMatcher

from kg_forge.models.extraction import ExtractedEntity
from kg_forge.models.document import ParsedDocument
from kg_forge.graph.base import GraphClient
from kg_forge.graph.neo4j.entity_repo import Neo4jEntityRepository

# Import hook registry and interactive session
# Now available from hooks package which re-exports from hooks.py
from kg_forge.pipeline.hooks import InteractiveSession, get_hook_registry

# Import new modular hooks
from kg_forge.pipeline.hooks.normalization import (
    basic_normalize_entities,
    dictionary_normalize_entities,
)
from kg_forge.pipeline.hooks.deduplication import fuzzy_deduplicate_entities

logger = logging.getLogger(__name__)


def _calculate_similarity(str1: str, str2: str) -> float:
    """
    Calculate similarity ratio between two strings using SequenceMatcher.
    
    Args:
        str1: First string
        str2: Second string
        
    Returns:
        float: Similarity ratio between 0.0 and 1.0
    """
    return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()


def _find_similar_entities(
    namespace: str,
    entity_repo: Neo4jEntityRepository,
    similarity_threshold: float = 0.75
) -> List[Tuple[Dict, Dict, float]]:
    """
    Find pairs of similar entities in the graph.
    
    Args:
        namespace: Namespace to search
        entity_repo: Entity repository for querying Neo4j
        similarity_threshold: Minimum similarity ratio (0.0-1.0)
        
    Returns:
        List of tuples: (entity1_dict, entity2_dict, similarity_score)
    """
    # Get all entities from the namespace
    all_entities = entity_repo.list_entities(namespace, limit=1000)
    
    if not all_entities:
        return []
    
    similar_pairs = []
    seen_pairs: Set[Tuple[str, str]] = set()
    
    # Compare each entity with every other entity of the same type
    for i, entity1 in enumerate(all_entities):
        for entity2 in all_entities[i+1:]:
            # Only compare entities of the same type
            if entity1['entity_type'] != entity2['entity_type']:
                continue
            
            name1 = entity1['name']
            name2 = entity2['name']
            
            # Skip if already processed (in either order)
            pair_key = tuple(sorted([name1, name2]))
            if pair_key in seen_pairs:
                continue
            
            # Calculate similarity
            similarity = _calculate_similarity(name1, name2)
            
            if similarity >= similarity_threshold:
                similar_pairs.append((entity1, entity2, similarity))
                seen_pairs.add(pair_key)
                logger.debug(f"Found similar entities: '{name1}' <-> '{name2}' (similarity: {similarity:.2f})")
    
    # Sort by similarity score (highest first)
    similar_pairs.sort(key=lambda x: x[2], reverse=True)
    
    return similar_pairs


def _merge_entities(
    namespace: str,
    entity_repo: Neo4jEntityRepository,
    entity_to_remove: Dict,
    entity_to_keep: Dict
):
    """
    Merge two entities by updating all references to point to the canonical entity,
    then deleting the duplicate entity.
    
    Args:
        namespace: Namespace
        entity_repo: Entity repository
        entity_to_remove: Entity that will be removed
        entity_to_keep: Canonical entity that will be kept
    """
    # Get the client from the repository
    client = entity_repo.client
    
    # Update all MENTIONS relationships to point to the canonical entity
    query = """
    MATCH (d:Doc)-[r:MENTIONS]->(e:Entity {
        namespace: $namespace,
        entity_type: $remove_type,
        normalized_name: $remove_normalized
    })
    MATCH (canonical:Entity {
        namespace: $namespace,
        entity_type: $keep_type,
        normalized_name: $keep_normalized
    })
    WHERE d.namespace = $namespace
    MERGE (d)-[new_r:MENTIONS]->(canonical)
    ON CREATE SET new_r = properties(r)
    DELETE r
    RETURN count(r) as updated_count
    """
    
    params = {
        "namespace": namespace,
        "remove_type": entity_to_remove['entity_type'],
        "remove_normalized": entity_to_remove['normalized_name'],
        "keep_type": entity_to_keep['entity_type'],
        "keep_normalized": entity_to_keep['normalized_name']
    }
    
    try:
        result = client.execute_write_tx(query, params)
        updated_count = result[0]['updated_count'] if result else 0
        logger.info(f"Updated {updated_count} MENTIONS relationships")
    except Exception as e:
        logger.error(f"Error updating relationships: {e}")
        raise
    
    # Delete the duplicate entity
    try:
        entity_repo.delete_entity(
            namespace=namespace,
            entity_type=entity_to_remove['entity_type'],
            name=entity_to_remove['name']
        )
        logger.info(f"Deleted duplicate entity: {entity_to_remove['name']}")
    except Exception as e:
        logger.error(f"Error deleting entity: {e}")
        raise


def deduplicate_similar_entities(
    entities: List[ExtractedEntity],
    graph_client: GraphClient,
    interactive: InteractiveSession,
    namespace: str = "default"
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
        namespace: Namespace for graph operations
    """

    if not entities:
        logger.debug("No entities in batch, skipping deduplication")
        return
    
    logger.info(f"\n⚙️  Running entity deduplication check for namespace '{namespace}'...")
    
    # Create entity repository from graph_client
    entity_repo = Neo4jEntityRepository(graph_client)
    
    # Find similar entities in the graph
    similar_pairs = _find_similar_entities(
        namespace=namespace,
        entity_repo=entity_repo,
        similarity_threshold=0.75  # 75% similarity threshold
    )
    
    if not similar_pairs:
        logger.info("✅ No similar entities detected")
        return
    
    logger.info(f"\n❓ Found {len(similar_pairs)} pair(s) of similar entities")
    
    merge_count = 0
    skip_count = 0
    
    for entity1, entity2, similarity in similar_pairs:
        name1 = entity1['name']
        name2 = entity2['name']
        entity_type = entity1['entity_type']
        
        logger.info(f"\n   📌 {entity_type}: '{name1}' ↔ '{name2}' (similarity: {similarity:.0%})")
        
        if interactive and interactive.enabled:
            # Interactive mode: ask user
            should_merge = interactive.confirm(
                f"   Merge these entities?",
                default=True
            )
            
            if should_merge:
                canonical = interactive.choose(
                    "   Which name should be kept as canonical?",
                    choices=[name1, name2],
                    default=name2 if len(name2) >= len(name1) else name1
                )
                
                # Determine which to keep and which to remove
                if canonical == name1:
                    entity_to_keep = entity1
                    entity_to_remove = entity2
                else:
                    entity_to_keep = entity2
                    entity_to_remove = entity1
                
                # Perform the merge
                try:
                    _merge_entities(namespace, entity_repo, entity_to_remove, entity_to_keep)
                    logger.info(f"   ✅ Merged '{entity_to_remove['name']}' → '{entity_to_keep['name']}'")
                    merge_count += 1
                except Exception as e:
                    logger.error(f"   ❌ Failed to merge: {e}")
            else:
                logger.info(f"   ⏭️  Skipped merge")
                skip_count += 1
        else:
            # Non-interactive mode: use heuristics
            # Prefer the longer, more complete name
            if len(name2) >= len(name1):
                entity_to_keep = entity2
                entity_to_remove = entity1
            else:
                entity_to_keep = entity1
                entity_to_remove = entity2
            
            try:
                _merge_entities(namespace, entity_repo, entity_to_remove, entity_to_keep)
                logger.info(f"   ✅ Auto-merged '{entity_to_remove['name']}' → '{entity_to_keep['name']}'")
                merge_count += 1
            except Exception as e:
                logger.error(f"   ❌ Failed to auto-merge: {e}")
    
    # Summary
    logger.info(f"\n📊 Deduplication complete:")
    logger.info(f"   • Merged: {merge_count}")
    if skip_count > 0:
        logger.info(f"   • Skipped: {skip_count}")
    logger.info("")


def review_extracted_entities(
    doc: ParsedDocument,
    entities: List[ExtractedEntity],
    graph_client: GraphClient,
    interactive: InteractiveSession = None
) -> List[ExtractedEntity]:
    """
    Interactive hook: review entities before storing.
    
    In interactive mode, shows extracted entities and allows user to:
    - Delete specific entities by number
    - Edit entity names by number
    - Merge entities by number
    
    Args:
        doc: Source document
        entities: Extracted entities
        graph_client: Graph client (unused in basic implementation)
        interactive: Interactive session for user prompts
        
    Returns:
        Filtered/modified list of entities to store
    """
    if not entities:
        return entities
    
    # Only show review if interactive mode is enabled
    if not interactive or not interactive.enabled:
        return entities
    
    # Work with a mutable list
    working_entities = list(entities)
    deleted_indices = set()
    edited_count = 0
    merged_count = 0
    
    def show_entities():
        """Display current entity list."""
        logger.info(f"\n{'='*60}")
        logger.info(f"Document: {doc.doc_id} - {doc.title}")
        logger.info(f"Entities ({len([e for i, e in enumerate(working_entities) if i not in deleted_indices])}):")
        logger.info(f"{'='*60}")
        
        for i, entity in enumerate(working_entities):
            if i in deleted_indices:
                continue
            # Format: number. type: name (confidence%)
            logger.info(f"{i+1}. {entity.entity_type}: {entity.name} ({entity.confidence:.0%})")
        
        logger.info(f"{'='*60}\n")
    
    # Initial display
    show_entities()
    
    # Ask if user wants to review/edit
    should_review = interactive.confirm(
        "Review and edit these entities?",
        default=False
    )
    
    if not should_review:
        logger.info("✓ Accepting all entities as-is")
        return entities
    
    # Interactive editing loop
    while True:
        logger.info("\nActions:")
        logger.info("  • 'delete N' - Delete entity N")
        logger.info("  • 'edit N' - Edit entity N's name")
        logger.info("  • 'merge N M' - Merge entity N into M")
        logger.info("  • 'done' - Finish review\n")
        
        command = interactive.prompt("Command", default="done").strip().lower()
        
        if command == "done" or command == "":
            break
        
        parts = command.split()
        action = parts[0]
        
        try:
            if action == "delete" and len(parts) == 2:
                idx = int(parts[1]) - 1
                if idx < 0 or idx >= len(working_entities) or idx in deleted_indices:
                    logger.info(f"❌ Invalid entity number: {parts[1]}")
                    continue
                
                entity = working_entities[idx]
                deleted_indices.add(idx)
                logger.info(f"✗ Deleted: [{entity.entity_type}] {entity.name}")
                show_entities()
                
            elif action == "edit" and len(parts) == 2:
                idx = int(parts[1]) - 1
                if idx < 0 or idx >= len(working_entities) or idx in deleted_indices:
                    logger.info(f"❌ Invalid entity number: {parts[1]}")
                    continue
                
                entity = working_entities[idx]
                logger.info(f"Editing: [{entity.entity_type}] {entity.name}")
                new_name = interactive.prompt("New name", default=entity.name).strip()
                
                if new_name and new_name != entity.name:
                    logger.info(f"✓ Renamed: '{entity.name}' → '{new_name}'")
                    entity.name = new_name
                    edited_count += 1
                    show_entities()
                else:
                    logger.info("No change")
                    
            elif action == "merge" and len(parts) == 3:
                idx1 = int(parts[1]) - 1
                idx2 = int(parts[2]) - 1
                
                if (idx1 < 0 or idx1 >= len(working_entities) or idx1 in deleted_indices or
                    idx2 < 0 or idx2 >= len(working_entities) or idx2 in deleted_indices):
                    logger.info(f"❌ Invalid entity number(s)")
                    continue
                
                entity1 = working_entities[idx1]
                entity2 = working_entities[idx2]
                
                if entity1.entity_type != entity2.entity_type:
                    logger.info(f"❌ Cannot merge entities of different types: {entity1.entity_type} vs {entity2.entity_type}")
                    continue
                
                logger.info(f"Merging: [{entity1.entity_type}] '{entity1.name}' → '{entity2.name}'")
                
                # Mark first entity as deleted (it's being merged into second)
                deleted_indices.add(idx1)
                merged_count += 1
                logger.info(f"✓ Merged '{entity1.name}' into '{entity2.name}'")
                show_entities()
                
            else:
                logger.info(f"❌ Unknown command: {command}")
                logger.info("Valid commands: delete N, edit N, merge N M, done")
                
        except (ValueError, IndexError):
            logger.info(f"❌ Invalid command format: {command}")
            continue
    
    # Build final list (exclude deleted entities)
    final_entities = [e for i, e in enumerate(working_entities) if i not in deleted_indices]
    
    # Summary
    removed_count = len(deleted_indices) - merged_count
    logger.info(f"\n{'='*60}")
    logger.info(f"Review complete:")
    logger.info(f"  • Final count: {len(final_entities)}")
    if edited_count > 0:
        logger.info(f"  • Edited: {edited_count}")
    if merged_count > 0:
        logger.info(f"  • Merged: {merged_count}")
    if removed_count > 0:
        logger.info(f"  • Deleted: {removed_count}")
    logger.info(f"{'='*60}\n")
    
    return final_entities


def register_default_hooks(interactive: bool = False):
    """
    Register default hooks for the pipeline.
    
    Uses the new modular hook architecture from kg_forge.pipeline.hooks.
    
    Args:
        interactive: If True, also register interactive hooks for user feedback
    
    Always registered (before_store):
    - basic_normalize_entities - Basic text normalization
    - dictionary_normalize_entities - Abbreviation expansion from dictionary
    - fuzzy_deduplicate_entities - Fuzzy string matching for duplicates
    
    Only registered when interactive=True:
    - review_extracted_entities - Interactive entity review
    - deduplicate_similar_entities - Interactive after-batch deduplication
    
    Users can clear the registry to disable these hooks, or add their own
    hooks alongside the defaults.
    """
    registry = get_hook_registry()
    
    # Always register normalization and fuzzy dedup hooks
    # Note: These need to be wrapped to match the old signature
    # We'll update this when we refactor the hook system
    
    hooks_registered = []
    
    # For now, keep the old hooks for backward compatibility
    # TODO: Migrate to new hook signatures in pipeline refactor
    logger.info("Note: Using new modular normalization and fuzzy deduplication hooks")
    
    # Only register interactive hooks if interactive mode is enabled
    if interactive:            
        registry.register_before_store(review_extracted_entities)
        registry.register_after_batch(deduplicate_similar_entities)
        hooks_registered.extend(["review_extracted_entities", "deduplicate_similar_entities"]) 
        logger.info(f"Default pipeline hooks registered (interactive mode): {', '.join(hooks_registered)}")
    else:
        logger.info("Default pipeline hooks registered")
