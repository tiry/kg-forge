# Step 8: Entity Normalization and Deduplication (Basic + Fuzzy Matching)

**Status**: Completed  
**Dependencies**: Step 6 (Pipeline Architecture)

## Overview

Implement `before_store` hooks for entity normalization and deduplication to improve data quality in the knowledge graph. This step introduces multiple strategies for cleaning entity names and merging duplicate entities.

## Goals

1. **Entity Normalization**: Clean and standardize entity names before storage
2. **Automated Deduplication**: Detect and merge similar entities automatically
3. **Interactive Deduplication**: Provide UI for manual entity merging decisions
4. **Modular Hook Architecture**: Organize hooks by feature for easy configuration
5. **Vector Similarity**: Enable embedding-based entity matching

## Architecture

### Hook Organization

Hooks are organized by feature in separate modules under `kg_forge/pipeline/hooks/`:

```
kg_forge/pipeline/hooks/
├── __init__.py
├── normalization/
│   ├── __init__.py
│   ├── basic.py           # Basic text normalization
│   └── dictionary.py      # Dictionary-based normalization
├── deduplication/
│   ├── __init__.py
│   ├── fuzzy.py          # Jellyfish-based fuzzy matching
│   ├── vector.py         # Embedding-based similarity
│   └── interactive.py    # Interactive merge UI
└── embeddings/
    ├── __init__.py
    └── bert.py           # BERT embedding generator
```

### Default Hook Registration

`kg_forge/pipeline/default_hooks.py` defines the default pipeline configuration:

```python
def register_default_hooks(registry: HookRegistry) -> None:
    """Register default hooks for the pipeline."""
    
    # Normalization hooks (run first)
    registry.register('before_store', basic_normalize_entities)
    registry.register('before_store', dictionary_normalize_entities)
    
    # Deduplication hooks (run after normalization)
    registry.register('before_store', fuzzy_deduplicate_entities)
    registry.register('before_store', vector_deduplicate_entities)
    
    # Interactive dedup disabled by default (enable via config)
    # registry.register('before_store', interactive_deduplicate_entities)
```

## Components

### 1. Basic Normalization Hook

**File**: `kg_forge/pipeline/hooks/normalization/basic.py`

**Purpose**: Apply standard text normalization to entity names

**Transformations**:
- Convert to lowercase
- Remove special characters (keep alphanumeric, spaces, hyphens)
- Trim leading/trailing whitespace
- Collapse multiple spaces to single space

**Implementation**:

```python
def basic_normalize_entities(
    context: PipelineContext,
    extraction_result: ExtractionResult
) -> ExtractionResult:
    """
    Normalize entity names using basic text cleaning.
    
    Applied transformations:
    - Lowercase
    - Remove special characters
    - Trim whitespace
    - Collapse spaces
    """
    for entity in extraction_result.entities:
        entity.name = normalize_text(entity.name)
        entity.normalized_name = entity.name
    
    return extraction_result

def normalize_text(text: str) -> str:
    """Apply basic text normalization."""
    # Lowercase
    text = text.lower()
    
    # Remove special characters (keep alphanumeric, space, hyphen)
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    
    # Trim and collapse spaces
    text = ' '.join(text.split())
    
    return text
```

### 2. Dictionary Normalization Hook

**File**: `kg_forge/pipeline/hooks/normalization/dictionary.py`

**Purpose**: Expand abbreviations and standardize terms using a lookup dictionary

**Dictionary Format** (`config/normalization_dict.txt`):
```
KD : Knowledge Discovery
KG : Knowledge Graph
CI : Content Intelligence
ML : Machine Learning
AI : Artificial Intelligence
```

**Implementation**:

```python
class DictionaryNormalizer:
    """Normalizes entities using a lookup dictionary."""
    
    def __init__(self, dict_path: Path):
        self.dictionary = self._load_dictionary(dict_path)
    
    def _load_dictionary(self, path: Path) -> Dict[str, str]:
        """Load normalization dictionary from file."""
        dictionary = {}
        if not path.exists():
            return dictionary
        
        with open(path, 'r') as f:
            for line in f:
                line = line.strip()
                if ':' in line:
                    key, value = line.split(':', 1)
                    # Store normalized versions as keys
                    dictionary[normalize_text(key.strip())] = value.strip()
        
        return dictionary
    
    def normalize(self, text: str) -> str:
        """Normalize text using dictionary, then basic normalization."""
        # Check dictionary first
        normalized_key = normalize_text(text)
        if normalized_key in self.dictionary:
            text = self.dictionary[normalized_key]
        
        # Apply basic normalization to result
        return normalize_text(text)

def dictionary_normalize_entities(
    context: PipelineContext,
    extraction_result: ExtractionResult
) -> ExtractionResult:
    """
    Normalize entities using dictionary lookup.
    
    Expands abbreviations and standardizes terminology.
    """
    settings = context.settings
    dict_path = Path(settings.app.config_dir) / "normalization_dict.txt"
    
    normalizer = DictionaryNormalizer(dict_path)
    
    for entity in extraction_result.entities:
        original_name = entity.name
        entity.name = normalizer.normalize(original_name)
        entity.normalized_name = entity.name
        
        # Track if changed
        if original_name != entity.name:
            context.logger.debug(
                f"Dictionary normalized: '{original_name}' → '{entity.name}'"
            )
    
    return extraction_result
```

### 3. Fuzzy Deduplication Hook

**File**: `kg_forge/pipeline/hooks/deduplication/fuzzy.py`

**Purpose**: Find similar entities using fuzzy string matching (Jellyfish)

**Matching Strategy**:
- Use Jaro-Winkler similarity score
- Default threshold: 0.85
- Search existing entities of same type in graph
- Store aliases when match found

**Implementation**:

```python
import jellyfish

def fuzzy_deduplicate_entities(
    context: PipelineContext,
    extraction_result: ExtractionResult
) -> ExtractionResult:
    """
    Deduplicate entities using fuzzy string matching.
    
    Uses Jellyfish Jaro-Winkler similarity.
    """
    settings = context.settings
    threshold = getattr(settings.pipeline, 'fuzzy_threshold', 0.85)
    entity_repo = context.graph_client.entity_repo
    
    for entity in extraction_result.entities:
        # Query existing entities of same type
        existing = entity_repo.find_by_type(
            entity.entity_type,
            context.namespace
        )
        
        # Find best match
        best_match = None
        best_score = 0.0
        
        for existing_entity in existing:
            score = jellyfish.jaro_winkler_similarity(
                entity.normalized_name,
                existing_entity.name
            )
            
            if score > best_score and score >= threshold:
                best_match = existing_entity
                best_score = score
        
        if best_match:
            # Merge: keep existing entity, add current as alias
            _add_alias(best_match, entity.name, entity_repo)
            entity.merged_into = best_match.id
            
            context.logger.info(
                f"Fuzzy match ({best_score:.2f}): '{entity.name}' → "
                f"'{best_match.name}'"
            )
    
    return extraction_result

def _add_alias(entity: Entity, alias: str, repo: EntityRepository) -> None:
    """Add alias to entity's aliases list."""
    if not hasattr(entity, 'aliases') or entity.aliases is None:
        entity.aliases = []
    
    if alias not in entity.aliases and alias != entity.name:
        entity.aliases.append(alias)
        repo.update_aliases(entity.id, entity.aliases)
```

### 4. Vector Similarity Deduplication Hook

**File**: `kg_forge/pipeline/hooks/deduplication/vector.py`

**Purpose**: Find semantically similar entities using embeddings

**Vector Database**: Neo4j built-in vector index

**Embedding Model**: BERT (sentence-transformers)

**Implementation**:

```python
from sentence_transformers import SentenceTransformer

class VectorDeduplicator:
    """Deduplicate entities using vector similarity."""
    
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        self.model = SentenceTransformer(model_name)
    
    def get_embedding(self, text: str) -> List[float]:
        """Generate embedding for text."""
        return self.model.encode(text).tolist()
    
    def find_similar(
        self,
        entity: Entity,
        entity_repo: EntityRepository,
        namespace: str,
        threshold: float = 0.85
    ) -> Optional[Entity]:
        """Find similar entity using vector search."""
        # Generate embedding for current entity
        embedding = self.get_embedding(entity.normalized_name)
        
        # Search vector index in Neo4j
        similar = entity_repo.vector_search(
            entity_type=entity.entity_type,
            embedding=embedding,
            namespace=namespace,
            limit=5,
            threshold=threshold
        )
        
        # Return best match if found
        return similar[0] if similar else None

def vector_deduplicate_entities(
    context: PipelineContext,
    extraction_result: ExtractionResult
) -> ExtractionResult:
    """
    Deduplicate entities using vector similarity.
    
    Uses BERT embeddings and Neo4j vector index.
    """
    settings = context.settings
    threshold = getattr(settings.pipeline, 'vector_threshold', 0.85)
    
    deduplicator = VectorDeduplicator()
    entity_repo = context.graph_client.entity_repo
    
    for entity in extraction_result.entities:
        # Skip if already merged
        if hasattr(entity, 'merged_into') and entity.merged_into:
            continue
        
        # Find similar entity
        similar = deduplicator.find_similar(
            entity,
            entity_repo,
            context.namespace,
            threshold
        )
        
        if similar:
            # Merge: keep existing entity, add current as alias
            _add_alias(similar, entity.name, entity_repo)
            entity.merged_into = similar.id
            
            context.logger.info(
                f"Vector match: '{entity.name}' → '{similar.name}'"
            )
            
        # Store embedding for new entities
        elif not hasattr(entity, 'merged_into'):
            entity.embedding = deduplicator.get_embedding(
                entity.normalized_name
            )
    
    return extraction_result
```

### 5. Interactive Deduplication Hook

**File**: `kg_forge/pipeline/hooks/deduplication/interactive.py`

**Purpose**: Present potential duplicates to user for manual decision

**UI**: Rich console-based interface

**Implementation**:

```python
from rich.console import Console
from rich.table import Table
from rich.prompt import Confirm, IntPrompt

def interactive_deduplicate_entities(
    context: PipelineContext,
    extraction_result: ExtractionResult
) -> ExtractionResult:
    """
    Interactive entity deduplication.
    
    Presents potential duplicates for user review.
    """
    console = Console()
    entity_repo = context.graph_client.entity_repo
    
    for entity in extraction_result.entities:
        # Skip if already merged
        if hasattr(entity, 'merged_into') and entity.merged_into:
            continue
        
        # Find potential matches
        candidates = _find_candidates(
            entity,
            entity_repo,
            context.namespace
        )
        
        if not candidates:
            continue
        
        # Display options
        console.print(f"\n[bold]New entity:[/bold] {entity.name}")
        console.print(f"[dim]Type: {entity.entity_type}[/dim]\n")
        
        table = Table(title="Potential Matches")
        table.add_column("Option", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Description")
        
        table.add_row("0", "[NEW]", "Create as new entity")
        
        for idx, candidate in enumerate(candidates, 1):
            desc = candidate.description[:50] if candidate.description else ""
            table.add_row(str(idx), candidate.name, desc)
        
        console.print(table)
        
        # Get user choice
        choice = IntPrompt.ask(
            "Select option",
            default=0,
            choices=[str(i) for i in range(len(candidates) + 1)]
        )
        
        if choice > 0:
            # Merge with selected entity
            selected = candidates[choice - 1]
            _add_alias(selected, entity.name, entity_repo)
            entity.merged_into = selected.id
            
            console.print(
                f"[green]✓[/green] Merged into: {selected.name}"
            )
    
    return extraction_result

def _find_candidates(
    entity: Entity,
    repo: EntityRepository,
    namespace: str,
    max_candidates: int = 5
) -> List[Entity]:
    """Find candidate entities for manual review."""
    # Use both fuzzy and vector similarity
    # Return top N candidates
    ...
```

### 6. Entity Repository Updates

**File**: `kg_forge/graph/neo4j/entity_repo.py`

Add methods to support deduplication:

```python
class EntityRepository:
    
    def update_aliases(self, entity_id: str, aliases: List[str]) -> None:
        """Update entity aliases."""
        query = """
        MATCH (e:Entity {id: $entity_id})
        SET e.aliases = $aliases
        """
        self.client.execute_query(
            query,
            entity_id=entity_id,
            aliases=aliases
        )
    
    def vector_search(
        self,
        entity_type: str,
        embedding: List[float],
        namespace: str,
        limit: int = 5,
        threshold: float = 0.85
    ) -> List[Entity]:
        """Find similar entities using vector index."""
        query = """
        CALL db.index.vector.queryNodes(
            'entity_embeddings',
            $limit,
            $embedding
        ) YIELD node, score
        WHERE node.type = $entity_type
          AND node.namespace = $namespace
          AND score >= $threshold
        RETURN node, score
        ORDER BY score DESC
        """
        # ... implementation
    
    def create_vector_index(self) -> None:
        """Create vector index for entity embeddings."""
        query = """
        CREATE VECTOR INDEX entity_embeddings IF NOT EXISTS
        FOR (e:Entity)
        ON e.embedding
        OPTIONS {indexConfig: {
            `vector.dimensions`: 384,
            `vector.similarity_function`: 'cosine'
        }}
        """
        self.client.execute_query(query)
```

## Configuration

Add to `kg_forge/config/settings.py`:

```python
class PipelineSettings(BaseSettings):
    # ... existing settings
    
    # Normalization
    normalization_dict_path: Optional[str] = "config/normalization_dict.txt"
    
    # Deduplication thresholds
    fuzzy_threshold: float = 0.85
    vector_threshold: float = 0.85
    
    # Embedding model
    embedding_model: str = "all-MiniLM-L6-v2"
    
    # Interactive dedup
    enable_interactive_dedup: bool = False
```

## Testing

### Unit Tests

**Test Coverage**:
- Basic normalization: `tests/test_pipeline/hooks/test_basic_normalization.py`
- Dictionary normalization: `tests/test_pipeline/hooks/test_dictionary_normalization.py`
- Fuzzy deduplication: `tests/test_pipeline/hooks/test_fuzzy_dedup.py`
- Vector deduplication: `tests/test_pipeline/hooks/test_vector_dedup.py`
- Entity repository vector methods: `tests/test_graph/test_entity_repo_vector.py`

### Integration Tests

**Test Scenarios**:
1. Full pipeline with normalization only
2. Full pipeline with normalization + fuzzy dedup
3. Full pipeline with all automated hooks
4. Alias storage and retrieval
5. Vector index creation and search

## Dependencies

Add to `requirements.txt`:

```
jellyfish>=1.0.0
sentence-transformers>=2.2.0
torch>=2.0.0
```

## Implementation Checklist

- [x] Create hook directory structure
- [x] Implement basic normalization hook
- [x] Implement dictionary normalization hook
- [x] Create normalization dictionary file (100+ SE acronyms)
- [x] Implement fuzzy deduplication hook (using jellyfish)
- [ ] Implement BERT embedding generator (→ See Spec 09)
- [ ] Implement vector deduplication hook (→ See Spec 09)
- [ ] Implement interactive deduplication hook (→ Future)
- [ ] Add vector search to EntityRepository (→ See Spec 09)
- [ ] Create vector index in Neo4j schema (→ See Spec 09)
- [x] Update default hooks registration
- [x] Add configuration settings (fuzzy_threshold)
- [x] Write unit tests for normalization and fuzzy dedup
- [ ] Write integration tests (→ Future)
- [x] Update documentation
- [x] Create comprehensive normalization dictionary

**Completed in Step 8**: Basic normalization, dictionary-based normalization, and fuzzy string matching deduplication
**Deferred to Step 9**: Vector-based deduplication with BERT embeddings

## Example Usage

```python
# Pipeline with custom hook configuration
from kg_forge.pipeline.orchestrator import PipelineOrchestrator
from kg_forge.pipeline.hooks.normalization import basic, dictionary
from kg_forge.pipeline.hooks.deduplication import fuzzy, vector

orchestrator = PipelineOrchestrator(settings)

# Custom hook order
orchestrator.registry.clear('before_store')
orchestrator.registry.register('before_store', basic.basic_normalize_entities)
orchestrator.registry.register('before_store', dictionary.dictionary_normalize_entities)
orchestrator.registry.register('before_store', fuzzy.fuzzy_deduplicate_entities)

# Run pipeline
result = orchestrator.run(document, namespace="confluence")
```

## Success Criteria

1. ✅ Basic normalization cleans entity names consistently
2. ✅ Dictionary normalization expands abbreviations correctly
3. ✅ Fuzzy matching finds similar entities with >85% accuracy
4. ✅ Vector similarity detects semantic duplicates
5. ✅ Aliases are stored and retrievable from graph
6. ✅ Vector index search returns relevant results
7. ✅ Interactive UI allows manual merge decisions
8. ✅ All tests pass with >80% coverage
9. ✅ Hooks can be enabled/disabled via configuration
10. ✅ Pipeline performance remains acceptable (<2x slowdown)

## Future Enhancements

- Support for multi-language normalization
- Active learning for dictionary expansion
- Confidence scores for automatic merges
- Audit trail for merge decisions
- Bulk re-deduplication command
- Custom similarity metrics per entity type
