# Knowledge Graph Forge (kg-forge)

[![CI](https://github.com/YOUR_USERNAME/kg-forge/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/kg-forge/actions/workflows/ci.yml)
![Coverage](.github/coverage.svg)

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
│   │   ├── ingest.py       # Ingest command
│   │   ├── query.py        # Query command
│   │   ├── render.py       # Render command
│   │   └── neo4j_ops.py    # Neo4j operations
│   ├── config/             # Configuration
│   │   ├── __init__.py
│   │   └── settings.py     # Settings management
│   └── utils/              # Utilities
│       ├── __init__.py
│       └── logging.py      # Logging setup
├── tests/                  # Test suite
│   ├── __init__.py
│   ├── test_cli/           # CLI tests
│   └── test_config/        # Config tests
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
│   └── 01-cli-foundation.md # CLI foundation spec
├── requirements.txt        # Project dependencies
├── setup.py               # Package setup file
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

#### Neo4j Operations

```bash
# Start Neo4j database
kg-forge neo4j-start

# Stop Neo4j database
kg-forge neo4j-stop

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

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=kg_forge

# Run specific test file
pytest tests/test_cli/test_main.py
```

### Project Status

This project is currently in early development. The following features are implemented:

- [x] CLI command structure
- [x] Configuration management with environment variables and YAML
- [x] Logging setup
- [x] Command parsing and validation
- [ ] HTML parsing and content curation
- [ ] Entity definition loading
- [ ] LLM integration for entity extraction
- [ ] Neo4j graph operations
- [ ] Graph visualization

## License
