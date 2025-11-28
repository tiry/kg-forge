# Step 7: Ingest Pipeline

## Overview

Step 7 implements the end-to-end ingest pipeline that orchestrates all previous components into a complete workflow. The pipeline discovers HTML files under a source folder, runs curation to produce canonical documents (Step 3), uses the LLM extraction pipeline (Step 6) with entity definitions and templates (Step 4), and writes `:Doc` and `:Entity` nodes and relationships into Neo4j according to the schema (Step 5). This is the first step that runs a full path from filesystem → LLM → graph, focusing on correctness, idempotency, and hooks integration (`process_before_store`, `process_after_batch`). Step 7 does NOT handle graph visualization (that's Step 8) and does NOT implement complex dedup/merge strategies beyond the simple merge keys defined in Step 5.

## Scope

### In Scope

- Implement the ingestion pipeline that:
  - Walks the `--source` directory to discover HTML files
  - Loads and curates HTML files into the document model (Step 2)
  - For each curated document/chunk, builds a prompt and calls the LLM extraction pipeline (Step 5)
  - Applies `process_before_store` hooks to the extracted metadata
  - Upserts `:Doc` and `:Entity` nodes in Neo4j and creates:
    - `(:Doc)-[:MENTIONS]->(:Entity)` relationships
    - Ontology-driven `(:Entity)-[:RELATION]->(:Entity)` relationships where applicable
  - Applies `process_after_batch` hook at the end of a batch or ingest run
- Implement full semantics for `kg-forge ingest` options:
  - `--source`, `--namespace`, `--dry-run`, `--refresh`, `--interactive/--biraj`
  - `--prompt-template`, `--model`
- Implement **content hashing** and **idempotent ingest**:
  - Compute MD5 of curated text per document
  - Skip re-import if hash unchanged (unless `--refresh` is set)
- Integrate LLM error-handling rules from Step 5 into batch ingest:
  - Per-document failures are skipped with logging
  - >10 consecutive failures abort the ingest with non-zero exit code
- Implement basic ingest metrics (number of docs processed, skipped, failed, entities created/merged)
- End-to-end tests using:
  - Fake LLM implementation from Step 5
  - Docker-based Neo4j fixture from Step 4

### Out of Scope

- Advanced deduplication or record-linkage logic beyond the simple `(namespace, entity_type, normalized_name)` merge key
- Complex ontology-inferred relationship creation (beyond what is directly specified in entity definitions)
- Graph visualization and rendering (Step 7)
- KE SaaS pipeline integration (future step)
- Multi-tenant orchestration or multi-namespace migrations (beyond using `--namespace`)
- Performance optimizations like parallel processing or bulk import strategies
- Advanced chunking strategies beyond 1 page = 1 chunk

## Pipeline Design

The ingest pipeline follows this sequence:

1. **Configuration Resolution**: Load settings from Step 1 and merge CLI options with precedence
2. **File Discovery**: Walk `--source` directory recursively, filtering for `.html` files with stable ordering
3. **Per-Document Processing**: For each HTML file:
   - Derive `doc_id` from relative path (without extension, normalized)
   - Extract `source_path`, apply `namespace` from config/CLI
   - Run HTML → curated text transformation using Step 2's document loader
   - Compute `content_hash` (MD5) over curated text content
   - Check Neo4j for existing `:Doc` with same `(namespace, doc_id, content_hash)`:
     - If found and `--refresh` is NOT set → skip document (log as "unchanged")
     - If not found or `--refresh` is set → continue processing
   - Call LLM extraction pipeline (Step 5) with:
     - Curated text chunk(s) as document content
     - Entity definitions template from Step 3
   - Receive `ExtractionResult` (`{"entities": [...]}`) or handle failures:
     - Apply retry & failure counter logic from Step 5
     - Skip individual failing documents while continuing batch
   - Run `process_before_store` hook with:
     - Original curated content (CuratedDocument object)
     - Extracted metadata (dict from LLM result)
     - Neo4j client instance
   - Write to Neo4j (if not `--dry-run`):
     - Upsert `:Doc` node with content hash and metadata
     - Upsert `:Entity` nodes for each extracted entity
     - Create `(:Doc)-[:MENTIONS]->(:Entity)` relationships with confidence scores
     - Create entity-entity relationships based on definitions
   - Accumulate metrics and entity records for batch processing
4. **Batch Completion**: After processing all documents:
   - Call `process_after_batch` hook with:
     - List of all entities created/updated in this run
     - Neo4j client instance
     - Interactive session if `--interactive/--biraj` is enabled
   - Log final metrics summary

### Batching Strategy

- **Transaction Boundaries**: Each document is processed in its own Neo4j transaction
- **Rollback Behavior**: Failed document writes are rolled back individually, processing continues
- **Batch Size**: No artificial batching - process documents as discovered (single-threaded in v1)
- **Memory Management**: Process documents sequentially to avoid loading all content into memory

## Hook Integration

Hooks are implemented in `kg_forge/hooks.py` with a registry pattern:

### Hook Registry

```python
class HookRegistry:
    def __init__(self):
        self._before_store_hooks: list[Callable] = []
        self._after_batch_hooks: list[Callable] = []
    
    def register_before_store(self, func: Callable):
        """Register process_before_store hook"""
        
    def register_after_batch(self, func: Callable):
        """Register process_after_batch hook"""
```

### Hook Signatures

- **process_before_store**:
  ```python
  def process_before_store(content: CuratedDocument, metadata: dict, kg_client: Neo4jClient) -> dict:
      """Modify metadata before storing in graph. Return modified metadata dict."""
  ```

- **process_after_batch**:
  ```python
  def process_after_batch(entities: list[EntityRecord], kg_client: Neo4jClient, interactive: InteractiveSession | None) -> None:
      """Process all entities after batch completion. No return value."""
  ```

### Hook Behavior

- **Optional Execution**: Hooks are optional - default implementations do nothing
- **Error Handling**: Hook exceptions are logged as warnings and do not abort the pipeline
- **Hook Discovery**: Hooks are auto-registered by importing modules in `kg_forge/hooks/` directory
- **Interactive Mode**: `InteractiveSession` is only available when `--interactive/--biraj` flag is set

## Neo4j Write Behaviour

Step 6 uses the Neo4j schema from Step 4 with these semantics:

### Node Creation and Merging

- **`:Doc` nodes**:
  - Merge key: `(namespace, doc_id)`
  - Always update: `content_hash`, `source_path`, `last_processed_at`
  - Create if not exists, update properties if exists

- **`:Entity` nodes**:
  - Merge key: `(namespace, entity_type, normalized_name)`
  - Update properties: `name`, `last_seen_at`, `confidence` (if higher)
  - Create if not exists, update properties if exists

### Relationship Creation

- **`:MENTIONS` relationships**:
  - Link `(:Doc)-[:MENTIONS]->(:Entity)` for each extracted entity
  - Properties: `confidence` (from LLM extraction result)
  - Create new relationship for each ingest (no deduplication)

- **Entity-entity relationships**:
  - Derived from entity definitions' `Relations` section where both entities exist
  - Create relationships like `(:Entity)-[:COLLABORATES_WITH]->(:Entity)` based on definitions
  - Only create if both source and target entities were extracted in current or previous runs

### Flag Semantics

- **Dry Run (`--dry-run`)**:
  - Run full pipeline including LLM calls and hook execution
  - Skip all Neo4j write operations (create, update, relationship creation)
  - Log what writes would have occurred at INFO level
  - Useful for testing pipeline without affecting database

- **Refresh (`--refresh`)**:
  - Ignore content hash comparison - always reprocess documents
  - Useful when entity definitions, prompt templates, or LLM model changes
  - Does not delete existing data - only updates/creates

### Transaction Strategy

- **Per-Document Transactions**: Each document is processed in its own transaction
- **Rollback on Failure**: Database errors cause transaction rollback for that document only
- **Continue on Failure**: Failed document writes are logged, processing continues with next document
- **Batch Hooks**: `process_after_batch` runs in separate transaction after all documents processed

## CLI Behaviour (`kg-forge ingest`)

The `kg-forge ingest` command implements the complete ingest pipeline:

```bash
kg-forge ingest --source <path> [options]
```

### Arguments and Options

- `--source PATH` (required): Root directory containing HTML files to process
- `--namespace TEXT` (optional): Namespace for this ingest run (default from config)
- `--dry-run` (flag): Run pipeline without writing to Neo4j
- `--refresh` (flag): Reprocess all documents ignoring content hash
- `--interactive` / `--biraj` (flag): Enable interactive mode for hooks
- `--prompt-template PATH` (optional): Override default prompt template file
- `--model TEXT` (optional): Override LLM model name from config
- `--max-docs INTEGER` (optional): Limit number of documents processed (for debugging)

### Command Behavior

**Progress and Logging**:
- Display file discovery progress with total count
- Show per-document processing status (processed/skipped/failed)
- Log LLM extraction results and Neo4j write operations
- Display final metrics summary:
  - Total files discovered
  - Documents processed, skipped (unchanged), failed
  - Entities created, updated
  - Total processing time

**Configuration Precedence**:
- Follow Step 1 precedence: YAML config < environment variables < CLI arguments
- Validate required configuration (Neo4j connection, entity definitions path)
- Support `--fake-llm` flag from Step 5 for testing

**Exit Codes**:
- `0`: Success (even if some documents skipped due to unchanged content hash)
- `1`: Configuration or validation errors
- `2`: LLM consecutive failure threshold exceeded (>10 failures)
- `3`: Critical Neo4j connection or schema errors

### Example Usage

```bash
# Basic ingest with default configuration
kg-forge ingest --source ./confluence_export

# Dry run to test without database writes
kg-forge ingest --source ./test_data --dry-run --fake-llm

# Refresh all documents with custom model
kg-forge ingest --source ./docs --refresh --model anthropic.claude-3-sonnet

# Interactive mode with custom namespace
kg-forge ingest --source ./export --namespace "team_docs" --interactive

# Debug mode with document limit
kg-forge ingest --source ./large_export --max-docs 10 --dry-run
```

## Project Structure

```
kg_forge/
├── ingest/
│   ├── __init__.py
│   ├── pipeline.py           # Core IngestPipeline class and orchestration
│   ├── hooks.py             # Hook registry and default implementations
│   ├── metrics.py           # IngestMetrics class for tracking statistics
│   └── filesystem.py        # File discovery and path utilities
├── cli/
│   ├── ingest.py            # CLI command implementation
│   └── main.py             # Updated to include ingest command
├── hooks/
│   ├── __init__.py
│   └── examples/
│       ├── __init__.py
│       ├── metadata_enricher.py  # Example process_before_store hook
│       └── batch_reporter.py     # Example process_after_batch hook
└── utils/
    ├── hashing.py           # Content hash utilities
    └── interactive.py       # InteractiveSession class for --biraj mode

tests/
├── test_ingest/
│   ├── __init__.py
│   ├── test_ingest_single_doc.py    # Single document processing
│   ├── test_ingest_idempotency.py   # Hash-based skipping behavior
│   ├── test_ingest_dry_run.py       # Dry run mode validation
│   ├── test_ingest_error_handling.py # LLM failures and recovery
│   ├── test_ingest_hooks.py         # Hook integration testing
│   ├── test_ingest_metrics.py       # Metrics collection and reporting
│   └── test_filesystem.py          # File discovery utilities
├── test_cli/
│   └── test_ingest_cli.py           # End-to-end CLI command testing
└── data/
    └── html/
        ├── sample_space/
        │   ├── page1.html           # Simple Confluence export
        │   ├── page2.html           # Page with multiple entities
        │   └── nested/
        │       └── page3.html       # Nested directory structure
        └── malformed/
            └── broken.html          # Invalid HTML for error testing
```

## Dependencies

Step 6 reuses existing dependencies without introducing new runtime requirements:

### Existing Dependencies

- **HTML Processing**: `beautifulsoup4` and `lxml` from Step 2
- **Neo4j Integration**: `neo4j>=5.0.0` from Step 4  
- **LLM Integration**: `llama-index-llms-bedrock`, `boto3` from Step 5
- **Configuration**: `pyyaml`, `python-dotenv` from Step 1
- **CLI Framework**: `click`, `rich` from Step 1

### Standard Library Usage

- `hashlib` for MD5 content hashing
- `pathlib` for filesystem operations
- `os.walk()` for directory traversal
- `json` for metadata serialization

### Test Dependencies

- **Docker Integration**: Reuse existing Neo4j test fixtures from Step 4
- **File Fixtures**: Sample HTML files stored in `tests/data/html/`
- **Mock Objects**: Use existing patterns from Steps 2-5 for component isolation

No heavy new dependencies are introduced - Step 6 focuses on orchestration of existing components.

## Implementation Details

### Filesystem Traversal

**File Discovery Algorithm**:
- Use `os.walk()` for recursive directory traversal
- Filter files by `.html` extension (case-insensitive)
- Sort files alphabetically for reproducible processing order
- Generate `doc_id` from relative path: remove extension, normalize separators, lowercase

**Path Handling**:
```python
def derive_doc_id(file_path: Path, source_root: Path) -> str:
    """Convert file path to doc_id: relative/path/file -> relative_path_file"""
    relative_path = file_path.relative_to(source_root)
    return str(relative_path.with_suffix('')).replace(os.sep, '_').lower()
```

### Content Hashing Strategy

**Hash Computation**:
- Generate MD5 hash of curated text content (not raw HTML)
- Include metadata like title, extracted text, but exclude timestamps
- Store hash in `:Doc` node `content_hash` property for comparison

**Idempotency Logic**:
```python
def should_process_document(doc_id: str, content_hash: str, namespace: str, refresh: bool) -> bool:
    """Check if document needs processing based on content hash"""
    if refresh:
        return True
    
    existing = neo4j_client.get_document(namespace, doc_id)
    return existing is None or existing.content_hash != content_hash
```

### Chunking Strategy

**Initial Implementation**:
- 1 HTML file = 1 document = 1 chunk (as per architecture seeds)
- Future evolution point for larger documents or section-based chunking
- Document model from Step 2 supports multiple chunks per document

### Metrics Collection

**IngestMetrics Class**:
```python
@dataclass
class IngestMetrics:
    files_discovered: int = 0
    docs_processed: int = 0  
    docs_skipped: int = 0    # Due to unchanged content hash
    docs_failed: int = 0     # Due to LLM or Neo4j errors
    entities_created: int = 0
    entities_updated: int = 0
    processing_time: float = 0.0
```

**Logging Strategy**:
- INFO: Progress updates, successful operations, final metrics
- WARNING: Skipped documents, recoverable failures
- ERROR: LLM failures, Neo4j write errors
- DEBUG: Detailed pipeline steps, hook execution

### Interactive Mode

**InteractiveSession**:
- Available only when `--interactive/--biraj` flag is set
- Passed to `process_after_batch` hook for user interaction
- Supports simple terminal-based prompts and confirmations
- Example use cases: manual entity validation, batch approval

**Implementation Assumptions**:
- Ingest pipeline is single-threaded in v1 for simplicity
- LLM calls are sequential (no parallel processing)
- Neo4j writes use individual transactions per document
- Hook execution is synchronous and blocking

## Testing Strategy

### End-to-End Test Infrastructure

**Test Environment Setup**:
- Docker-based Neo4j fixture from Step 4 (isolated test database)
- Fake LLM implementation from Step 5 (deterministic responses)
- Sample HTML files in `tests/data/html/` (realistic Confluence exports)
- Temporary directories for source path testing

### Core Test Scenarios

**Happy Path Testing** (`test_ingest_single_doc.py`):
- Process single HTML file through complete pipeline
- Verify `:Doc` node creation with correct properties
- Verify `:Entity` node creation for extracted entities
- Verify `:MENTIONS` relationships with confidence scores
- Assert metrics tracking (1 processed, 0 skipped, N entities created)

**Idempotency Testing** (`test_ingest_idempotency.py`):
- Run ingest twice on identical HTML content
- First run: creates nodes and relationships
- Second run without `--refresh`: skips processing (0 processed, 1 skipped)
- Verify no duplicate nodes or relationships created
- Test `--refresh` flag forces reprocessing despite unchanged content

**Dry Run Testing** (`test_ingest_dry_run.py`):
- Run complete pipeline with `--dry-run` flag
- Verify LLM calls are made and hooks are executed
- Assert zero writes to Neo4j database
- Verify logging shows "would create" messages for intended operations

**Error Handling Testing** (`test_ingest_error_handling.py`):
- Simulate LLM parse failures using fake LLM malformed responses
- Verify individual document failures are logged and skipped
- Test consecutive failure counter and abort behavior (>10 failures)
- Verify Neo4j write failures cause transaction rollback but continue processing

**Hook Integration Testing** (`test_ingest_hooks.py`):
- Register test hooks that modify metadata and track batch entities
- Verify `process_before_store` can alter entity extraction results
- Verify `process_after_batch` receives complete entity list
- Test hook exception handling (logged but doesn't abort pipeline)

### Test Isolation and CI

**Database Isolation**:
- Each test uses unique namespace (e.g., `test_namespace_12345`)
- Test fixtures clean up created nodes after test completion
- No shared state between test runs

**CI Configuration**:
- All tests use fake LLM only (no real Bedrock API calls)
- Docker Neo4j containers managed by test fixtures
- Environment variable `KG_FORGE_TEST_MODE=true` enables test-specific behaviors
- Coverage target: >90% for ingest module components

**Performance Testing**:
- Measure processing time for batches of 10, 50, 100 documents
- Memory usage monitoring for large document sets
- Baseline metrics for regression detection

## Success Criteria

Step 6 is considered complete when:

- [ ] `kg-forge ingest --source tests/data/html --fake-llm` with Docker Neo4j:
  - Discovers and processes all HTML files in test data
  - Creates appropriate `:Doc` and `:Entity` nodes according to schema
  - Establishes `:MENTIONS` relationships with confidence scores
  - Logs processing metrics and exits with code 0
- [ ] **Idempotent behavior**: Re-running ingest on unchanged files skips processing (verified by metrics: 0 processed, N skipped)
- [ ] **Refresh semantics**: `--refresh` flag forces reprocessing despite unchanged content hash
- [ ] **Dry run functionality**: `--dry-run` executes full pipeline without Neo4j writes, logs intended operations
- [ ] **Hook integration**: Custom `process_before_store` and `process_after_batch` hooks are called at correct pipeline points
- [ ] **Error resilience**: LLM failures skip individual documents, >10 consecutive failures abort with non-zero exit code
- [ ] **Configuration integration**: CLI options override config file values following Step 1 precedence rules
- [ ] **Metrics accuracy**: Processing statistics (docs processed/skipped/failed, entities created) are correctly tracked and reported
- [ ] **No API changes**: Steps 2-5 components integrate without modification (composition, not modification)
- [ ] **Test coverage**: Ingest module achieves >90% test coverage with comprehensive end-to-end scenarios
- [ ] **CLI usability**: Command help text, error messages, and progress logging provide clear user experience

## Next Steps

Step 6 provides the fully-populated Knowledge Graph based on Confluence HTML exports by orchestrating the HTML parsing (Step 2), entity extraction (Step 5), and Neo4j storage (Step 4) into a complete ingest workflow. Step 7 will leverage this populated graph to implement visualization and advanced exploration capabilities (`kg-forge render` and enhanced `kg-forge query` commands), enabling users to discover insights and relationships within their imported Confluence content. The robust ingest pipeline established in Step 6 ensures that the graph contains high-quality, structured data ready for visualization and complex querying operations.