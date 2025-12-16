# Step 9: Vector-Based Entity Deduplication (ChromaDB)

**Status**: In Progress - Updating to use ChromaDB  
**Dependencies**: Step 8 (Basic Normalization and Fuzzy Matching)

## Overview

Implement vector-based entity deduplication using BERT embeddings and ChromaDB for vector storage. This adds semantic similarity matching to complement the existing fuzzy string matching, enabling detection of entities that are semantically similar but may not match well with string comparison alone.

**Architecture Change**: Instead of using Neo4j Enterprise vector indexes (not available in Community Edition), we use ChromaDB as a separate, embedded vector database alongside Neo4j.

## Goals

1. **Semantic Similarity**: Detect entities with similar meanings using embeddings
2. **BERT Integration**: Use Hugging Face sentence-transformers for local embeddings
3. **ChromaDB Storage**: Lightweight, embeddable vector database (SQLite-backed)
4. **Complementary Matching**: Run after fuzzy matching to catch additional duplicates
5. **Efficient Search**: Use ChromaDB's built-in cosine similarity search

## Architecture

### Component Structure

```
kg_forge/
├── vector/                      # NEW: Vector storage abstraction
│   ├── __init__.py
│   ├── base.py                  # Abstract VectorStore interface
│   └── chroma.py                # ChromaDB implementation
├── pipeline/
│   └── hooks/
│       └── deduplication/
│           ├── fuzzy.py         # Existing fuzzy matching
│           └── vector.py        # Vector-based matching (updated)
├── graph/
│   └── neo4j/
│       └── entity_repo.py       # Entity metadata (no vector methods needed)
└── config/
    └── settings.py              # Vector config
```

### Data Flow

```
Neo4j (Graph Database)          ChromaDB (Vector Database)
├─ Entities                     ├─ Entity Embeddings
├─ Documents                    │  • Collection per namespace
├─ Relationships                │  • 384-dim vectors
└─ Entity metadata              └─ Metadata: entity_id, type, name
```

**Key Design Decision**: Separate concerns - Neo4j handles graph structure, ChromaDB handles vector similarity.

## Implementation Details

### 1. Vector Store Abstraction

**File**: `kg_forge/vector/base.py`

```python
"""Abstract base class for vector stores."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple


class VectorStore(ABC):
    """Abstract interface for vector storage and similarity search."""
    
    @abstractmethod
    def add_entity(
        self,
        entity_id: str,
        entity_type: str,
        entity_name: str,
        embedding: List[float],
        namespace: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add entity embedding to the vector store.
        
        Args:
            entity_id: Unique entity identifier
            entity_type: Type of entity (Technology, Product, etc.)
            entity_name: Entity name
            embedding: Embedding vector
            namespace: Namespace for isolation
            metadata: Additional metadata
        """
        pass
    
    @abstractmethod
    def search_similar(
        self,
        entity_type: str,
        embedding: List[float],
        namespace: str,
        limit: int = 5,
        threshold: float = 0.85
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        """
        Search for similar entities by vector similarity.
        
        Args:
            entity_type: Type to filter by
            embedding: Query embedding vector
            namespace: Namespace to search in
            limit: Maximum results
            threshold: Minimum similarity score (0-1)
            
        Returns:
            List of (entity_id, similarity_score, metadata) tuples
        """
        pass
    
    @abstractmethod
    def delete_namespace(self, namespace: str) -> int:
        """
        Delete all entities in a namespace.
        
        Args:
            namespace: Namespace to clear
            
        Returns:
            Number of entities deleted
        """
        pass
    
    @abstractmethod
    def get_stats(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics about stored vectors.
        
        Args:
            namespace: Optional namespace to filter by
            
        Returns:
            Statistics dictionary
        """
        pass
```

**File**: `kg_forge/vector/chroma.py`

```python
"""ChromaDB implementation of vector store."""

import logging
from typing import List, Dict, Any, Optional, Tuple
import chromadb
from chromadb.config import Settings as ChromaSettings

from kg_forge.vector.base import VectorStore

logger = logging.getLogger(__name__)


class ChromaVectorStore(VectorStore):
    """ChromaDB-based vector storage for entity embeddings."""
    
    def __init__(self, persist_directory: str = "./data/chroma_db"):
        """
        Initialize ChromaDB client.
        
        Args:
            persist_directory: Directory for ChromaDB persistence
        """
        self.persist_directory = persist_directory
        
        # Initialize ChromaDB with persistence
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        logger.info(f"Initialized ChromaDB at: {persist_directory}")
        self._collections = {}
    
    def _get_collection(self, namespace: str):
        """Get or create collection for namespace."""
        if namespace not in self._collections:
            # Collection name: namespace-based
            collection_name = f"entities_{namespace}"
            
            # Get or create collection
            try:
                collection = self.client.get_collection(collection_name)
            except Exception:
                collection = self.client.create_collection(
                    name=collection_name,
                    metadata={"namespace": namespace}
                )
            
            self._collections[namespace] = collection
            logger.info(f"Using ChromaDB collection: {collection_name}")
        
        return self._collections[namespace]
    
    def add_entity(
        self,
        entity_id: str,
        entity_type: str,
        entity_name: str,
        embedding: List[float],
        namespace: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add entity embedding to ChromaDB."""
        collection = self._get_collection(namespace)
        
        # Prepare metadata
        meta = {
            "entity_type": entity_type,
            "entity_name": entity_name,
            "namespace": namespace
        }
        if metadata:
            meta.update(metadata)
        
        # Add to collection
        collection.add(
            ids=[entity_id],
            embeddings=[embedding],
            metadatas=[meta]
        )
        
        logger.debug(f"Added embedding for entity: {entity_name} ({entity_type})")
    
    def search_similar(
        self,
        entity_type: str,
        embedding: List[float],
        namespace: str,
        limit: int = 5,
        threshold: float = 0.85
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        """Search for similar entities in ChromaDB."""
        collection = self._get_collection(namespace)
        
        # Query with entity_type filter
        results = collection.query(
            query_embeddings=[embedding],
            n_results=limit,
            where={"entity_type": entity_type}
        )
        
        # Process results
        similar_entities = []
        
        if results['ids'] and results['ids'][0]:
            for i, entity_id in enumerate(results['ids'][0]):
                score = 1 - results['distances'][0][i]  # Convert distance to similarity
                
                # Filter by threshold
                if score >= threshold:
                    metadata = results['metadatas'][0][i]
                    similar_entities.append((entity_id, score, metadata))
        
        return similar_entities
    
    def delete_namespace(self, namespace: str) -> int:
        """Delete ChromaDB collection for namespace."""
        collection_name = f"entities_{namespace}"
        
        try:
            collection = self.client.get_collection(collection_name)
            count = collection.count()
            self.client.delete_collection(collection_name)
            
            # Remove from cache
            if namespace in self._collections:
                del self._collections[namespace]
            
            logger.info(f"Deleted ChromaDB collection: {collection_name} ({count} entities)")
            return count
            
        except Exception as e:
            logger.warning(f"Could not delete collection {collection_name}: {e}")
            return 0
    
    def get_stats(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """Get ChromaDB statistics."""
        if namespace:
            try:
                collection = self._get_collection(namespace)
                count = collection.count()
                return {
                    "namespace": namespace,
                    "entity_count": count,
                    "collection_name": f"entities_{namespace}"
                }
            except Exception as e:
                return {"error": str(e)}
        else:
            # Global stats
            collections = self.client.list_collections()
            return {
                "total_collections": len(collections),
                "collections": [c.name for c in collections]
            }
```

### 2. Updated Vector Deduplication Hook

**File**: `kg_forge/pipeline/hooks/deduplication/vector.py`

Key changes:
- Use VectorStore abstraction instead of Neo4j
- Store embeddings in ChromaDB instead of Neo4j
- Search uses ChromaDB similarity search

```python
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
        """Generate embedding vector for text."""
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
        # Generate embedding
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
        settings.vector.threshold: float (default: 0.85)
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
```

### 3. Configuration Updates

**File**: `kg_forge/config/settings.py`

```python
class VectorSettings(BaseSettings):
    """Vector storage and deduplication settings."""
    
    # ChromaDB settings
    persist_dir: str = "./data/chroma_db"
    
    # Deduplication settings  
    threshold: float = 0.85
    model_name: str = "all-MiniLM-L6-v2"
    enabled: bool = True


class GraphConfig(BaseSettings):
    """Main configuration."""
    
    # Existing settings...
    neo4j: Neo4jSettings
    pipeline: PipelineSettings
    
    # Vector settings
    vector: VectorSettings = VectorSettings()
```

### 4. Database Clear Operation

Update `kg_forge/cli/db.py` to also clear ChromaDB:

```python
def clear_namespace(namespace: str, confirm: bool = False):
    """Clear both Neo4j and ChromaDB for namespace."""
    # Clear Neo4j
    neo4j_count = graph_client.schema_manager.clear_namespace(namespace)
    
    # Clear ChromaDB
    from kg_forge.vector.chroma import ChromaVectorStore
    vector_store = ChromaVectorStore()
    chroma_count = vector_store.delete_namespace(namespace)
    
    logger.info(
        f"Cleared namespace '{namespace}': "
        f"{neo4j_count} graph nodes, {chroma_count} vectors"
    )
```

## Testing

### Unit Tests

**File**: `tests/test_vector/test_chroma.py`

```python
"""Tests for ChromaDB vector store."""

import pytest
import tempfile
import shutil
from pathlib import Path

from kg_forge.vector.chroma import ChromaVectorStore


class TestChromaVectorStore:
    """Test ChromaDB vector store implementation."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for ChromaDB."""
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp, ignore_errors=True)
    
    @pytest.fixture
    def vector_store(self, temp_dir):
        """Create ChromaVectorStore instance."""
        return ChromaVectorStore(persist_directory=temp_dir)
    
    def test_add_and_search(self, vector_store):
        """Test adding and searching entities."""
        # Add entities
        vector_store.add_entity(
            entity_id="tech-1",
            entity_type="Technology",
            entity_name="Kubernetes",
            embedding=[0.1] * 384,
            namespace="test"
        )
        
        # Search
        results = vector_store.search_similar(
            entity_type="Technology",
            embedding=[0.1] * 384,
            namespace="test",
            threshold=0.9
        )
        
        assert len(results) == 1
        assert results[0][0] == "tech-1"
    
    def test_namespace_isolation(self, vector_store):
        """Test that namespaces are isolated."""
        # Add to namespace1
        vector_store.add_entity(
            "e1", "Type1", "Entity1", [0.5] * 384, "ns1"
        )
        
        # Add to namespace2
        vector_store.add_entity(
            "e2", "Type1", "Entity2", [0.5] * 384, "ns2"
        )
        
        # Search in ns1 should not find ns2 entities
        results = vector_store.search_similar(
            "Type1", [0.5] * 384, "ns1", threshold=0.5
        )
        
        assert len(results) == 1
        assert results[0][0] == "e1"
```

## Dependencies

**Update `requirements.txt`**:

```
# Existing dependencies...
jellyfish>=1.0.0

# Vector deduplication
sentence-transformers>=2.2.0
torch>=2.0.0
chromadb>=0.4.0  # NEW: ChromaDB for vector storage
```

## Implementation Checklist

- [ ] Create vector store abstraction (`vector/base.py`)
- [ ] Implement ChromaDB backend (`vector/chroma.py`)
- [ ] Update VectorDeduplicator to use ChromaDB
- [ ] Update vector_deduplicate_entities hook
- [ ] Add vector settings to configuration
- [ ] Update db clear command to handle ChromaDB
- [ ] Write ChromaDB unit tests
- [ ] Write vector dedup integration tests
- [ ] Update documentation
- [ ] Performance testing

## Success Criteria

1. ✅ ChromaDB stores and retrieves embeddings correctly
2. ✅ Vector dedup detects semantic duplicates missed by fuzzy matching
3. ✅ All unit tests pass with >80% coverage
4. ✅ ChromaDB persists across restarts
5. ✅ Namespace isolation works correctly
6. ✅ Clear namespace removes both Neo4j and ChromaDB data
7. ✅ No dependency on Neo4j Enterprise Edition

## Future Enhancements

- Support for different embedding models
- Batch embedding generation
- Alternative vector stores (Qdrant, LanceDB)
- Hybrid search combining fuzzy + vector scores
- Vector index optimization and tuning
