"""Vector-based entity deduplication using BERT embeddings and ChromaDB."""

import logging
from typing import List, Optional, TYPE_CHECKING

from sentence_transformers import SentenceTransformer
from kg_forge.vector.chroma import ChromaVectorStore

if TYPE_CHECKING:
    from kg_forge.pipeline.orchestrator import PipelineContext
    from kg_forge.models.extraction import Entity, ExtractionResult

logger = logging.getLogger(__name__)


class VectorDeduplicator:
    """Deduplicate entities using vector similarity with ChromaDB."""
    
    def __init__(
        self,
        model_name: str = 'all-MiniLM-L6-v2',
        vector_store: Optional[ChromaVectorStore] = None
    ):
        """
        Initialize with a sentence-transformers model and vector store.
        
        Args:
            model_name: HuggingFace model name (default: all-MiniLM-L6-v2)
            vector_store: VectorStore instance (creates new if None)
        """
        self.model = SentenceTransformer(model_name)
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
        self.vector_store = vector_store or ChromaVectorStore()
    
    @property
    def dimension(self) -> int:
        """Get embedding dimensionality."""
        return self.embedding_dim
    
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
        namespace: str,
        threshold: float = 0.85
    ) -> Optional[dict]:
        """
        Find similar entity using ChromaDB vector search.
        
        Args:
            entity: Entity to find matches for
            namespace: Entity namespace to search
            threshold: Minimum cosine similarity (0-1)
            
        Returns:
            Dict with entity info if found, None otherwise
        """
        # Generate embedding for current entity
        entity_name = entity.properties.get('normalized_name') or entity.name
        embedding = self.get_embedding(entity_name)
        
        # Search in ChromaDB
        similar = self.vector_store.search_similar(
            entity_type=entity.entity_type,
            embedding=embedding,
            namespace=namespace,
            limit=1,
            threshold=threshold
        )
        
        # Return best match if found
        if similar:
            entity_id, score, metadata = similar[0]
            return {
                'id': entity_id,
                'name': metadata['entity_name'],
                'score': score
            }
        
        return None


def vector_deduplicate_entities(
    context: "PipelineContext",
    extraction_result: "ExtractionResult"
) -> "ExtractionResult":
    """
    Deduplicate entities using vector similarity and ChromaDB.
    
    This hook uses BERT embeddings and ChromaDB to find semantically 
    similar entities. It runs after fuzzy matching and only processes 
    entities that weren't already matched.
    
    Configuration:
        settings.vector.threshold:  float (default: 0.85)
        settings.vector.model_name: str (default: 'all-MiniLM-L6-v2')
        settings.vector.persist_dir: str (default: './data/chroma_db')
    
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
    persist_dir = './data/chroma_db'
    
    if hasattr(context.settings, 'vector'):
        threshold = getattr(context.settings.vector, 'threshold', 0.85)
        model_name = getattr(context.settings.vector, 'model_name', 'all-MiniLM-L6-v2')
        persist_dir = getattr(context.settings.vector, 'persist_dir', './data/chroma_db')
    
    # Initialize deduplicator with ChromaDB
    try:
        vector_store = ChromaVectorStore(persist_directory=persist_dir)
        deduplicator = VectorDeduplicator(model_name, vector_store)
        context.logger.info(
            f"Vector dedup: {model_name} ({deduplicator.dimension}D) + ChromaDB"
        )
    except Exception as e:
        context.logger.error(f"Failed to initialize vector dedup: {e}")
        return extraction_result
    
    namespace = context.namespace
    duplicate_count = 0
    stored_count = 0
    
    # Process each entity
    for entity in extraction_result.entities:
        # Skip if already merged by fuzzy matching
        if hasattr(entity, 'duplicate_of') and entity.duplicate_of:
            continue
        
        try:
            # Find similar entity in ChromaDB
            similar = deduplicator.find_similar(entity, namespace, threshold)
            
            if similar:
                # Mark as duplicate
                entity.duplicate_of = similar['name']
                entity.duplicate_of_id = similar['id']
                duplicate_count += 1
                
                context.logger.info(
                    f"Vector match: '{entity.name}' → '{similar['name']}' "
                    f"(score: {similar['score']:.3f})"
                )
            else:
                # Store embedding in ChromaDB for new unique entities
                entity_name = entity.properties.get('normalized_name') or entity.name
                embedding = deduplicator.get_embedding(entity_name)
                
                # Generate entity ID (will be created in Neo4j later)
                entity_id = f"{namespace}:{entity.entity_type}:{entity_name}"
                
                deduplicator.vector_store.add_entity(
                    entity_id=entity_id,
                    entity_type=entity.entity_type,
                    entity_name=entity.name,
                    embedding=embedding,
                    namespace=namespace,
                    metadata={'normalized_name': entity_name}
                )
                stored_count += 1
                
        except Exception as e:
            context.logger.warning(
                f"Error in vector dedup for '{entity.name}': {e}"
            )
            continue
    
    if duplicate_count > 0 or stored_count > 0:
        context.logger.info(
            f"Vector dedup: {duplicate_count} duplicates found, "
            f"{stored_count} new embeddings stored (threshold: {threshold})"
        )
    
    return extraction_result
