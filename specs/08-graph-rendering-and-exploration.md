# Step 8: Graph Rendering & Exploration

## Overview

Step 8 provides a way to visually explore the Knowledge Graph by querying a subgraph from Neo4j (filtered by namespace and optional criteria) and generating a self-contained HTML file with an interactive vis.js visualization. This enables users to discover insights and relationships within their imported Confluence content through an intuitive graph interface. Step 8 does NOT change how ingest/LLM work (no new writes to Neo4j), modify the ontology or schema, implement a full-blown web app (just static HTML + JS visualization), or handle advanced analytics (that remains separate).

## Scope

### In Scope

- Implementing a **subgraph selection strategy**:
  - Select seed nodes (e.g. all docs in a namespace, or a specific doc/entity)
  - Traverse up to `--depth` hops from seed nodes
  - Limit to `--max-nodes` while maintaining graph connectivity as much as possible
  - Support deterministic ordering for reproducible graph generation
- Implementing a **Neo4j query layer** for rendering:
  - Cypher queries to fetch nodes and relationships filtered by `namespace`
  - Optional filters (e.g. node types, doc IDs, entity types, specific entity names)
  - BFS traversal with configurable depth limits
- Implementing an **HTML/JS generator**:
  - Create static HTML file with embedded neovis.js configuration and pre-fetched data
  - Style nodes and relationships (colors, labels, tooltips) based on schema
  - Self-contained output requiring no live Neo4j connection
- Implementing the `kg-forge render` CLI command with:
  - `--out`, `--depth`, `--max-nodes`, `--namespace` options
  - Seed specification options (`--seed-doc-id`, `--seed-entity` + `--entity-type`)
  - Optional entity type filters (`--include-types`, `--exclude-types`)
- Unit & integration tests:
  - Verify correct Cypher queries and parameters for subgraph selection
  - Verify HTML includes required JS config and serialized graph data
  - Test depth limits, node limits, and filtering behavior

### Out of Scope

- Running a persistent web server or SPA frontend
- Modifying ingest or LLM extraction logic
- Advanced layout algorithms beyond what neovis.js provides
- Exporting to formats other than HTML (e.g. PNG/PDF) in this step
- Fine-grained per-user permissions (assume trusted local usage)
- Real-time graph updates or live Neo4j connections from browser
- Complex graph analytics or centrality calculations
- Interactive editing of graph structure

## Rendering Requirements

### Subgraph Selection Strategy

**Default Behavior (No Seeds)**:
- Select representative subgraph from namespace:
  - Pick top 10 documents by `last_processed_at` (most recently ingested)
  - Include all entities mentioned by these documents
  - If under `--max-nodes`, expand to include entities' relationships
- Fallback for empty namespace: return empty graph with informative message

**Seed-Based Selection**:
- `--seed-doc-id <id>`: Start BFS from specified `:Doc` node
- `--seed-entity "<name>" --entity-type <type>`: Start BFS from matching `:Entity` node
- Multiple seeds: Union of reachable nodes from all seed starting points

**Depth Traversal**:
- Use BFS from seed nodes up to `--depth` hops
- Traverse relationship types: `:MENTIONS`, entity-entity relations (`:WORKS_ON`, `:COLLABORATES_WITH`, etc.)
- Include both directions of relationships for complete connectivity

**Node Limit Enforcement**:
- Order nodes by: seed nodes first, then by hop distance, then by node degree (most connected first)
- Cut off when `--max-nodes` reached, preferring to keep complete connected components
- Log truncation information including final node/relationship counts

### Visual Mapping Rules

**Node Styling**:
- `:Doc` nodes: Blue rectangles with `doc_id` as primary label
- `:Entity` nodes: Colored circles based on entity type:
  - `Product`: Green circles
  - `EngineeringTeam`: Orange circles  
  - `Technology`: Purple circles
  - `Component`: Gray circles
  - Default entity: Light blue circles
- Node size based on degree (number of connections)
- Tooltip shows all node properties (`name`, `namespace`, `confidence`, etc.)

**Relationship Styling**:
- `:MENTIONS`: Thin gray arrows from docs to entities
- Entity-entity relationships: Colored arrows with relationship type as label
  - `WORKS_ON`: Green arrows
  - `COLLABORATES_WITH`: Blue arrows
  - `USES`: Purple arrows
  - Default: Black arrows

**Interactive Features**:
- Zoom and pan navigation
- Click node to highlight neighbors
- Hover to show detailed property tooltips
- Double-click to center view on node

## Neo4j Query Layer

### Query Patterns

The renderer uses these Cypher query patterns:

**Seed Node Resolution**:
```cypher
// Find doc seed
MATCH (d:Doc {namespace: $namespace, doc_id: $doc_id}) RETURN d

// Find entity seed  
MATCH (e:Entity {namespace: $namespace, entity_type: $entity_type, name: $name}) RETURN e
```

**Subgraph Expansion**:
```cypher
// BFS expansion from seeds up to specified depth
MATCH p = (seed)-[*1..$depth]-(connected)
WHERE seed.namespace = $namespace AND connected.namespace = $namespace
RETURN nodes(p), relationships(p)
```

**Filtering and Limits**:
- Apply `--include-types` / `--exclude-types` filters in WHERE clauses
- Order results deterministically by node ID for reproducible truncation
- Limit to `--max-nodes` in application layer after Cypher execution

### Python Query Abstraction

**GraphQuery Class** (`kg_forge/render/graph_query.py`):
```python
@dataclass
class NodeRecord:
    id: int
    labels: list[str]
    properties: dict[str, Any]

@dataclass  
class RelationshipRecord:
    id: int
    start_node: int
    end_node: int
    type: str
    properties: dict[str, Any]

@dataclass
class GraphData:
    nodes: list[NodeRecord]
    relationships: list[RelationshipRecord]
    
class GraphQuery:
    def get_subgraph(self, namespace: str, seeds: list[dict], 
                     depth: int, max_nodes: int, 
                     include_types: list[str] = None,
                     exclude_types: list[str] = None) -> GraphData:
        """Retrieve filtered subgraph from Neo4j"""
```

**Error Handling**:
- Missing namespace: Return empty graph with warning
- Invalid seeds: Log warning, continue with valid seeds only
- Neo4j connection errors: Raise with clear user message
- Empty results: Return empty graph with informative message

## HTML & neovis.js Integration

### HTML Template Structure

**Static HTML Generation**:
```html
<!DOCTYPE html>
<html>
<head>
    <title>KG Forge - Graph Visualization</title>
    <script src="https://unpkg.com/neovis.js@2.0.2"></script>
    <style>/* Basic styling */</style>
</head>
<body>
    <div id="viz" style="width: 100%; height: 100vh;"></div>
    <script>
        // Embedded graph data and configuration
        const graphData = {{GRAPH_DATA_JSON}};
        const config = {{NEOVIS_CONFIG_JSON}};
        
        // Initialize visualization
        const viz = new NeoVis.default(config);
        viz.renderWithCypher("RETURN 1"); // Trigger with pre-loaded data
    </script>
</body>
</html>
```

### neovis.js Configuration

**Pre-fetched Data Mode**:
- Embed complete `GraphData` as JSON in HTML
- Configure neovis.js to use embedded data instead of live Neo4j connection
- No credentials or connection strings in generated HTML

**Visual Configuration**:
```javascript
const config = {
    container_id: "viz",
    server_url: null, // Use embedded data mode
    server_user: null,
    server_password: null,
    labels: {
        "Doc": {
            "caption": "doc_id",
            "size": "pagerank",
            "community": "community",
            "font": {color: "white"},
            "color": "#1f77b4"
        },
        "Entity": {
            "caption": "name", 
            "size": "degree",
            "color": "#ff7f0e"
        }
    },
    relationships: {
        "MENTIONS": {
            "thickness": "weight",
            "caption": false,
            "color": "#cccccc"
        }
    },
    initial_cypher: null // Use embedded data
};
```

**Security Considerations**:
- No Neo4j credentials embedded in HTML
- Graph data is already filtered by namespace during query
- HTML is safe to share (contains only visualization data, no secrets)
- Recommend serving from local filesystem or trusted web server

## CLI Integration

### Command Interface

```bash
kg-forge render [OPTIONS]
```

**Core Options**:
- `--namespace TEXT`: Namespace to render (default from config)
- `--out PATH`: Output HTML file path (default: `graph.html`)  
- `--depth INTEGER`: Maximum traversal depth from seeds (default: 2)
- `--max-nodes INTEGER`: Maximum nodes in visualization (default: 200)

**Seed Selection**:
- `--seed-doc-id TEXT`: Start from specific document ID
- `--seed-entity TEXT`: Entity name to use as seed (requires `--entity-type`)
- `--entity-type TEXT`: Entity type for `--seed-entity` (Product, Team, etc.)

**Filtering Options**:
- `--include-types TEXT`: Comma-separated entity types to include (e.g. "Product,Team")
- `--exclude-types TEXT`: Comma-separated entity types to exclude

### Usage Examples

```bash
# Render default subgraph for namespace
kg-forge render --namespace "team_docs"

# Start from specific document
kg-forge render --seed-doc-id "confluence_page_123" --depth 3

# Focus on specific entity and its connections
kg-forge render --seed-entity "Platform Engineering" --entity-type "EngineeringTeam"

# Filter to only show products and teams
kg-forge render --include-types "Product,EngineeringTeam" --max-nodes 100

# Custom output location with increased depth
kg-forge render --out "./reports/knowledge_graph.html" --depth 4
```

### Command Behavior

**Progress and Logging**:
- Log subgraph query execution with timing
- Report nodes and relationships counts before and after limits applied
- Show output file path and size
- Warn about truncation when `--max-nodes` limit reached

**Exit Codes**:
- `0`: Success (HTML file generated)
- `1`: Configuration errors (invalid namespace, missing Neo4j connection)
- `2`: Query errors (invalid seeds, empty results)
- `3`: File system errors (cannot write output file)

**Error Handling**:
- Missing seeds: Log warning, fall back to default selection
- Empty namespace: Generate empty visualization with helpful message
- Neo4j connection failure: Clear error message with troubleshooting hints

## Project Structure

```
kg_forge/
├── render/
│   ├── __init__.py
│   ├── graph_query.py        # Neo4j subgraph retrieval and filtering
│   ├── html_builder.py       # HTML template generation with embedded data
│   ├── style_config.py       # Visual styling configuration for node/edge types
│   └── templates/
│       └── graph.html.j2     # Jinja2 template for generated HTML
├── cli/
│   ├── render.py            # CLI command implementation  
│   └── main.py             # Updated to include render command group
└── config/
    └── settings.py         # No changes needed (reuses existing config)

tests/
├── test_render/
│   ├── __init__.py
│   ├── test_graph_query_basic.py      # Basic subgraph selection logic
│   ├── test_graph_query_limits.py     # Depth and node limit enforcement
│   ├── test_graph_query_seeds.py      # Seed resolution and BFS expansion
│   ├── test_html_builder_structure.py # HTML structure and embedded data
│   ├── test_html_builder_styles.py    # Visual configuration generation
│   └── test_style_config.py           # Style mapping logic
├── test_cli/
│   └── test_render_cli.py             # End-to-end CLI command testing
└── data/
    └── render_fixtures/
        ├── sample_graph.cypher        # Test graph setup script
        └── expected_output.html       # Baseline HTML for comparison
```

## Dependencies

### Runtime Dependencies

**Template Engine**:
```
jinja2>=3.0.0  # For HTML template generation
```

**Existing Dependencies** (No Changes):
- Neo4j Python driver from Step 4 for graph queries
- Click and Rich from Step 1 for CLI interface  
- Configuration system from Step 1 for namespace defaults

### Frontend Dependencies (CDN)**:
- **neovis.js**: Loaded via CDN (`https://unpkg.com/neovis.js@2.0.2`)
- **No Python packaging** of JavaScript libraries
- **No bundling** required - keep HTML generation simple

### Development/Test Dependencies

**Existing Test Infrastructure**:
- Docker Neo4j fixture from Step 4 for integration tests
- Pytest framework with existing patterns
- Mock objects for unit testing query logic

**No Heavy New Dependencies**:
- Avoid graph processing libraries (NetworkX, etc.)
- Avoid complex templating beyond Jinja2
- Leverage neovis.js capabilities instead of custom visualization

## Implementation Details

### Subgraph Selection Algorithm

**Deterministic Node Ordering**:
```python
def order_nodes_for_limit(nodes: list[NodeRecord], seeds: list[NodeRecord]) -> list[NodeRecord]:
    """Order nodes to prioritize important ones before applying max_nodes limit"""
    # 1. Seed nodes first (preserve user intent)
    # 2. Sort by hop distance from seeds (closer nodes first) 
    # 3. Sort by node degree (highly connected nodes first)
    # 4. Sort by node ID for deterministic behavior
```

**Connected Component Preservation**:
- When approaching `--max-nodes` limit, prefer keeping complete connected components
- Avoid creating isolated nodes by checking relationship connectivity
- Log information about which nodes/components were excluded

### Graph Data Serialization

**JSON Structure for Embedding**:
```javascript
{
    "nodes": [
        {
            "id": 123,
            "labels": ["Doc"],
            "properties": {
                "doc_id": "page_456", 
                "namespace": "team_docs",
                "content_hash": "abc123..."
            }
        }
    ],
    "relationships": [
        {
            "id": 789,
            "startNode": 123,
            "endNode": 456, 
            "type": "MENTIONS",
            "properties": {"confidence": 0.92}
        }
    ]
}
```

**Property Filtering**:
- Include essential properties: `id`, `name`, `doc_id`, `entity_type`, `namespace`
- Exclude large properties: `content`, `curated_text`
- Include relationship properties: `confidence`, custom relation properties
- Limit property string lengths to keep payload manageable

### Style Configuration System

**Configurable Styling** (`style_config.py`):
```python
DEFAULT_STYLES = {
    "node_styles": {
        "Doc": {"color": "#1f77b4", "shape": "box", "font": {"color": "white"}},
        "Entity:Product": {"color": "#2ca02c", "shape": "dot"},
        "Entity:EngineeringTeam": {"color": "#ff7f0e", "shape": "dot"},
        "Entity": {"color": "#d62728", "shape": "dot"}  # fallback
    },
    "relationship_styles": {
        "MENTIONS": {"color": "#cccccc", "width": 1},
        "WORKS_ON": {"color": "#2ca02c", "width": 2},
        "COLLABORATES_WITH": {"color": "#1f77b4", "width": 2}
    }
}
```

**Extension Points**:
- Easy to add new entity types with custom styles
- Support for conditional styling based on properties (e.g., confidence levels)
- Configurable via YAML config file in future versions

### Logging and Metrics

**Structured Logging**:
```python
logger.info("Starting subgraph query", extra={
    "namespace": namespace,
    "seeds": len(seeds),
    "depth": depth,
    "max_nodes": max_nodes
})

logger.info("Subgraph extracted", extra={
    "nodes_found": len(nodes),
    "relationships_found": len(relationships), 
    "nodes_after_limit": min(len(nodes), max_nodes),
    "truncated": len(nodes) > max_nodes
})
```

## Testing Strategy

### Unit Tests

**Graph Query Testing** (`test_graph_query_*.py`):
- Mock Neo4j driver to return known test data
- Verify correct Cypher queries generated for different seed/filter combinations
- Test BFS expansion logic with controlled graph topology
- Verify `max_nodes` enforcement preserves most important nodes
- Test edge cases: empty namespace, invalid seeds, connection failures

**HTML Builder Testing** (`test_html_builder_*.py`):
- Test HTML template rendering with sample graph data
- Verify JSON serialization of nodes and relationships
- Check neovis.js configuration structure and completeness  
- Validate HTML structure (required divs, script tags, CDN links)
- Test style configuration embedding

### Integration Tests

**End-to-End Pipeline** (`test_render_cli.py`):
- Use Docker Neo4j fixture with small test graph
- Run complete `kg-forge render` command with various options
- Verify output HTML file creation and basic structure
- Test different seed and filtering scenarios
- Validate exit codes for error conditions

**Test Data Setup**:
- Create minimal test graph with 2-3 docs, 5-6 entities, various relationship types
- Use predictable IDs and properties for deterministic testing
- Cover different entity types and relationship patterns from schema

### HTML Validation

**Structural Testing** (No Browser Required):
- Parse generated HTML with BeautifulSoup
- Verify presence of visualization container div
- Check embedded JSON data completeness and validity
- Validate neovis.js configuration object structure
- Ensure no syntax errors in embedded JavaScript

**Visual Testing** (Optional):
- Document approach for manual testing in browser
- Provide sample commands that generate known-good visualizations
- No automated browser testing in CI (too complex for v1)

## Success Criteria

Step 7 is considered complete when:

- [x] `kg-forge render --namespace default --out graph.html` produces an HTML file that:
  - Loads without JavaScript errors in a browser
  - Shows nodes and edges corresponding to the expected subgraph from Neo4j
  - Visually distinguishes `:Doc` vs `:Entity` nodes with appropriate colors/shapes
  - Displays meaningful labels (doc IDs, entity names) and tooltips
- [x] **Subgraph selection logic** behaves correctly and is covered by tests:
  - BFS expansion respects `--depth` parameter exactly
  - `--max-nodes` enforcement preserves seed nodes and connectivity
  - Seed resolution works for both doc IDs and entity name/type combinations
- [x] **Visual styling** clearly distinguishes node and relationship types:
  - Different entity types (Product, Team, Technology) have distinct colors
  - Relationship types are labeled and styled appropriately
  - Node sizes reflect importance (degree, etc.)
- [x] **CLI interface** provides good user experience:
  - Helpful error messages for invalid seeds or empty namespaces
  - Progress logging for long queries and file generation
  - Reasonable defaults work out-of-the-box for typical usage
- [x] **No writes to Neo4j** occur during render operations
- [x] **No changes required** to Steps 2-6 APIs beyond existing interfaces
- [x] **Test coverage** for rendering modules meets project target (>90%)
- [x] **Generated HTML** is self-contained and safe to share (no embedded credentials)

## Step 1: Ontology Visualization (COMPLETED ✅)

**FOUNDATIONAL FEATURE**: Interactive visualization of ontology structure using Cytoscape.js

### Overview

Implemented `render-ontology` command to generate interactive HTML visualizations of the ontology structure, showing entity types and their relationships. This provides a foundational capability for understanding ontology structure before populating the knowledge graph with actual data.

### Implementation

- **New CLI Command**: `kg-forge render-ontology` with comprehensive options
  - `--ontology-pack`: Select specific ontology pack to visualize
  - `--layout`: Choose from force-directed, hierarchical, circular, or grid layouts
  - `--theme`: Light or dark theme support
  - `--include-examples`: Include entity examples as additional nodes
  - `--out`: Custom output file path

- **Cytoscape.js Integration**: Professional graph visualization library
  - Interactive node dragging, zooming, and panning
  - Rich tooltips showing entity descriptions and relationships
  - Multiple layout algorithms for different exploration needs
  - Responsive design working across devices and screen sizes

- **Self-contained Output**: No external dependencies required
  - Embedded Cytoscape.js library in generated HTML
  - Offline-capable visualization files
  - Safe to share without exposing system details

### Test Coverage

All ontology visualization functionality is fully tested:
- ✅ CLI help and argument parsing (test_render_ontology_help)
- ✅ HTML file generation with proper content (test_render_ontology_generates_html)
- ✅ Error handling for invalid ontology packs (test_render_ontology_invalid_pack)
- ✅ Layout algorithm options validation (test_render_ontology_layout_options)
- ✅ Theme support verification (test_render_ontology_theme_options)
- ✅ Entity examples integration (test_render_ontology_with_examples)

**Result**: 6/6 tests passing (100% pass rate) with comprehensive coverage of all features.

## Next Steps

Step 7 provides the first user-facing visualization capability by leveraging the populated Knowledge Graph from Steps 2-6 (HTML parsing, entity extraction, and Neo4j storage) to generate interactive graph visualizations. This establishes the foundation for more advanced exploration features such as filter panels, saved views, export capabilities, or integration with richer UI frameworks. Step 7 is intentionally minimal and backend-driven (CLI + static HTML) to validate the core visualization approach before investing in more complex frontend infrastructure. Future enhancements can build on this static HTML generation approach to add real-time filtering, collaborative features, or integration with existing enterprise visualization tools.