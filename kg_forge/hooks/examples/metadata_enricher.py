"""
Example process_before_store hook that enriches metadata.
"""

import logging
from typing import Dict, Any

from kg_forge.ingest.hooks import register_before_store
from kg_forge.models.document import ParsedDocument
from kg_forge.graph.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)


@register_before_store
def metadata_enricher(content: ParsedDocument, metadata: Dict[str, Any], 
                     kg_client: Neo4jClient) -> Dict[str, Any]:
    """
    Example hook that enriches extraction metadata with additional context.
    
    Args:
        content: Original curated document
        metadata: Extraction metadata from LLM
        kg_client: Neo4j client instance
        
    Returns:
        Enhanced metadata dictionary
    """
    logger.debug(f"Enriching metadata for document: {metadata.get('doc_id', 'unknown')}")
    
    # Add processing timestamp
    import datetime
    metadata['processed_at'] = datetime.datetime.utcnow().isoformat()
    
    # Add document statistics
    metadata['doc_stats'] = {
        'title_length': len(content.title or ''),
        'content_length': len(content.text or ''),
        'link_count': len(content.links),
        'breadcrumb_depth': len(content.breadcrumb) if content.breadcrumb else 0
    }
    
    # Add entity count by type
    entities = metadata.get('entities', [])
    entity_counts = {}
    for entity in entities:
        entity_type = entity.get('type', 'unknown')
        entity_counts[entity_type] = entity_counts.get(entity_type, 0) + 1
    
    metadata['entity_counts_by_type'] = entity_counts
    metadata['total_entities'] = len(entities)
    
    # Add confidence statistics
    if entities:
        confidences = [entity.get('confidence', 0.0) for entity in entities]
        metadata['confidence_stats'] = {
            'min': min(confidences),
            'max': max(confidences),
            'avg': sum(confidences) / len(confidences)
        }
    
    logger.info(f"Enriched metadata with {len(entities)} entities and processing stats")
    
    return metadata