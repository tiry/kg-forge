# kg-forge Usage Guide

This guide provides examples for all `kg-forge` CLI commands.

## Table of Contents

- [Setup](#setup)
- [Parse Command](#parse-command)
- [Entity Management](#entity-management)
- [Extract Command (LLM)](#extract-command-llm)
- [Database Operations](#database-operations)
- [Ingest Command](#ingest-command)
- [Query Command](#query-command)
- [Render Command](#render-command)

---

## Setup

### Installation

```bash
# Clone and install
cd kg_forge
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e .
```

### Configuration

Create a `.env` file from the example:

```bash
cp .env.example .env
```

Edit `.env` to configure:

```bash
# LLM Provider (choose one)
OPENROUTER_API_KEY=sk-or-v1-your-key-here
# OR
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret

# Neo4j Database
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-secure-password
```

---

## Parse Command

Parse Confluence HTML documents into structured format.

### Basic Usage

```bash
# Parse a single HTML file
kg-forge parse document.html

# Parse all HTML files in a directory
kg-forge parse ~/Downloads/confluence-export/

# Parse and show detailed information
kg-forge parse document.html --show-links --show-content
```

### Options

```bash
# Show extracted links
kg-forge parse document.html --show-links

# Show document content (first 500 chars)
kg-forge parse document.html --show-content

# Show both links and content
kg-forge parse document.html --show-links --show-content
```

### Output

The parse command displays:
- Document ID
- Title
- Breadcrumb path
- Content hash
- Statistics (word count, link count)
- Optionally: links and content preview

---

## Entity Management

Manage entity type definitions used for extraction and ingestion.

### List Entity Types

```bash
# List all entity types
kg-forge entities list

# List from custom directory
kg-forge entities list --entities-dir custom_entities/
```

Output shows a table with:
- Entity Type ID
- Name
- Relations count
- Examples count
- Source file

### Show Entity Details

```bash
# Show details for a specific entity type
kg-forge entities show product

# Case-insensitive
kg-forge entities show Product
kg-forge entities show PRODUCT

# Show entity from custom directory
kg-forge entities show technology --entities-dir custom_entities/
```

Output includes:
- Entity type information
- Description
- Relations to other entities
- Example instances

### Validate Entity Definitions

```bash
# Validate all entity definitions
kg-forge entities validate

# Validate specific directory
kg-forge entities validate --entities-dir custom_entities/
```

Checks for:
- Missing required fields (name, description)
- Missing relations
- Missing examples
- File parsing errors

### Show Entity Template

```bash
# Display template to stdout
kg-forge entities template

# Save template to a file
kg-forge entities template --output new_entity.md

# Use custom template
kg-forge entities template --entities-dir custom_entities/
```

Use this template to create new entity type definitions.

---

## Extract Command (LLM)

Extract entities from documents using LLM (OpenRouter or AWS Bedrock).

### Basic Usage

```bash
# Extract all entity types from a document
kg-forge extract document.html

# Extract specific entity types only
kg-forge extract document.html --types Product --types Technology

# Filter by confidence threshold
kg-forge extract document.html --min-confidence 0.7
```

### Output Formats

```bash
# Human-readable text output (default)
kg-forge extract document.html

# JSON output
kg-forge extract document.html --format json

# JSON output to file
kg-forge extract document.html --format json > results.json
```

### Advanced Options

```bash
# Use custom entity definitions directory
kg-forge extract document.html --entities-dir custom_entities/

# Adjust max tokens for LLM response
kg-forge extract document.html --max-tokens 8000

# Combine multiple options
kg-forge extract document.html \
  --types Product --types Component \
  --min-confidence 0.8 \
  --format json \
  --max-tokens 6000
```

### ⚠️ Important Note on Type Filtering

When using `--types` to filter specific entity types, be aware of this limitation:

**The Issue:** Entity definitions often reference related entity types. For example:
- `Product` may have relations to `Component` and `Technology`
- If you only extract `--types Product`, the prompt won't include definitions for Component or Technology
- This can reduce extraction quality because the LLM lacks context about related entities

**Recommendation:**
```bash
# ❌ Limited context - Product references Component but it's not in prompt
kg-forge extract doc.html --types Product

# ✅ Better context - Include related entity types
kg-forge extract doc.html --types Product --types Component --types Technology

# ✅ Best - Extract all types then filter by confidence
kg-forge extract doc.html --min-confidence 0.8
```

**When to use `--types`:**
- ✅ Quick testing of specific entity definitions
- ✅ When entity types have no cross-references
- ✅ For performance when extracting from large documents

**When NOT to use `--types`:**
- ❌ When entity definitions have many relations to other types
- ❌ When you need highest extraction quality
- ❌ For production ingestion pipelines

For production use, it's generally better to extract all entity types and let the full knowledge graph capture all relationships, rather than filtering upfront.

### Example Output (Text Format)

```
✓ Extraction Complete

File: document.html
Model: anthropic/claude-3-haiku
Entities found: 5
Tokens used: 2,147
Extraction time: 3.42s

Product (2):
  • Knowledge Discovery
  • Content Lake (confidence: 0.85)

Technology (3):
  • Neo4j
  • Python
  • LlamaIndex (confidence: 0.90)
```

### Example Output (JSON Format)

```json
{
  "file": "document.html",
  "model": "anthropic/claude-3-haiku",
  "entities": [
    {
      "type": "product",
      "name": "Knowledge Discovery",
      "confidence": 1.0
    },
    {
      "type": "technology",
      "name": "Neo4j",
      "confidence": 1.0
    }
  ],
  "metadata": {
    "entity_count": 5,
    "extraction_time": 3.42,
    "tokens_used": 2147,
    "success": true
  }
}
```

---

## Database Operations

Manage the Neo4j database lifecycle.

### Start Database

```bash
# Start Neo4j using Docker Compose
kg-forge db start

# Auto-detects Rancher Desktop if available
# Falls back to Docker Desktop
```

The database will be available at:
- Bolt: `bolt://localhost:7687`
- HTTP: `http://localhost:7474`
- Browser: `http://localhost:7474/browser/`

### Initialize Database

```bash
# Create schema (constraints and indexes)
kg-forge db init

# Initialize with custom namespace
kg-forge db init --namespace production
```

Creates:
- Unique constraints on entity and document IDs
- Indexes for performance
- Namespace isolation

### Stop Database

```bash
# Stop the database
kg-forge db stop

# Data persists in Docker volumes
```

### Reset Database

```bash
# WARNING: Deletes all data!
kg-forge db reset

# With confirmation
kg-forge db reset --yes
```

---

## Ingest Command

Ingest documents and entities into Neo4j knowledge graph.

### Basic Usage

```bash
# Ingest from a directory
kg-forge ingest ~/Downloads/confluence-export/

# Ingest with output directory for processed files
kg-forge ingest ~/Downloads/confluence-export/ --output processed/

# Use custom namespace
kg-forge ingest ~/Downloads/confluence-export/ --namespace production
```

### What It Does

1. Parses HTML documents
2. Extracts entities (using LLM if configured)
3. Stores documents in Neo4j
4. Creates entity nodes
5. Links documents to entities
6. Creates relationships between entities

### Output

```bash
# Processed files are saved to --output directory
# with .json extension containing:
# - Parsed document
# - Extracted entities  
# - Metadata
```

---

## Query Command

Query the knowledge graph.

### Basic Queries

```bash
# List all entities in the graph
kg-forge query entities

# List entities of a specific type
kg-forge query entities --type Product

# Search for specific entity
kg-forge query entity "Knowledge Discovery"

# Query from specific namespace
kg-forge query entities --namespace production
```

### Advanced Queries

```bash
# Find documents mentioning an entity
kg-forge query documents-by-entity "Neo4j"

# Find related entities
kg-forge query related "Knowledge Discovery"

# Custom Cypher query
kg-forge query cypher "MATCH (n:Entity) RETURN n.name LIMIT 10"
```

---

## Render Command

Visualize the knowledge graph.

### Generate Visualizations

```bash
# Render graph visualization
kg-forge render graph

# Render specific namespace
kg-forge render graph --namespace production

# Output to file
kg-forge render graph --output knowledge-graph.html

# Render entity relationships only
kg-forge render entities

# Render document-entity network
kg-forge render network
```

### Visualization Types

- **Graph**: Full knowledge graph
- **Entities**: Entity relationship diagram
- **Network**: Document-entity network
- **Timeline**: Temporal view (if timestamps available)

---

## Common Workflows

### Complete Pipeline

```bash
# 1. Start database
kg-forge db start
kg-forge db init

# 2. Validate entity definitions
kg-forge entities validate

# 3. Test extraction on one document
kg-forge extract test-document.html

# 4. Ingest all documents
kg-forge ingest ~/Downloads/confluence-export/ --output processed/

# 5. Query the knowledge graph
kg-forge query entities

# 6. Visualize results
kg-forge render graph --output kg.html
```

### Testing Entity Extraction

```bash
# 1. Review entity definitions
kg-forge entities list
kg-forge entities show product

# 2. Test extraction
kg-forge extract sample-doc.html --types Product --types Technology

# 3. Adjust confidence threshold
kg-forge extract sample-doc.html --min-confidence 0.8

# 4. Get JSON output for analysis
kg-forge extract sample-doc.html --format json > results.json
```

### Database Maintenance

```bash
# Backup (using Neo4j tools)
docker exec kg-forge-neo4j neo4j-admin dump --database=neo4j --to=/backups/neo4j.dump

# Reset and re-ingest
kg-forge db reset --yes
kg-forge db init
kg-forge ingest ~/Downloads/confluence-export/
```

---

## Troubleshooting

### LLM Extraction Issues

```bash
# Check LLM configuration
kg-forge extract test.html
# Error: "No LLM provider configured"
# → Add OPENROUTER_API_KEY or AWS credentials to .env

# Increase token limit for large documents
kg-forge extract large-doc.html --max-tokens 8000

# Test specific entity types
kg-forge extract test.html --types Product
```

### Database Connection Issues

```bash
# Check if database is running
docker ps | grep neo4j

# Restart database
kg-forge db stop
kg-forge db start

# Check logs
docker logs kg-forge-neo4j
```

### Entity Definition Issues

```bash
# Validate definitions
kg-forge entities validate

# Check template format
kg-forge entities template > check-format.md
```

---

## Getting Help

```bash
# General help
kg-forge --help

# Command-specific help
kg-forge parse --help
kg-forge extract --help
kg-forge entities --help
kg-forge db --help
kg-forge ingest --help
kg-forge query --help
kg-forge render --help

# Version information
kg-forge --version
```

---

## See Also

- [README.md](README.md) - Project overview and installation
- [Install.md](Install.md) - Detailed installation instructions
- [Dev.md](Dev.md) - Development setup and testing
- [specs/](specs/) - Technical specifications
- [.env.example](.env.example) - Configuration template
