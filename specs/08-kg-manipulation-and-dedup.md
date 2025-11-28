# Step 8: KG Manipulation & Deduplication (Human-in-the-Loop)

## Overview

Step 8 provides a repeatable, human-in-the-loop framework for detecting likely duplicate or related entities in the Knowledge Graph, allowing users to review and confirm merges/alias relationships, and keeping the graph clean and meaningful as ingest runs accumulate more content. This step builds on top of the existing ingest + schema (Steps 2–6) and uses hooks and/or dedicated commands for KG maintenance. Step 8 does NOT change the basic ontology (no new entity types), change ingest semantics for fresh data, or alter the core CLI foundation or rendering semantics.

## Scope

### In Scope

- Implement a **dedup & alias detection engine** that:
  - Runs over existing `:Entity` nodes in a given `namespace`
  - Uses multiple configurable heuristics to propose candidate groups:
    - Normalized name equality (leveraging existing `normalized_name` property)
    - Phonetic hashing (Soundex/Metaphone/Double Metaphone)
    - N-gram similarity (Jaccard on character trigrams)
    - Case-insensitive prefix/suffix matches for partial names
    - Configurable thresholds and scoring combinations
- Define a **canonical vs alias** representation for entity merges:
  - Choose one canonical entity per group using deterministic rules
  - Rewire all relationships from aliases to canonical entity
  - Mark aliases via `(:Entity)-[:ALIAS_OF]->(:Entity)` relationship
  - Preserve alias nodes for audit trail and future reference
- Implement **interactive review flows**:
  - Integrate with `--interactive` / `--biraj` flag from existing CLI infrastructure
  - Prompt users to accept/reject suggested merges with detailed explanations
  - Support batch approval/rejection operations for efficiency
- Provide **CLI commands** for deduplication workflow:
  - `kg-forge dedup-suggest`: Generate and display/save merge suggestions
  - `kg-forge dedup-review`: Interactive review of suggestion plans
  - `kg-forge dedup-apply`: Apply approved merge plans with transaction safety
  - Hook integration via `process_after_batch` for post-ingest cleanup
- Implement **configurable heuristics system**:
  - YAML-based configuration for similarity thresholds
  - CLI flags to override thresholds and enable/disable specific matchers
  - Extensible architecture for future matching strategies
- Logging and metrics tracking:
  - Candidate pairs/groups discovery statistics
  - Merge acceptance/rejection rates and reasons
  - Performance metrics for matching and merge operations
- Comprehensive testing:
  - Unit tests for matching heuristics and scoring logic
  - Integration tests for merge application semantics
  - CLI workflow tests for both interactive and batch modes

### Out of Scope

- Changing the core `:Doc` / `:Entity` node schema or relationship types
- Modifying ingest behavior for new documents (beyond leveraging cleaned graph)
- Full-blown MDM / golden-record system for complex organizational hierarchies
- Advanced machine-learning-based entity resolution models (beyond extensible interface)
- Web UI beyond CLI + potential HTML export of suggestions
- Cross-namespace deduplication (maintain namespace isolation)
- Real-time deduplication during ingest (focus on post-processing cleanup)
- Integration with external master data management systems

## Deduplication Model & Semantics

### Candidate Detection Model

**CandidateGroup Structure**:
```python
@dataclass
class CandidatePair:
    entity1_id: int
    entity2_id: int
    entity1_name: str
    entity2_name: str
    entity_type: str
    match_reasons: dict[str, Union[bool, float]]  # {"normalized_match": True, "phonetic_score": 0.9}
    combined_score: float
    suggested_canonical: int  # ID of suggested canonical entity

@dataclass
class CandidateGroup:
    canonical_entity: int
    alias_entities: list[int]
    entity_type: str
    match_scores: dict[int, float]  # entity_id -> score vs canonical
    group_confidence: float
```

### Merge Semantics

**Canonical Selection Rules**:
1. **Highest relationship degree** (most connected entity becomes canonical)
2. **Longest complete name** (prefer full names over abbreviated versions)
3. **Earliest creation timestamp** (`created_at` property as tiebreaker)
4. **Lexicographic ordering** of `entity_id` (final deterministic fallback)

**Merge Application Process**:
1. **Identify canonical entity** using selection rules above
2. **Rewire all relationships**:
   - All `(:Doc)-[:MENTIONS]->(alias)` become `(:Doc)-[:MENTIONS]->(canonical)`
   - All `(alias)-[:RELATION]->(other)` become `(canonical)-[:RELATION]->(other)`
   - All `(other)-[:RELATION]->(alias)` become `(other)-[:RELATION]->(canonical)`
3. **Create alias relationships**: `(alias)-[:ALIAS_OF]->(canonical)`
4. **Update alias properties**:
   - Set `canonical_id: <canonical_entity_id>`
   - Set `is_alias: true`
   - Preserve original `name` and other properties for audit trail

**Deduplication Memory**:
- Store merge decisions in `(:Entity)-[:ALIAS_OF]->(:Entity)` relationships
- Avoid re-suggesting pairs where one entity has `canonical_id` pointing to the other
- Track merge timestamps and reasons in relationship properties
- Support "undo" operations by reversing alias relationships (future enhancement)

**Idempotency Guarantees**:
- Re-running dedup on same data produces identical suggestions
- Applying same merge plan multiple times has no additional effect
- Each merge operation is atomic within Neo4j transaction boundaries

## Heuristics & Matching Engine

### Implemented Matching Strategies

**Normalization-Based Matching**:
- Leverage existing `normalized_name` property from Step 4 schema
- Exact equality on normalized names indicates strong duplicate candidate
- Score: `1.0` for exact match, `0.0` otherwise

**Phonetic Hashing**:
- Use **Double Metaphone** algorithm for robust phonetic matching
- Handle common name variations: "Catherine/Katherine", "Smith/Smyth"
- Compute phonetic hash on-the-fly during matching (not stored)
- Score: `1.0` for exact phonetic match, `0.8` for primary/secondary match

**N-gram Similarity**:
- Generate character trigrams from entity names
- Use **Jaccard similarity** coefficient: `|intersection| / |union|`
- Effective for typos, abbreviations: "Kubernetes" vs "K8s", "JavaScript" vs "JS"
- Score: Jaccard coefficient (0.0 to 1.0)

**Prefix/Suffix Matching**:
- Handle partial names: "James Earl Jones" contains "James Jones"
- Check if shorter name is prefix/suffix of longer name (after normalization)
- Minimum length threshold to avoid false positives on common short names
- Score: `0.7` for valid prefix/suffix match, `0.0` otherwise

**Abbreviation Detection**:
- Check if shorter name matches initials of longer name
- "Machine Learning Platform" matches "MLP"
- Case-insensitive with configurable minimum abbreviation length
- Score: `0.6` for valid abbreviation match, `0.0` otherwise

### Scoring & Thresholding

**Combined Scoring Formula**:
```python
combined_score = max(
    normalization_score,
    phonetic_score * 0.9,
    ngram_score * 0.8,
    prefix_score * 0.7,
    abbreviation_score * 0.6
)
```

**Configurable Thresholds**:
- `minimum_candidate_score: 0.6` (pairs below this threshold ignored)
- `strong_match_threshold: 0.8` (automatic suggestion for interactive review)
- `weak_match_threshold: 0.6` (requires manual review confirmation)
- Per-heuristic enable/disable flags
- Entity-type specific threshold overrides

**Configuration Format** (YAML):
```yaml
dedup:
  thresholds:
    minimum_candidate_score: 0.6
    strong_match_threshold: 0.8
    weak_match_threshold: 0.6
  heuristics:
    normalization: true
    phonetic: true
    ngram: true
    prefix_suffix: true
    abbreviation: true
  entity_type_overrides:
    EngineeringTeam:
      minimum_candidate_score: 0.7  # Stricter for team names
```

## Hook Integration vs Dedicated Commands

### Hook Integration Points

**process_after_batch Hook Enhancement**:
- After ingest completion in `--interactive` mode, automatically run dedup suggestions
- Present top-confidence matches for immediate review
- Allow users to approve quick wins without separate command execution
- Defer complex cases to dedicated dedup commands

**Optional process_before_store Hook**:
- Lightweight duplicate detection for new entities during ingest
- Check incoming entity against recent entities using fast heuristics
- Log potential duplicates for post-ingest review
- Avoid slowing ingest pipeline with expensive matching

### Dedicated Commands (Primary Interface)

**Dedup Suggestion Generation**:
```bash
kg-forge dedup-suggest --namespace default --entity-type Product,Team --min-score 0.7 --out suggestions.json
```

**Interactive Review Workflow**:
```bash
kg-forge dedup-review --plan suggestions.json --interactive
```

**Batch Merge Application**:
```bash
kg-forge dedup-apply --plan reviewed_suggestions.json --dry-run
kg-forge dedup-apply --plan reviewed_suggestions.json  # Apply approved merges
```

**Hook Integration Philosophy**:
- Hooks provide convenience and workflow integration
- Dedicated commands offer full control and auditability
- Users can choose their preferred workflow (inline vs batch)
- Both approaches use same underlying dedup engine

## CLI Design

### Core Commands

#### `kg-forge dedup-suggest`

Generate deduplication suggestions for review:

```bash
kg-forge dedup-suggest [OPTIONS]
```

**Options**:
- `--namespace TEXT`: Target namespace (default from config)
- `--entity-type TEXT`: Comma-separated entity types to analyze (default: all)
- `--min-score FLOAT`: Minimum similarity score threshold (default: 0.6)
- `--max-candidates INTEGER`: Maximum candidate pairs to generate (default: 1000)
- `--out PATH`: Save suggestions to JSON file (default: stdout)
- `--format [json|table]`: Output format for display

**Behavior**:
- Query all entities in namespace matching type filters
- Apply configured matching heuristics with specified thresholds
- Sort candidates by combined score (highest first)
- Output suggestions in specified format
- Non-interactive mode safe for automation and CI

#### `kg-forge dedup-review`

Interactively review and approve/reject suggestions:

```bash
kg-forge dedup-review --plan PATH [OPTIONS]
```

**Options**:
- `--plan PATH`: JSON file containing dedup suggestions (required)
- `--interactive`: Enable interactive review mode (default: false)
- `--auto-approve-above FLOAT`: Auto-approve matches above score threshold
- `--out PATH`: Save reviewed plan to file (default: overwrite input)

**Interactive Mode Behavior**:
- Present each candidate group with entity details and match reasons
- Show relationship counts and sample relationships for context
- Prompt: `[A]pprove / [R]eject / [S]kip / [Q]uit / [H]elp`
- Support bulk operations: approve all above threshold, reject all below threshold
- Track review progress and allow resuming interrupted sessions

#### `kg-forge dedup-apply`

Apply approved merge decisions to Knowledge Graph:

```bash
kg-forge dedup-apply --plan PATH [OPTIONS]
```

**Options**:
- `--plan PATH`: JSON file containing reviewed suggestions (required)
- `--dry-run`: Show what would be merged without applying changes
- `--batch-size INTEGER`: Number of merges per transaction (default: 10)

**Behavior**:
- Validate plan file format and entity existence
- Apply merges in transaction batches for safety
- Log detailed merge operations and affected relationship counts
- Report final statistics: entities merged, relationships rewired, errors

### Exit Codes

- `0`: Success (suggestions generated, reviews completed, merges applied)
- `1`: Configuration or validation errors (missing namespace, invalid thresholds)
- `2`: Input/output errors (cannot read plan file, cannot write suggestions)
- `3`: Neo4j connection or transaction errors
- `4`: Interactive session aborted by user

### Example Workflows

**Complete Dedup Workflow**:
```bash
# 1. Generate suggestions
kg-forge dedup-suggest --namespace team_docs --entity-type Product,Team --out suggestions.json

# 2. Review interactively
kg-forge dedup-review --plan suggestions.json --interactive --out reviewed_plan.json

# 3. Apply approved merges
kg-forge dedup-apply --plan reviewed_plan.json --dry-run  # Preview
kg-forge dedup-apply --plan reviewed_plan.json           # Execute
```

**Post-Ingest Cleanup**:
```bash
# After large ingest, clean up entities
kg-forge ingest --source ./confluence_export --namespace team_docs
kg-forge dedup-suggest --namespace team_docs --min-score 0.8 | kg-forge dedup-apply --plan -
```

## Project Structure

```
kg_forge/
├── dedup/
│   ├── __init__.py
│   ├── matcher.py              # Heuristic implementations and candidate generation
│   ├── model.py               # CandidatePair, CandidateGroup, DedupPlan data models
│   ├── scorer.py              # Scoring logic and threshold configuration
│   ├── apply.py               # Merge execution and transaction management
│   ├── config.py              # Dedup-specific configuration loading
│   └── heuristics/
│       ├── __init__.py
│       ├── normalization.py   # Normalized name matching
│       ├── phonetic.py        # Double Metaphone implementation
│       ├── ngram.py           # N-gram similarity calculation
│       ├── prefix_suffix.py   # Partial name matching
│       └── abbreviation.py    # Abbreviation detection logic
├── cli/
│   ├── dedup.py              # CLI command implementations
│   └── main.py              # Updated to include dedup command group
├── hooks/
│   └── dedup_integration.py  # Optional hook implementations for post-ingest dedup
└── utils/
    └── interactive.py        # Enhanced InteractiveSession for dedup workflows

tests/
├── test_dedup/
│   ├── __init__.py
│   ├── test_matcher_heuristics.py     # Individual heuristic correctness
│   ├── test_matcher_integration.py    # End-to-end matching pipeline
│   ├── test_scorer_thresholds.py      # Scoring and threshold logic
│   ├── test_apply_merges.py           # Merge application semantics
│   ├── test_canonical_selection.py    # Canonical entity selection rules
│   ├── test_dedup_cli_suggest.py      # Suggestion generation CLI
│   ├── test_dedup_cli_review.py       # Interactive review CLI
│   ├── test_dedup_cli_apply.py        # Merge application CLI
│   └── test_idempotency.py            # Ensuring operations are repeatable
├── test_cli/
│   └── test_dedup_integration.py      # Full workflow integration testing
└── data/
    └── dedup/
        ├── sample_duplicates.cypher   # Test graph with known duplicates
        ├── expected_suggestions.json  # Expected output for test cases
        └── merge_scenarios/           # Various merge test cases
            ├── simple_pair.json
            ├── complex_group.json
            └── edge_cases.json
```

## Dependencies

### New Runtime Dependencies

**String Similarity and Phonetics**:
```
# Phonetic hashing algorithms
metaphone>=0.6          # Double Metaphone implementation
# Alternative: jellyfish>=0.9.0 (includes multiple phonetic algorithms)

# String similarity metrics (optional, implement in-house if preferred)
textdistance>=4.2.0     # Comprehensive similarity metrics library
```

**Chosen Approach**: Use `metaphone` for phonetic hashing and implement n-gram similarity in-house to minimize dependencies.

### Existing Dependencies (Reused)

- **Neo4j Integration**: `neo4j>=5.0.0` from Step 4 for all graph operations
- **CLI Framework**: `click`, `rich` from Step 1 for command interface
- **Configuration**: `pyyaml`, `python-dotenv` from Step 1 for threshold configuration
- **Interactive Sessions**: Enhanced `InteractiveSession` class from Step 6

### Standard Library Usage

- `difflib` for sequence matching in prefix/suffix detection
- `hashlib` for deterministic entity ID hashing in canonical selection
- `json` for plan file serialization and deserialization
- `itertools` for efficient candidate pair generation

**Dependency Philosophy**:
- Prefer lightweight, focused libraries over heavyweight frameworks
- Implement simple algorithms in-house rather than adding dependencies
- Reuse existing project infrastructure maximally

## Implementation Details

### Entity Selection Strategy

**Stratified Matching Approach**:
- Group entities by `entity_type` to avoid cross-type false positives
- Within each type, create buckets by normalized name prefix (first 3 characters)
- Only compare entities within same bucket plus adjacent buckets
- Reduces matching complexity from O(N²) to approximately O(N log N)

**Filtering for Relevance**:
- Focus on entities with `degree >= 2` (connected to multiple documents/entities)
- Prioritize recently created entities (`created_at` within last ingest runs)
- Optional: filter by confidence score threshold from LLM extraction
- Configurable limits: max entities per type, max pairs per run

### Matching Pipeline Architecture

**Batch Processing Strategy**:
```python
def generate_candidates(entities: list[Entity], config: DedupConfig) -> list[CandidatePair]:
    # 1. Group entities by type and normalized name prefix
    buckets = create_similarity_buckets(entities)
    
    # 2. Generate pairs within and across adjacent buckets
    candidate_pairs = []
    for bucket_group in buckets:
        pairs = generate_pairs_in_bucket(bucket_group)
        candidate_pairs.extend(pairs)
    
    # 3. Apply all enabled heuristics to each pair
    scored_pairs = []
    for pair in candidate_pairs:
        scores = apply_all_heuristics(pair, config)
        if scores.combined_score >= config.minimum_threshold:
            scored_pairs.append(pair)
    
    # 4. Sort by score and apply limits
    return sorted(scored_pairs, key=lambda p: p.combined_score, reverse=True)[:config.max_candidates]
```

### Merge Execution Strategy

**Transaction Management**:
- Each candidate group merge is wrapped in single Neo4j transaction
- Batch multiple small merges (same entity type) into single transaction when safe
- Rollback on any failure within transaction boundary
- Log detailed transaction outcomes for audit

**Relationship Rewiring Algorithm**:
```python
def apply_merge(canonical_id: int, alias_ids: list[int], neo4j_client: Neo4jClient):
    with neo4j_client.session() as session:
        with session.begin_transaction() as tx:
            # 1. Collect all relationships involving alias entities
            alias_relationships = get_all_relationships(alias_ids, tx)
            
            # 2. Rewire each relationship to canonical entity
            for rel in alias_relationships:
                if rel.start_node in alias_ids:
                    create_relationship(canonical_id, rel.end_node, rel.type, rel.properties, tx)
                if rel.end_node in alias_ids:
                    create_relationship(rel.start_node, canonical_id, rel.type, rel.properties, tx)
                delete_relationship(rel.id, tx)
            
            # 3. Create alias relationships and update properties
            for alias_id in alias_ids:
                create_alias_relationship(alias_id, canonical_id, tx)
                update_alias_properties(alias_id, canonical_id, tx)
            
            tx.commit()
```

### Interactive Review Experience

**Rich Console Interface**:
- Use `rich` library for formatted tables showing candidate details
- Color-code match strength (green=strong, yellow=moderate, red=weak)
- Display side-by-side entity properties and relationship summaries
- Show match reason breakdown with individual heuristic scores

**Session State Management**:
- Save review progress to allow interruption and resumption
- Track user decisions (approve/reject/skip) with timestamps
- Support undo of recent decisions within session
- Generate summary statistics at session completion

### Performance Considerations

**Memory-Efficient Processing**:
- Stream entity data from Neo4j rather than loading entire namespace
- Process candidates in batches to avoid memory exhaustion on large graphs
- Use generators and iterators for candidate pair enumeration
- Configurable batch sizes for both matching and merge operations

**Caching Strategy**:
- Cache phonetic hashes and n-gram sets for entities during matching session
- Avoid recomputing expensive similarity metrics for same entity pairs
- Clear caches between different dedup runs to prevent stale data

## Testing Strategy

### Unit Tests

**Heuristic Correctness** (`test_matcher_heuristics.py`):
- Test each matching heuristic with known positive/negative examples:
  - Phonetic: "Smith"/"Smyth", "Catherine"/"Katherine" should match
  - N-gram: "Kubernetes"/"K8s" should have moderate similarity
  - Prefix: "James Earl Jones"/"James Jones" should match
  - Abbreviation: "Machine Learning Platform"/"MLP" should match
- Verify edge cases: empty strings, single characters, Unicode handling
- Test scoring formula combines heuristics correctly

**Threshold and Configuration** (`test_scorer_thresholds.py`):
- Verify threshold enforcement filters candidates appropriately
- Test configuration loading from YAML with various valid/invalid inputs
- Test CLI threshold overrides properly update loaded configuration
- Verify entity-type specific threshold overrides work correctly

**Canonical Selection** (`test_canonical_selection.py`):
- Test deterministic canonical selection with various entity combinations
- Verify tie-breaking rules produce consistent results
- Test selection with missing properties (degree, timestamps)
- Ensure selection algorithm is stable under entity reordering

### Integration Tests

**End-to-End Merge Application** (`test_apply_merges.py`):
- Create test graph with known duplicates across different entity types
- Apply specific merge scenarios and verify:
  - Canonical entity retains all original relationships
  - Alias entities have relationships properly rewired
  - `ALIAS_OF` relationships created correctly
  - Alias properties updated with canonical references
- Test transaction rollback on simulated Neo4j errors
- Verify idempotency: re-applying same merges has no effect

**CLI Workflow Integration** (`test_dedup_integration.py`):
- Test complete suggest → review → apply workflow using Docker Neo4j fixture
- Verify JSON plan file format consistency across commands
- Test error handling for corrupted or incompatible plan files
- Simulate interactive review decisions and verify correct application

### Interactive Testing Strategy

**Mock Interactive Sessions** (`test_dedup_cli_review.py`):
- Use test harness to simulate user input sequences ("y", "n", "s", "q")
- Verify interactive prompts display correct candidate information
- Test batch operations (approve all above threshold, etc.)
- Verify session state persistence and resumption functionality

**Manual Testing Guidelines**:
- Document specific test scenarios for manual verification
- Provide sample datasets with known duplicate patterns
- Include instructions for testing various interactive workflows
- Validate visual presentation and user experience quality

### Performance and Scalability Testing

**Large Graph Simulation**:
- Generate test graphs with 1K, 10K, 100K entities
- Measure matching performance and memory usage
- Verify batch processing prevents memory exhaustion
- Test configuration tuning for different graph sizes

**Concurrent Access Testing**:
- Ensure dedup operations are safe during concurrent read operations
- Test transaction isolation during merge applications
- Verify no deadlocks or race conditions in Neo4j transactions

## Success Criteria

Step 8 is considered complete when:

- [ ] **Accurate duplicate detection**: On test graphs with known duplicates, `kg-forge dedup-suggest` produces expected candidate groups with >90% precision and >85% recall
- [ ] **Correct merge application**: `kg-forge dedup-apply` correctly merges entities and rewires relationships in Neo4j:
  - Canonical entities retain all relationships from aliases
  - Alias entities marked with `ALIAS_OF` relationships and updated properties
  - No relationship data loss or corruption during merge operations
- [ ] **Interactive workflow usability**: End-to-end interactive review works for realistic scenarios:
  - Clear presentation of candidate details and match reasons
  - Intuitive approval/rejection interface with batch operations
  - Session persistence allows interruption and resumption
- [ ] **Configurable matching engine**: Heuristics and thresholds are configurable via YAML and CLI flags:
  - Individual heuristics can be enabled/disabled
  - Thresholds can be tuned for different entity types
  - Configuration changes produce expected behavior modifications
- [ ] **Transaction safety and idempotency**: All merge operations are atomic and repeatable:
  - Failed merges rollback cleanly without partial state
  - Re-running same dedup plan produces no additional changes
  - Concurrent operations do not cause data corruption
- [ ] **Integration compatibility**: Steps 2–7 continue to work correctly on deduplicated graphs:
  - Ingest operations work with alias relationships present
  - Query commands return appropriate results considering canonical entities
  - Render operations display cleaned graph structure appropriately
- [ ] **Performance scalability**: Matching and merge operations complete efficiently on realistic graph sizes:
  - 10K entity graphs complete suggestion generation in <60 seconds
  - Merge application handles 100+ merge operations in <30 seconds
  - Memory usage remains bounded during large graph processing
- [ ] **Test coverage and quality**: All dedup modules achieve >90% test coverage with comprehensive scenarios:
  - Unit tests cover all heuristic edge cases and configuration combinations
  - Integration tests validate end-to-end workflows and error handling
  - Performance tests establish baseline metrics and detect regressions

## Next Steps

Step 8 transforms KG Forge from a "one-shot ingest tool" into a maintainable, evolving graph that can be kept clean as content grows, building upon the ingest pipeline (Step 6) and enhancing the visualization capabilities (Step 7) with higher-quality, deduplicated data. Future enhancements can integrate more advanced matching techniques (embeddings-based similarity, ML-trained entity resolution models), export canonical/alias mappings back to entity definition files (Step 3) for improved future ingestion, and feed deduplication decisions into the planned Knowledge Enrichment SaaS pipeline for cross-organization learning. The human-in-the-loop framework established in Step 8 provides the foundation for scaling entity resolution to larger, more complex organizational knowledge graphs while maintaining data quality and user trust through transparent, auditable merge decisions.