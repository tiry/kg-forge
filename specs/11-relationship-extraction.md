# Spec 11: Entity Relationship Extraction and Storage

**Status:** Draft  
**Created:** 2025-12-15  
**Dependencies:** Spec 06 (Data Pipeline), Spec 08 (Entity Deduplication), Spec 09 (Vector Deduplication)

## Overview

Currently, the system extracts entities from LLM responses but **discards the `relations` field**. This spec defines how to extract, process, and store entity-to-entity relationships to build a richer knowledge graph.

## Current State Analysis

### What Works
- ✅ LLM already returns `relations` in JSON response
- ✅ `Neo4jEntityRepository.create_relationship()` method exists
- ✅ Entity normalization/deduplication pipeline is functional
- ✅ Documents are linked to entities via `MENTIONS` relationships

### Current Limitations
- ❌ `ResponseParser` only extracts `entities`, ignores `relations`
- ❌ `ExtractionResult` model has no field for relationships  
- ❌ Orchestrator doesn't process or store entity–>entity relationships
- ❌ No mapping from LLM entity names → deduplicated graph entities

### LLM Response Format (Current)

**Key Insight:** The LLM uses **integer indices** to reference entities in relationships, not names!

```json
{
  "entities": [
    {
      "type_id": "product",
      "name": "Knowledge Discovery",
      "aliases": ["KD"],
      "evidence": "The KD product helps..."
    },
    {
      "type_id": "engineering_team",
      "name": "Platform Engineering",
      "evidence": "Maintained by Platform team"
    },
    {
      "type_id": "technology",
      "name": "Python",
      "evidence": "Built with Python"
    }
  ],
  "relations": [
    {
      "from_entity": 0,  // Index → "Knowledge Discovery"
      "to_entity": 1,     // Index → "Platform Engineering"
      "type": "maintained_by"
    },
    {
      "from_entity": 0,  // Index → "Knowledge Discovery"
      "to_entity": 2,     // Index → "Python"
      "type": "built_with"
    }
  ]
}
```

## Requirements

### FR1: Relationship Data Model

Create `ExtractedRelationship` dataclass in `models/extraction.py`:

```python
@dataclass
class ExtractedRelationship:
    """Relationship between two extracted entities using array indices."""
    
    from_index: int
    """Index of source entity in extraction results array."""
    
    to_index: int
    """Index of target entity in extraction results array."""
    
    relation_type: str
    """Relationship type (e.g., 'USES', 'MAINTAINED_BY')."""
    
    confidence: float = 1.0
    """Confidence score (0.0-1.0)."""
    
    properties: Dict[str, Any] = field(default_factory=dict)
    """Additional relationship properties (e.g., evidence)."""
```

**Note:** Indices reference positions in the `entities` list. After hooks run, we resolve indices to actual entity data using `entities[from_index]` and `entities[to_index]`.

### FR2: Update ExtractionResult Model

Add `relationships` field to `ExtractionResult`:

```python
@dataclass
class ExtractionResult:
    entities: List[ExtractedEntity]
    relationships: List[ExtractedRelationship] = field(default_factory=list)  # NEW
    raw_response: Optional[str] = None
    # ... rest unchanged
```

### FR3: Parser Enhancement

Update `ResponseParser._extract_entities()` to parse relationships using **entity indices**:

```python
def _extract_entities(self, data: dict) -> Tuple[List[ExtractedEntity], List[ExtractedRelationship]]:
    """Extract entities AND relationships from parsed JSON."""
    
    # Extract entities (existing logic)
    entities = self._parse_entities_list(data.get("entities", []))
    
    # Extract relationships using indices (NEW)
    relationships = self._parse_relationships_list(
        data.get("relations", []),
        entities  # Pass entities for index lookup
    )
    
    return entities, relationships

def _parse_relationships_list(
    self, 
    relations_data: list, 
    entities: List[ExtractedEntity]
) -> List[ExtractedRelationship]:
    """Parse relationships from JSON array using entity indices."""
    relationships = []
    
    for i, rel_data in enumerate(relations_data):
        try:
            rel = self._parse_relationship(rel_data, entities)
            relationships.append(rel)
        except Exception as e:
            logger.warning(f"Failed to parse relationship at index {i}: {e}")
            continue  # Skip malformed relationships
    
    logger.info(f"Parsed {len(relationships)} relationships")
    return relationships

def _parse_relationship(
    self, 
    data: dict, 
    entities: List[ExtractedEntity]
) -> ExtractedRelationship:
    """Parse single relationship from dict, storing entity INDICES (not resolved names).
    
    Args:
        data: Relationship dict with integer indices
        entities: List of entities (for validation only)
        
    Returns:
        ExtractedRelationship with stored indices
    """
    # Get indices (LLM returns integers)
    from_index = data.get("from_entity")
    to_index = data.get("to_entity")
    relation_type = data.get("relation_type") or data.get("type")
    
    # Validate indices present
    if from_index is None or to_index is None or relation_type is None:
        raise ValueError("Relationship missing required fields (from_entity, to_entity, type)")
    
    # Convert to int and validate range
    try:
        from_idx = int(from_index)
        to_idx = int(to_index)
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid entity index: {e}")
    
    if from_idx < 0 or from_idx >= len(entities):
        raise ValueError(f"from_entity index {from_idx} out of range (0-{len(entities)-1})")
    
    if to_idx < 0 or to_idx >= len(entities):
        raise ValueError(f"to_entity index {to_idx} out of range (0-{len(entities)-1})")
    
    # Optional fields
    confidence = float(data.get("confidence", 1.0))
    
    # Extract properties (evidence, etc.)
    properties = {
        k: v for k, v in data.items()
        if k not in ("from_entity", "to_entity", "relation_type", "type", "confidence")
    }
    
    # IMPORTANT: Store INDICES, not resolved names
    # This allows indices to remain valid after hooks modify entities in-place
    return ExtractedRelationship(
        from_index=from_idx,  # Store index for later resolution
        to_index=to_idx,
        relation_type=str(relation_type).upper(),  # Normalize to uppercase
        confidence=confidence,
        properties=properties
    )
```

### FR4: Index-Preserving Entity Processing

**Critical Requirement:** Maintain entity array indices through deduplication/normalization!

**The Challenge:**
- LLM returns relationships with **entity indices**: `{"from_entity": 0, "to_entity": 2}`
- Hooks modify entities (normalize names, merge duplicates)
- **Relationships must still find entities using the same indices after hooks run**

**Solution: In-Place Entity Modification**

The entity list must maintain **stable indices** throughout processing:

```python
# After parsing
entities = [
    ExtractedEntity(name="Knowledge Discovery", type="product"),      # Index 0
    ExtractedEntity(name="Platform Engineering", type="team"),        # Index 1
    ExtractedEntity(name="Python", type="technology")                 # Index 2
]

relationships = [
    ExtractedRelationship(from_index=0, to_index=1, type="MAINTAINED_BY"),
    ExtractedRelationship(from_index=0, to_index=2, type="BUILT_WITH")
]

# After hooks run (entities may be modified, but indices preserved)
entities = [
    ExtractedEntity(name="Knowledge Discovery", type="product"),      # Index 0 - maybe normalized
    ExtractedEntity(name="Platform Engineering", type="team"),        # Index 1 - maybe merged with another
    ExtractedEntity(name="Python", type="technology")                 # Index 2 - unchanged
]

# Relationships STILL reference indices 0, 1, 2
```

**Implementation Notes:**

1. **Parser stores indices in relationships:**
   ```python
   # Store index, not resolved name (see updated FR3)
   ExtractedRelationship(
       from_index=0,  # NOT from_entity="Knowledge Discovery"
       to_index=2,
       ...
   )
   ```

2. **Hooks operate in-place:**
   - Hooks receive `List[ExtractedEntity]`
   - Hooks modify entities at their indices
   - Hooks return the SAME list (modified)
   - **Never reorder or remove items**

3. **Relationship resolution happens AFTER hooks:**
   ```python
   # In orchestrator, after hooks complete
   for relation in relationships:
       from_entity = entities[relation.from_index]  # Get post-hook entity
       to_entity = entities[relation.to_index]
       
       # Now use from_entity.name and to_entity.name to create relationship
   ```

4. **Indices are transient:**
   - Indices only exist during document processing
   - NOT stored in Neo4j
   - Only used to map LLM relations → final entity data

### FR5: Orchestrator Changes

Update `_ingest_to_graph()` to process relationships **AFTER** entities are created:

```python
def _ingest_to_graph(
    self,
    doc: ParsedDocument,
    entities: List[ExtractedEntity],
    relationships: List[ExtractedRelationship]  # NEW parameter
) -> tuple:
    """
    Ingest document, entities, AND relationships into Neo4j.
    
    Returns:
        Tuple of (entities_created, relationships_created)
    """
    namespace = self.config.namespace
    entities_created = 0
    relationships_created = 0
    
    # 1. Create document (unchanged)
    self.document_repo.create_document(...)
    
    # 2. Create entities (unchanged)
    for entity in entities:
        try:
            self.entity_repo.create_entity(...)
            entities_created += 1
        except DuplicateEntityError:
            pass  # Already exists
        
        # Add MENTIONS relationship (unchanged)
        self.document_repo.add_mention(...)
        relationships_created += 1
    
    # 3. Create entity-to-entity relationships (NEW)
    for relation in relationships:
        # Resolve indices to entities (AFTER hooks have run)
        # Entities may have been normalized/deduplicated, but indices are stable
        try:
            from_entity = entities[relation.from_index]
            to_entity = entities[relation.to_index]
        except IndexError as e:
            logger.warning(
                f"Skipping relationship {relation.relation_type}: "
                f"invalid index ({e})"
            )
            continue
        
        # Look up entities in graph to get canonical names
        # (Hooks may have modified names, so we verify they exist)
        from_entity_data = self.entity_repo.get_entity(
            namespace=namespace,
            entity_type=from_entity.entity_type,
            name=from_entity.name
        )
        to_entity_data = self.entity_repo.get_entity(
            namespace=namespace,
            entity_type=to_entity.entity_type,
            name=to_entity.name
        )
        
        # Skip if either entity doesn't exist in graph
        if not from_entity_data or not to_entity_data:
            logger.warning(
                f"Skipping relationship {relation.relation_type}: "
                f"entity not found in graph ({from_entity.name} -> {to_entity.name})"
            )
            continue
        
        # Create relationship in graph using canonical names
        try:
            self.entity_repo.create_relationship(
                namespace=namespace,
                from_entity_type=from_entity.entity_type,
                from_entity_name=from_entity_data['name'],  # Canonical name from graph
                to_entity_type=to_entity.entity_type,
                to_entity_name=to_entity_data['name'],  # Canonical name from graph
                rel_type=relation.relation_type,
                confidence=relation.confidence,
                **relation.properties
            )
            relationships_created += 1
            logger.debug(
                f"Created relationship: {from_entity.name} -[{relation.relation_type}]-> {to_entity.name}"
            )
        except GraphError as e:
            logger.warning(f"Failed to create relationship: {e}")
            continue  # Skip failed relationships, don't abort
    
    return entities_created, relationships_created
```

### FR6: Update Pipeline Flow

Modify `_process_document()` to pass relationships through pipeline:

```python
def _process_document(self, doc: ParsedDocument) -> DocumentProcessingResult:
    # ... existing code ...
    
    # Extract entities AND relationships
    extraction_result = self._extract_entities(doc)
    
    entities = extraction_result.entities
    relationships = extraction_result.relationships  # NEW
    
    # Run hooks on entities (unchanged)
    if self.hook_registry.before_store_hooks:
        entities = self.hook_registry.run_before_store(...)
    
    # Ingest entities AND relationships
    if not self.config.dry_run:
        entities_created, relationships_created = self._ingest_to_graph(
            doc, 
            entities,
            relationships  # NEW parameter
        )
    
    # Update result with relationship count
    return DocumentProcessingResult(
        document_id=doc.doc_id,
        success=True,
        entities_found=len(entities),
        relationships_created=relationships_created,  # Updated count
        processing_time=...
    )
```

## Error Handling

### Missing Entity References
**Problem:** LLM references entity that wasn't extracted or doesn't exist in graph

**Solution:**
- Log warning with entity name/type
- Skip the relationship (don't abort pipeline)
- Track skipped relationships in statistics

### Malformed Relationship Data
**Problem:** LLM returns invalid relationship JSON

**Solution:**
- Parser logs warning and skips malformed relationship
- Continue processing other relationships
- Don't fail entire extraction

### Circular References
**Problem:** A→B and B→A relationships

**Solution:**
- Neo4j handles naturally (directed graph)
- No special handling needed

## Testing Requirements

### Unit Tests
- `tests/test_extractors/test_parser.py`
  - Parse relationships from valid JSON
  - Handle missing relationship fields gracefully
  - Handle empty relations array

- `tests/test_models/test_extraction.py`
  - Create `ExtractedRelationship` with valid data
  - Validate relationship data model

### Integration Tests
- `tests/test_pipeline/test_orchestrator.py`
  - Extract and store relationships end-to-end
  - Handle missing entity references
  - Verify relationship counts in statistics

- `tests/test_graph/test_entity_repo.py`
  - Verify relationship creation with properties
  - Test relationship deduplication (MERGE behavior)

### Test Data
Create `tests/test_data/llm_responses/relationships_response.json`:

```json
{
  "entities": [
    {"type_id": "product", "name": "Knowledge Discovery", "evidence": "KD helps users discover knowledge"},
    {"type_id": "technology", "name": "Python", "evidence": "Built with Python"},
    {"type_id": "engineering_team", "name": "Platform Team", "evidence": "Maintained by Platform team"}
  ],
  "relations": [
    {
      "from_entity": 0,
      "to_entity": 1,
      "type": "built_with",
      "evidence": "KD is built using Python"
    },
    {
      "from_entity": 0,
      "to_entity": 2,
      "type": "maintained_by",
      "evidence": "Maintained by Platform Engineering"
    }
  ]
}
```

##Files to Modify

1. **kg_forge/models/extraction.py**
   - Add `ExtractedRelationship` dataclass
   - Add `relationships` field to `ExtractionResult`

2. **kg_forge/extractors/parser.py**
   - Update `_extract_entities()` → return tuple
   - Add `_parse_relationships_list()`
   - Add `_parse_relationship()`

3. **kg_forge/pipeline/orchestrator.py**
   - Add `_resolve_entity_name()` method
   - Update `_ingest_to_graph()` signature and logic
   - Update `_process_document()` to handle relationships

4. **kg_forge/models/pipeline.py** (optional)
   - Add `total_relationships_skipped` to `PipelineStatistics`

## Success Criteria

1. ✅ Parser extracts relationships from LLM JSON
2. ✅ Relationships stored in Neo4j with proper entity resolution
3. ✅ Entity name normalization/deduplication works for relationships
4. ✅ Missing entity references logged as warnings (don't abort)
5. ✅ Integration tests verify end-to-end relationship creation
6. ✅ Pipeline statistics include relationship counts

## Future Enhancements (Out of Scope)

- Relationship confidence filtering (similar to entity confidence filtering)
- Relationship deduplication hooks
- Relationship validation against schema
- Bi-directional relationship inference
- Relationship property normalization

## References

- Spec 06: Data Pipeline (entity extraction flow)
- Spec 08: Entity Normalization (name normalization logic)
- Spec 09: Vector Deduplication (entity deduplication process)
- Neo4j Cypher: CREATE/MERGE relationship syntax
