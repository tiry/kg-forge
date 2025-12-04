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

## Pipeline Command (End-to-End Processing)

🚀 **NEW** - The pipeline command orchestrates the complete end-to-end workflow: load documents → extract entities → store in Neo4j.

### Basic Usage

```bash
# Run the complete pipeline on a directory
kg-forge pipeline ~/Downloads/confluence-export/

# Use a specific namespace
kg-forge pipeline ~/Downloads/confluence-export/ --namespace production

# Extract specific entity types only
kg-forge pipeline ~/Downloads/confluence-export/ --types Product --types Technology
```

### What the Pipeline Does

The pipeline command automates the entire knowledge graph construction process:

1. **Loads** HTML documents from the source directory
2. **Extracts** entities using LLM (OpenRouter or AWS Bedrock)
3. **Normalizes** entity names (e.g., "K8S" → "Kubernetes") using default hooks
4. **Stores** documents and entities in Neo4j
5. **Links** documents to entities with MENTIONS relationships
6. **Tracks** progress with real-time statistics

### Pipeline Options

```bash
# Namespace (organize different projects)
kg-forge pipeline docs/ --namespace confluence

# Entity types (filter extraction)
kg-forge pipeline docs/ --types Product --types Component

# Confidence threshold (filter low-confidence entities)
kg-forge pipeline docs/ --min-confidence 0.8

# Skip already processed documents (hash-based)
kg-forge pipeline docs/ --reprocess  # Force reprocess all

# Batch size (process in batches)
kg-forge pipeline docs/ --batch-size 20

# Maximum consecutive failures before aborting
kg-forge pipeline docs/ --max-failures 10

# Dry run (test without writing to database)
kg-forge pipeline docs/ --dry-run
```

### Interactive Mode 🎯

**Human-in-the-Loop Entity Curation**

Enable interactive mode for entity deduplication and validation:

```bash
# Enable interactive mode
kg-forge pipeline docs/ --interactive

# Alternative flag (same as --interactive)
kg-forge pipeline docs/ --biraj
```

**What Interactive Mode Does:**

When enabled, the pipeline will prompt you to:

1. **Merge similar entities**
   ```
   Found similar entities: "Catherine J." and "Katherine Jones"
   Merge them? [Y/n]: y
   Which name should be canonical? 
     1. Catherine J.
     2. Katherine Jones
   Choice [2]: 2
   ```

2. **Resolve ambiguous names**
   ```
   Found similar entities: "K8s" and "Kubernetes"
   Merge them? [Y/n]: y
   Canonical name: Kubernetes
   ✓ Merged "K8s" → "Kubernetes"
   ```

3. **Review entity normalization**
   - See what automatic normalizations were applied
   - Confirm or reject suggested merges
   - Choose canonical names for merged entities

**When to Use Interactive Mode:**

✅ **Use --interactive for:**
- First-time ingestion of important documents
- Curating a production knowledge graph
- When entity quality is critical
- Building a golden dataset

❌ **Skip --interactive for:**
- Batch processing large document sets
- CI/CD pipelines (use default hooks automatically)
- Quick testing or experimentation
- Re-processing already curated data

### Dry Run Mode

Test the pipeline without writing to the database:

```bash
# Run extraction but don't store results
kg-forge pipeline docs/ --dry-run

# Combine with interactive to test curation workflow
kg-forge pipeline docs/ --dry-run --interactive

# See what would be extracted
kg-forge pipeline docs/ --dry-run --min-confidence 0.9
```

**Dry run output shows:**
- How many entities would be extracted
- Which documents would be processed or skipped
- Normalization and deduplication results
- No database writes are performed

### Pipeline Output

**Progress Tracking:**

```
🚀  Knowledge Graph Pipeline
📂 Source:       ~/Downloads/confluence-export/
🏷️  Namespace:    default
🔖 Entity types: all
📊 Min confidence: 0.0
♻️  Skip processed: Yes

⚙️  Initializing components...
✅ Components initialized

ℹ️  Loaded 15 documents from ~/Downloads/confluence-export/

[1/15 6.7%] PROCESSED Content-Lake_3352431259.html: 8 entities in 4.23s
[2/15 13.3%] PROCESSED Architecture_3352234692.html: 12 entities in 5.18s
[3/15 20.0%] SKIPPED Content-Model_3182532046.html: Already processed (hash match)
[4/15 26.7%] PROCESSED Technology-Stack_3352234693.html: 6 entities in 3.92s
...
[15/15 100.0%] PROCESSED Summary_3352234699.html: 4 entities in 2.81s

📊 Pipeline Results
📄 Total documents:     15
✅ Processed:           12
⏭️  Skipped:             3
❌ Failed:              0
📈 Success rate:        100.0%
🏷️  Total entities:      87
🔗 Total relationships: 124
⏱️  Duration:            58.42s

✨ Pipeline completed successfully!
```

**With Errors:**

```
[8/15 53.3%] FAILED Document_123.html: LLM timeout after 30s

⚠️  Errors encountered:

  1. Document_123.html: LLM timeout after 30s
  2. Document_456.html: Rate limit exceeded

⚠️  Pipeline completed with 2 failure(s)
```

### Default Hooks

The pipeline automatically applies these hooks:

1. **Entity Name Normalization** (before_store)
   - Converts common abbreviations to full names
   - "K8S" → "Kubernetes"
   - "AI/ML" → "Artificial Intelligence and Machine Learning"  
   - "CICD" → "CI/CD"

2. **Entity Deduplication** (after_batch, interactive mode only)
   - Detects similar entity names
   - Prompts for merge decisions
   - Updates canonical names

These hooks ensure consistency in your knowledge graph.

### Advanced Examples

**Production Ingestion:**

```bash
# High-quality extraction with interactive curation
kg-forge pipeline confluence-docs/ \
  --namespace production \
  --min-confidence 0.85 \
  --interactive \
  --max-failures 3
```

**Quick Test Run:**

```bash
# Test extraction without database writes
kg-forge pipeline test-docs/ \
  --dry-run \
  --types Product \
  --min-confidence 0.9
```

**Batch Processing:**

```bash
# Process large document sets efficiently
kg-forge pipeline large-corpus/ \
  --namespace archive \
  --batch-size 50 \
  --skip-processed \
  --max-failures 10
```

**Re-process with Higher Quality:**

```bash
# Force reprocess with stricter confidence
kg-forge pipeline docs/ \
  --reprocess \
  --min-confidence 0.9 \
  --interactive
```

### Idempotency & Resume

The pipeline is **idempotent** by default:

- Documents are identified by content hash (SHA-256)
- Already processed documents are automatically skipped
- Safe to run multiple times on the same directory
- Resume after failures without re-processing

```bash
# First run - processes all 100 documents
kg-forge pipeline docs/

# Second run - skips all 100 (already processed)
kg-forge pipeline docs/

# Force reprocess
kg-forge pipeline docs/ --reprocess
```

### Comparison: Pipeline vs. Ingest

**Use `kg-forge pipeline` when:**
- ✅ You want end-to-end automation
- ✅ You have LLM configured (OpenRouter/Bedrock)
- ✅ You want entity extraction + graph storage
- ✅ You need progress tracking and error handling
- ✅ You want interactive entity curation

**Use `kg-forge ingest` when:**
- ✅ You already have extracted entity JSON files
- ✅ You want to store pre-processed data
- ✅ LLM extraction is not needed
- ✅ You're working with legacy data

**Quick Reference:**

| Feature | `pipeline` | `ingest` |
|---------|-----------|----------|
| Document Loading | ✅ Yes | ✅ Yes |
| LLM Extraction | ✅ Yes | ❌ No |
| Entity Normalization | ✅ Yes | ❌ No |
| Interactive Mode | ✅ Yes | ❌ No |
| Progress Tracking | ✅ Detailed | ✅ Basic |
| Idempotency | ✅ Hash-based | ⚠️ Manual |
| Dry Run | ✅ Yes | ❌ No |

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
