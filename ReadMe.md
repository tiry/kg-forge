# Knowledge Graph Forge (kg-forge)

[![CI](https://github.com/tiry/kg-forge/actions/workflows/ci.yml/badge.svg)](https://github.com/tiry/kg-forge/actions/workflows/ci.yml)
![Coverage](https://raw.githubusercontent.com/tiry/kg-forge/badges/.github/coverage.svg)

CLI tool for extracting entities from unstructured content and building knowledge graphs for experimentation and analysis.

## Description

Knowledge Graph Forge is a command-line tool that helps extract entities and relationships from unstructured data to build and manipulate knowledge graphs. The tool aims to address questions about:

- Best strategies for extracting meaningful entities and topics from content
- Optimal methods for storing, organizing, merging, and pruning a Knowledge Graph
- Creating and maintaining useful ontologies

The tool provides a simple end-to-end pipeline that focuses on knowledge graph creation and usage, with minimal dependencies on external services in early versions.

## Project Structure

```
kg_forge/
├── kg_forge/               # Main package
│   ├── __init__.py         # Package metadata
│   ├── cli/                # CLI commands
│   │   ├── __init__.py
│   │   ├── main.py         # Main CLI entry point
│   │   ├── db.py           # Database commands (init, status, clear)
│   │   ├── entities.py     # Entity commands (list, show, validate)
│   │   ├── parse.py        # Parse command
│   │   ├── ingest.py       # Ingest command
│   │   ├── query.py        # Query command
│   │   ├── render.py       # Render command
│   │   └── neo4j_ops.py    # Neo4j operations (start/stop)
│   ├── config/             # Configuration
│   │   ├── __init__.py
│   │   └── settings.py     # Settings management (GraphConfig)
│   ├── models/             # Data models
│   │   ├── __init__.py
│   │   └── document.py     # Document model
│   ├── parsers/            # Content parsers
│   │   ├── __init__.py
│   │   ├── html_parser.py  # HTML parsing
│   │   └── document_loader.py # Document loading
│   ├── entities/           # Entity definitions
│   │   ├── __init__.py
│   │   ├── models.py       # Entity models
│   │   ├── parser.py       # Entity definition parser
│   │   ├── loader.py       # Entity definition loader
│   │   └── template.py     # Template merging
│   ├── graph/              # Graph database abstraction
│   │   ├── __init__.py
│   │   ├── base.py         # Abstract base classes
│   │   ├── exceptions.py   # Graph exceptions
│   │   ├── factory.py      # Factory pattern
│   │   └── neo4j/          # Neo4j implementation
│   │       ├── __init__.py
│   │       ├── client.py   # Connection manager
│   │       ├── schema.py   # Schema management
│   │       ├── entity_repo.py   # Entity repository
│   │       └── document_repo.py # Document repository
│   └── utils/              # Utilities
│       ├── __init__.py
│       └── logging.py      # Logging setup
├── tests/                  # Test suite
│   ├── __init__.py
│   ├── test_cli/           # CLI tests
│   ├── test_config/        # Config tests
│   ├── test_parsers/       # Parser tests
│   ├── test_entities/      # Entity tests
│   └── test_graph/         # Graph database tests
│       ├── __init__.py
│       ├── conftest.py     # Shared fixtures (Rancher-compatible)
│       ├── test_entity_repo.py    # Unit tests (mocks)
│       └── test_integration.py    # Integration tests (Docker)
├── entities_extract/       # Entity definitions
│   ├── product.md          # Product entity definition
│   ├── component.md        # Component entity definition
│   ├── workstream.md       # Workstream entity definition
│   ├── technology.md       # Technology entity definition
│   ├── engineering_team.md # Engineering team entity definition
│   ├── ai_ml_domain.md     # AI/ML domain entity definition
│   └── prompt_template.md  # Prompt template for entity extraction
├── specs/                  # Specification documents
│   ├── seed.md             # Initial specification
│   ├── 01-cli-foundation.md         # CLI foundation
│   ├── 02-html-parsing-and-document-model.md  # HTML parsing
│   ├── 03-entity-definitions-loading.md  # Entity loading
│   └── 04-neo4j-bootstrap.md        # Neo4j implementation
├── docs/                   # Documentation
│   ├── CI_SETUP.md         # CI/CD setup guide
│   └── PARSING_HTML.md     # HTML parsing documentation
├── requirements.txt        # Project dependencies
├── setup.py               # Package setup file
├── docker-compose.yml     # Neo4j container configuration
├── .env.example           # Example environment variables
├── kg_forge.yaml.example  # Example YAML configuration
└── .gitignore             # Git ignore file  
```

## Installation

### Prerequisites

- Python 3.8 or higher
- Neo4j instance (for actual graph operations)
- AWS account with Bedrock access (for LLM entity extraction)

### Setup

1. Clone the repository:

```bash
git clone <repository-url>
cd kg-forge
```

2. Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install the package in development mode:

```bash
pip install -e .
```

4. Configure your environment:

```bash
# Copy example files
cp .env.example .env
cp kg_forge.yaml.example kg_forge.yaml

# Edit configuration with your settings
# nano .env
# nano kg_forge.yaml
```

## Usage

### Main Commands

kg-forge provides several commands for working with knowledge graphs:

#### Ingest Content

```bash
# Basic ingest from source directory
kg-forge ingest --source <path/to/html/files>

# With namespace and other options
kg-forge ingest --source <path> --namespace test --dry-run --interactive
```

#### Query Knowledge Graph

```bash
# List entity types
kg-forge query list-types

# List entities of a specific type
kg-forge query list-entities --type Product

# List all documents
kg-forge query list-docs

# Show document details
kg-forge query show-doc --id <doc-id>

# Find related entities
kg-forge query find-related --entity "Knowledge Discovery" --type Product
```

#### Render Knowledge Graph

```bash
# Render with default options
kg-forge render

# With custom options
kg-forge render --out custom_graph.html --depth 3 --max-nodes 200
```

#### Database Operations

```bash
# Start Neo4j database (via Docker)
kg-forge neo4j-start

# Stop Neo4j database
kg-forge neo4j-stop

# Initialize database schema
kg-forge db init

# Check database status and statistics
kg-forge db status
kg-forge db status --namespace test

# Clear namespace data
kg-forge db clear --namespace test --confirm

# Export entities from graph to markdown files
kg-forge export-entities --output-dir custom_entities/
```

### Configuration Options

You can configure kg-forge using:

1. **Command-line arguments** (highest priority)
2. **YAML configuration file** (`kg_forge.yaml` or `config.yaml`)
3. **Environment variables**
4. **`.env` file values**
5. **Default values** (lowest priority)

#### Example Environment Variables

```env
# Neo4j Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password

# AWS Bedrock Configuration
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here
AWS_DEFAULT_REGION=us-east-1
BEDROCK_MODEL_NAME=anthropic.claude-3-haiku-20240307-v1:0

# Application Configuration
LOG_LEVEL=INFO
DEFAULT_NAMESPACE=default
```

#### Example YAML Configuration

```yaml
# Neo4j Configuration
neo4j:
  uri: bolt://localhost:7687
  username: neo4j
  password: password

# AWS Bedrock Configuration
aws:
  access_key_id: your_access_key_here
  secret_access_key: your_secret_key_here
  default_region: us-east-1
  bedrock_model_name: anthropic.claude-3-haiku-20240307-v1:0

# Application Configuration
app:
  log_level: INFO
  default_namespace: default
```

## Development

### Running Tests

kg-forge includes comprehensive unit and integration tests.

#### Unit Tests (Fast, No Dependencies)

```bash
# Activate virtual environment first
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Run all unit tests
pytest tests/test_cli tests/test_parsers tests/test_entities tests/test_graph/test_entity_repo.py -v

# Run specific test module
pytest tests/test_graph/test_entity_repo.py -v

# With coverage report
pytest --cov=kg_forge tests/
```

#### Integration Tests (Requires Docker or Rancher Desktop)

The integration tests spin up a real Neo4j container to test database operations end-to-end.

**For Docker Desktop:**
```bash
source venv/bin/activate
pytest tests/test_graph/test_integration.py -v -s
```

**For Rancher Desktop:**
```bash
source venv/bin/activate

# Option 1: Use --rancher flag
pytest tests/test_graph/test_integration.py -v -s --rancher

# Option 2: Use environment variable
USE_RANCHER=true pytest tests/test_graph/test_integration.py -v -s
```

The integration tests cover:
- Schema management (constraints & indexes)
- Entity CRUD operations
- Entity relationships
- Document operations
- Document-entity linking (MENTIONS relationships)
- Namespace isolation

#### Test Coverage

- **Unit Tests**: 40+ tests (parsers, entities, CLI, repositories)
- **Integration Tests**: 19 tests (real Neo4j database operations)
- **Total**: 60+ comprehensive tests

### Project Status

This project is currently in early development. The following features are implemented:

- [x] CLI command structure
- [x] Configuration management with environment variables and YAML
- [x] Logging setup
- [x] Command parsing and validation
- [x] HTML parsing and content curation
  - [x] Parse Confluence HTML exports
  - [x] Convert HTML to Markdown
  - [x] Extract metadata (title, breadcrumb, links)
  - [x] Generate content hashes for change detection
  - [x] LlamaIndex-compatible document models
- [x] Entity definition loading
  - [x] Parse entity definitions from markdown files
  - [x] Flexible markdown parsing (handles spacing/case variations)
  - [x] Template merging for LLM prompts
  - [x] CLI commands: list, show, validate, template
- [x] Neo4j graph operations
  - [x] Repository pattern with abstract base classes
  - [x] Factory pattern for backend selection
  - [x] Neo4j implementation (schema, entities, documents, relationships)
  - [x] Docker-compose integration
  - [x] Database CLI commands (init, status, clear)
  - [x] Name normalization for fuzzy matching
  - [x] Namespace isolation (multi-tenancy)
  - [x] Comprehensive test suite (27 tests)
- [ ] LLM integration for entity extraction
- [ ] Graph visualization

#### Architecture

**Graph Abstraction Layer:**
- `kg_forge/graph/base.py` - Abstract interfaces (GraphClient, SchemaManager, EntityRepository, DocumentRepository)
- `kg_forge/graph/factory.py` - Factory for backend-agnostic access
- `kg_forge/graph/neo4j/` - Complete Neo4j implementation

**Key Design Decisions:**
- Single `Entity` label with `entity_type` property (flexible schema)
- Canonical relationships (e.g., USES not USED_BY)
- Namespace property on all nodes for multi-tenancy
- Content hash tracking for deduplication
- Normalized entity names for fuzzy matching

## License
