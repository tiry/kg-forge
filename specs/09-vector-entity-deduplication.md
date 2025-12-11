# Step 9: Vector-Based Entity Deduplication

**Status**: Completed  
**Dependencies**: Step 8 (Basic Normalization and Fuzzy Matching)

## Overview

Implement vector-based entity deduplication using BERT embeddings and Neo4j vector indexes. This adds semantic similarity matching to complement the existing fuzzy string matching, enabling detection of entities that are semantically similar but may not match well with string comparison alone.

## Goals

1. **Semantic Similarity**: Detect entities with similar meanings using embeddings
2. **BERT Integration**: Use Hugging Face sentence-transformers for local embeddings
3. **Neo4j Vector Index**: Leverage Neo4j's built-in vector search capabilities
4. **Complementary Matching**: Run after fuzzy matching to catch additional duplicates
5. **Efficient Search**: Use vector indexes for fast similarity queries

## Architecture

### Component Structure

```
kg_forge/
├── pipeline/
│   └── hooks/
│       └── deduplication/
│           ├── fuzzy.py          # Existing fuzzy matching
│           └── vector.py         # New: Vector-based matching
├── graph/
│   └── neo4j/
│       ├── entity_repo.py        # Update: Add vector search methods
│       └── schema.py             # Update: Create vector index
└── config/
    └── settings.py               # Update: Add vector config
```

## Implementation Details

### 1. Vector Deduplication Hook

**File**: `kg_forge/pipeline/hooks/deduplication/vector.py`

**Purpose**: Find semantically similar entities using BERT embeddings and cosine similarity

**Key Features**:
- Uses sentence-transformers (all-MiniLM-L6-v2 model by default)
- Generates 384-dimensional embeddings
- Cosine similarity threshold (default: 0.85)
- Skips entities already matched by fuzzy dedup
- Stores embeddings on new entities for future comparisons

**Implementation**:

```python
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
                # Mark as duplicate
                entity.duplicate_of = similar.name
                entity.duplicate_of_id = getattr(similar, 'id', None)
                duplicate_count += 1
                
                context.logger.info(
                    f"Vector match: '{entity.name}' → '{similar.name}'"
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
    
    if duplicate_count > 0:
        context.logger.info(
            f"Vector dedup: {duplicate_count} duplicates found, "
            f"{embedding_count} new embeddings created (threshold: {threshold})"
        )
    
    return extraction_result
```

### 2. Entity Repository Vector Search Methods

**File**: `kg_forge/graph/neo4j/entity_repo.py`

Add vector search capabilities:

```python
def vector_search(
    self,
    entity_type: str,
    embedding: List[float],
    namespace: str,
    limit: int = 5,
    threshold: float = 0.85
) -> List[Entity]:
    """
    Find similar entities using Neo4j vector index.
    
    Args:
        entity_type: Type of entities to search
        embedding: Query embedding vector
        namespace: Entity namespace
        limit: Maximum number of results
        threshold: Minimum cosine similarity score
        
    Returns:
        List of similar entities sorted by similarity
    """
    query = """
    CALL db.index.vector.queryNodes(
        'entity_embeddings',
        $limit,
        $embedding
    ) YIELD node, score
    WHERE node.type = $entity_type
      AND node.namespace = $namespace
      AND score >= $threshold
      AND node.embedding IS NOT NULL
    RETURN node, score
    ORDER BY score DESC
    """
    
    try:
        result = self.client.execute_query(
            query,
            limit=limit,
            embedding=embedding,
            entity_type=entity_type,
            namespace=namespace,
            threshold=threshold
        )
        
        entities = []
        for record in result.records:
            node = record['node']
            score = record['score']
            
            # Convert node to Entity
            entity = self._node_to_entity(node)
            entity.similarity_score = score
            entities.append(entity)
        
        return entities
        
    except Exception as e:
        self.logger.error(f"Vector search failed: {e}")
        return []


def store_entity_with_embedding(
    self,
    entity: Entity,
    namespace: str
) -> str:
    """
    Store entity in Neo4j with its embedding vector.
    
    Args:
        entity: Entity to store
        namespace: Entity namespace
        
    Returns:
        Entity ID
    """
    # Existing storage logic...
    entity_id = self._create_entity_node(entity, namespace)
    
    # Store embedding if present
    if hasattr(entity, 'embedding') and entity.embedding:
        self._update_entity_embedding(entity_id, entity.embedding)
    
    return entity_id


def _update_entity_embedding(self, entity_id: str, embedding: List[float]) -> None:
    """Update entity's embedding vector."""
    query = """
    MATCH (e:Entity {id: $entity_id})
    SET e.embedding = $embedding
    """
    self.client.execute_query(
        query,
        entity_id=entity_id,
        embedding=embedding
    )
```

### 3. Neo4j Vector Index Creation

**File**: `kg_forge/graph/neo4j/schema.py`

Add vector index setup:

```python
def create_vector_index(self) -> None:
    """
    Create vector index for entity embeddings.
    
    This creates a vector index using cosine similarity for
    384-dimensional BERT embeddings (all-MiniLM-L6-v2).
    """
    query = """
    CREATE VECTOR INDEX entity_embeddings IF NOT EXISTS
    FOR (e:Entity)
    ON e.embedding
    OPTIONS {indexConfig: {
        `vector.dimensions`: 384,
        `vector.similarity_function`: 'cosine'
    }}
    """
    
    try:
        self.client.execute_query(query)
        self.logger.info("Created vector index: entity_embeddings")
    except Exception as e:
        self.logger.warning(f"Vector index creation failed: {e}")


def initialize_schema(self) -> None:
    """Initialize all schema elements including vector index."""
    # Existing schema creation...
    self.create_constraints()
    self.create_indexes()
    
    # Create vector index
    self.create_vector_index()
```

### 4. Configuration Updates

**File**: `kg_forge/config/settings.py`

```python
class PipelineSettings(BaseSettings):
    """Pipeline-specific settings."""
    
    # Existing settings...
    normalization_dict_path: Optional[str] = "config/normalization_dict.txt"
    fuzzy_threshold: float = 0.85
    
    # Vector deduplication settings
    vector_threshold: float = 0.85
    embedding_model: str = "all-MiniLM-L6-v2"
    enable_vector_dedup: bool = True
```

### 5. Default Hook Registration

**File**: `kg_forge/pipeline/default_hooks.py`

```python
from kg_forge.pipeline.hooks.normalization import (
    basic_normalize_entities,
    dictionary_normalize_entities
)
from kg_forge.pipeline.hooks.deduplication import (
    fuzzy_deduplicate_entities,
    vector_deduplicate_entities
)

def register_default_hooks(registry: HookRegistry) -> None:
    """Register default pipeline hooks."""
    
    # Normalization (run first)
    registry.register('before_store', basic_normalize_entities)
    registry.register('before_store', dictionary_normalize_entities)
    
    # Deduplication (run after normalization)
    registry.register('before_store', fuzzy_deduplicate_entities)
    registry.register('before_store', vector_deduplicate_entities)
```

## Testing

### Unit Tests

**File**: `tests/test_pipeline/hooks/test_vector_dedup.py`

```python
"""Tests for vector-based entity deduplication."""

import pytest
from unittest.mock import Mock, MagicMock
import numpy as np

from kg_forge.pipeline.hooks.deduplication.vector import (
    VectorDeduplicator,
    vector_deduplicate_entities
)
from kg_forge.models.extraction import ExtractedEntity, ExtractionResult


class TestVectorDeduplicator:
    """Test VectorDeduplicator class."""
    
    def test_get_embedding(self):
        """Test embedding generation."""
        dedup = VectorDeduplicator()
        
        embedding = dedup.get_embedding("kubernetes")
        
        # Should return 384-dimensional vector for all-MiniLM-L6-v2
        assert len(embedding) == 384
        assert all(isinstance(x, float) for x in embedding)
    
    def test_similar_texts_have_high_similarity(self):
        """Test that similar texts produce similar embeddings."""
        dedup = VectorDeduplicator()
        
        emb1 = np.array(dedup.get_embedding("machine learning"))
        emb2 = np.array(dedup.get_embedding("ML algorithms"))
        emb3 = np.array(dedup.get_embedding("database"))
        
        # Cosine similarity
        sim_ml = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
        sim_db = np.dot(emb1, emb3) / (np.linalg.norm(emb1) * np.linalg.norm(emb3))
        
        # ML terms should be more similar than ML vs database
        assert sim_ml > sim_db
        assert sim_ml > 0.7  # Reasonably high similarity
    
    def test_find_similar_with_matches(self):
        """Test finding similar entities."""
        dedup = VectorDeduplicator()
        
        entity = ExtractedEntity(
            entity_type="Technology",
            name="k8s",
            properties={"normalized_name": "kubernetes"}
        )
        
        # Mock entity repo
        mock_repo = Mock()
        existing_entity = ExtractedEntity(
            entity_type="Technology",
            name="Kubernetes"
        )
        existing_entity.id = "existing-1"
        mock_repo.vector_search.return_value = [existing_entity]
        
        # Find similar
        similar = dedup.find_similar(entity, mock_repo, "default", 0.85)
        
        assert similar is not None
        assert similar.name == "Kubernetes"


class TestVectorDeduplicateEntitiesHook:
    """Test vector_deduplicate_entities hook."""
    
    def test_vector_dedup_marks_duplicates(self):
        """Test that vector dedup marks similar entities."""
        # Mock context
        context = Mock()
        context.logger = Mock()
        context.settings = Mock()
        context.settings.pipeline = Mock()
        context.settings.pipeline.vector_threshold = 0.85
        context.settings.pipeline.embedding_model = 'all-MiniLM-L6-v2'
        context.namespace = "default"
        
        # Mock entity repo
        mock_repo = Mock()
        existing = ExtractedEntity(
            entity_type="Technology",
            name="Kubernetes",
            properties={'normalized_name': 'kubernetes'}
        )
        existing.id = 'existing-1'
        mock_repo.vector_search.return_value = [existing]
        
        context.graph_client = Mock()
        context.graph_client.entity_repo = mock_repo
        
        # Entity to deduplicate
        entities = [
            ExtractedEntity(
                entity_type="Technology",
                name="k8s",
                properties={'normalized_name': 'kubernetes'}
            )
        ]
        
        extraction_result = ExtractionResult(entities=entities)
        
        # Run hook
        result = vector_deduplicate_entities(context, extraction_result)
        
        # Verify
        assert hasattr(result.entities[0], 'duplicate_of')
        assert result.entities[0].duplicate_of == 'Kubernetes'
```

## Dependencies

**Update `requirements.txt`**:

```
# Existing dependencies...
jellyfish>=1.0.0

# Vector deduplication
sentence-transformers>=2.2.0
torch>=2.0.0
transformers>=4.30.0
```

## Implementation Checklist

- [ ] Implement VectorDeduplicator class
- [ ] Implement vector_deduplicate_entities hook
- [ ] Add vector_search method to EntityRepository
- [ ] Add store_entity_with_embedding method to EntityRepository
- [ ] Create vector index in Neo4j schema
- [ ] Update configuration settings
- [ ] Register vector dedup in default hooks
- [ ] Write unit tests
- [ ] Write integration tests
- [ ] Update documentation
- [ ] Performance testing with large entity sets

## Usage Example

```python
from kg_forge.pipeline.orchestrator import PipelineOrchestrator

# Vector dedup is enabled by default
orchestrator = PipelineOrchestrator(settings)
result = orchestrator.run(document, namespace="confluence")

# Disable vector dedup if needed
settings.pipeline.enable_vector_dedup = False

# Or customize threshold
settings.pipeline.vector_threshold = 0.90  # More strict matching
```

## Performance Considerations

1. **Model Loading**: Sentence-transformers model is loaded once and reused
2. **Embedding Storage**: 384 floats per entity (~1.5KB per embedding)
3. **Vector Index**: Neo4j vector index provides O(log n) search complexity
4. **Batch Processing**: Consider batching embedding generation for large entity sets

## Success Criteria

1. ✅ Vector dedup detects semantic duplicates missed by fuzzy matching
2. ✅ Processing time remains under 2x compared to fuzzy-only dedup
3. ✅ Vector index searches return results in <100ms
4. ✅ All unit tests pass with >80% coverage
5. ✅ Integration with existing pipeline hooks works seamlessly
6. ✅ Embeddings are stored correctly in Neo4j
7. ✅ Vector search returns relevant matches above threshold

## Future Enhancements

- Support for different embedding models (OpenAI, Cohere, etc.)
- Multilingual embedding models
- Fine-tuned models for domain-specific terminology
- Hybrid search combining fuzzy + vector scores
- Batch embedding generation for performance
- Embedding dimensionality reduction options
