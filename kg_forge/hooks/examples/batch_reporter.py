"""
Example process_after_batch hook that reports on processed entities.
"""

import logging
from collections import Counter
from typing import List, Optional

from kg_forge.ingest.hooks import register_after_batch, EntityRecord
from kg_forge.graph.neo4j_client import Neo4jClient
from kg_forge.utils.interactive import InteractiveSession

logger = logging.getLogger(__name__)


@register_after_batch  
def batch_reporter(entities: List[EntityRecord], kg_client: Neo4jClient, 
                  interactive: Optional[InteractiveSession] = None) -> None:
    """
    Example hook that reports statistics on processed entities after batch completion.
    
    Args:
        entities: List of all entities processed in this batch
        kg_client: Neo4j client instance
        interactive: Interactive session (if enabled)
    """
    logger.info(f"Batch reporter processing {len(entities)} entities")
    
    if not entities:
        logger.info("No entities to report on")
        return
    
    # Calculate statistics
    entity_counts = Counter(entity.entity_type for entity in entities)
    namespace_counts = Counter(entity.namespace for entity in entities)
    doc_counts = Counter(entity.doc_id for entity in entities)
    
    confidence_scores = [entity.confidence for entity in entities]
    avg_confidence = sum(confidence_scores) / len(confidence_scores)
    
    # Log summary statistics
    logger.info("=== Batch Processing Summary ===")
    logger.info(f"Total entities processed: {len(entities)}")
    logger.info(f"Average confidence: {avg_confidence:.3f}")
    logger.info(f"Unique documents: {len(doc_counts)}")
    logger.info(f"Namespaces: {list(namespace_counts.keys())}")
    
    logger.info("Entity type distribution:")
    for entity_type, count in entity_counts.most_common():
        logger.info(f"  {entity_type}: {count}")
    
    # Interactive reporting if enabled
    if interactive:
        interactive.print_info("Batch processing completed successfully!")
        
        # Display entity summary
        data = [
            {'Type': entity_type, 'Count': count}
            for entity_type, count in entity_counts.most_common()
        ]
        interactive.display_table("Entity Types Summary", data, max_rows=10)
        
        # Optionally show detailed entity list
        if interactive.confirm("Show detailed entity list?", default=False):
            entity_data = [
                {
                    'Type': entity.entity_type,
                    'Name': entity.name,
                    'Confidence': f"{entity.confidence:.2f}",
                    'Document': entity.doc_id
                }
                for entity in entities[:20]  # Limit to first 20
            ]
            interactive.display_table("Processed Entities", entity_data, max_rows=20)
            
            if len(entities) > 20:
                interactive.print_info(f"... and {len(entities) - 20} more entities")
    
    # Optional: Query Neo4j for additional statistics (if not dry run)
    try:
        with kg_client:
            # Count total entities in database for this namespace
            query = "MATCH (e:Entity {namespace: $namespace}) RETURN count(e) as total"
            result = kg_client.execute_query(query, {"namespace": entities[0].namespace})
            
            if result:
                total_entities = result[0]['total']
                logger.info(f"Total entities in namespace '{entities[0].namespace}': {total_entities}")
                
                if interactive:
                    interactive.print_info(f"Database now contains {total_entities} total entities in this namespace")
                    
    except Exception as e:
        logger.warning(f"Failed to query Neo4j statistics: {e}")
    
    logger.info("Batch reporter completed")