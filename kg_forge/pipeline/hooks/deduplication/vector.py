"""Vector-based entity deduplication using BERT embeddings."""

from typing import List, Optional, TYPE_CHECKING

from sentence_transformers import SentenceTransformer

if TYPE_CHECKING:
    from kg_forge.pipeline.orchestrator import PipelineContext
    from kg_forge.models.extraction import Entity, ExtractionResult


class VectorDeduplicator:
    """Deduplicate entities using vector similarity."""
    
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        """
        Initialize with a sentence-transformers model.
        
        Args:
            model_name: HuggingFace model name (default: all-MiniLM-L6-v2)
                       Produces 384-dimensional embeddings
        """
        self.model = SentenceTransformer(model_name)
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
    
    def get_embedding(self, text: str) -> List[float]:
        """
        Generate embedding vector for text.
        
        Args:
            text: Input text to encode
            
        Returns:
            List of floats representing the embedding vector
        """
        return self.model.encode(text, convert_to_tensor=False).tolist()
    
    def find_similar(
        self,
        entity: "Entity",
        entity_repo,
        namespace: str,
        threshold: float = 0.85
    ) -> Optional["Entity"]:
        """
        Find similar entity using vector search in Neo4j.
        
        Args:
            entity: Entity to find matches for
            entity_repo: EntityRepository instance
            namespace: Entity namespace to search
            threshold: Minimum cosine similarity (0-1)
            
        Returns:
            Most similar entity above threshold, or None
        """
        # Generate embedding for current entity
        entity_name = entity.properties.get('normalized_name') or entity.name
        embedding = self.get_embedding(entity_name)
        
        # Search vector index in Neo4j
        similar_entities = entity_repo.vector_search(
            entity_type=entity.entity_type,
            embedding=embedding,
            namespace=namespace,
            limit=5,
            threshold=threshold
        )
        
        # Return best match if found
        return similar_entities[0] if similar_entities else None


def vector_deduplicate_entities(
    context: "PipelineContext",
    extraction_result: "ExtractionResult"
) -> "ExtractionResult":
    """
    Deduplicate entities using vector similarity.
    
    This hook uses BERT embeddings and Neo4j vector index to find
    semantically similar entities. It runs after fuzzy matching and
    only processes entities that weren't already matched.
    
    Configuration:
        settings.pipeline.vector_threshold: float (default: 0.85)
        settings.pipeline.embedding_model: str (default: 'all-MiniLM-L6-v2')
    
    Args:
        context: Pipeline context with logger and settings
        extraction_result: Extraction result containing entities
        
    Returns:
        Modified extraction result with vector duplicates marked
    """
    if not extraction_result.entities:
        return extraction_result
    
    # Get configuration
    threshold = 0.85
    model_name = 'all-MiniLM-L6-v2'
    
    if hasattr(context.settings, 'pipeline'):
        threshold = getattr(context.settings.pipeline, 'vector_threshold', 0.85)
        model_name = getattr(context.settings.pipeline, 'embedding_model', 'all-MiniLM-L6-v2')
    
    # Initialize deduplicator
    try:
        deduplicator = VectorDeduplicator(model_name)
        context.logger.info(f"Using embedding model: {model_name} ({deduplicator.embedding_dim} dimensions)")
    except Exception as e:
        context.logger.error(f"Failed to load embedding model: {e}")
        return extraction_result
    
    # Get entity repository
    entity_repo = context.graph_client.entity_repo
    namespace = context.namespace
    
    duplicate_count = 0
    embedding_count = 0
    
    # Process each entity
    for entity in extraction_result.entities:
        # Skip if already merged by fuzzy matching
        if hasattr(entity, 'duplicate_of') and entity.duplicate_of:
            continue
        
        try:
            # Find similar entity using vector search
            similar = deduplicator.find_similar(
                entity,
                entity_repo,
                namespace,
                threshold
            )
            
            if similar:
                # Mark as duplicate (similar is a dict from vector_search)
                entity.duplicate_of = similar['name']
                entity.duplicate_of_id = similar.get('id')
                duplicate_count += 1
                
                context.logger.info(
                    f"Vector match: '{entity.name}' → '{similar['name']}'"
                )
            else:
                # Store embedding for new unique entities
                entity_name = entity.properties.get('normalized_name') or entity.name
                embedding = deduplicator.get_embedding(entity_name)
                entity.embedding = embedding
                embedding_count += 1
                
        except Exception as e:
            context.logger.warning(
                f"Error in vector dedup for entity '{entity.name}': {e}"
            )
            continue
    
    if duplicate_count > 0 or embedding_count > 0:
        context.logger.info(
            f"Vector dedup: {duplicate_count} duplicates found, "
            f"{embedding_count} new embeddings created (threshold: {threshold})"
        )
    
    return extraction_result
