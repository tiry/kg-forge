# HTML Parsing Guide

This guide explains how to parse Confluence HTML exports using kg-forge's parsing commands.

## Overview

kg-forge provides two commands for working with HTML files:

1. **`parse`** - Interactive exploration of parsed documents
2. **`ingest --output-dir`** - Export parsed content to markdown files

Both commands use the same HTML parser that:
- Extracts document metadata (title, breadcrumb, links)
- Converts HTML content to clean Markdown
- Generates content hashes for change detection
- Creates LlamaIndex-compatible document structures

## Command 1: `parse` - Interactive Exploration

Use the `parse` command to explore and inspect parsed documents without creating any files.

### Basic Usage

```bash
# Parse all HTML files in a directory
kg-forge parse --source <path/to/html/files>

# Parse a single HTML file
kg-forge parse --source path/to/file.html
```

### Options

- `--source` (required): Path to HTML file or directory
- `--show-links`: Display extracted links in a formatted table
- `--show-content`: Preview the markdown content (first 50 lines)

### Examples

#### Example 1: Quick Overview

```bash
kg-forge parse --source ~/Downloads/confluence_export/
```

**Output:**
```
Parsing HTML from: ~/Downloads/confluence_export

Parsing directory...

✓ Successfully parsed 3 document(s)

Document 1: Content Lake - Architecture
  ID: 3352431259
  Source: Content-Lake_3352431259.html
  Hash: d5ec0ac64fa45f94...
  Path: Home → Projects → Content Lake
  Links: 5 found
  Content: 81 lines, 2731 characters

Document 2: API Documentation
  ID: 3182532046
  Source: API-Documentation_3182532046.html
  Hash: e17001f51f5fce0f...
  Path: Home → Documentation
  Links: 12 found
  Content: 156 lines, 5842 characters

Summary:
  Total documents: 3
  Total links: 17
  Total content: 12,847 characters
```

#### Example 2: View Links

```bash
kg-forge parse --source ~/Downloads/confluence_export/ --show-links
```

**Output includes link tables:**
```
Document 1: Content Lake - Architecture
  ...
  Links: 5 found
┏━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Type     ┃ Text                ┃ URL                           ┃
┡━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ internal │ API Spec            │ API-Spec_2862976116.html      │
│ external │ GitHub Repo         │ https://github.com/...        │
│ internal │ Design Doc          │ Design-Doc_3342665299.html    │
└──────────┴─────────────────────┴───────────────────────────────┘
```

#### Example 3: Preview Content

```bash
kg-forge parse --source path/to/specific-doc.html --show-content
```

**Output includes markdown preview:**
```
Document 1: API Design Principles
  ...
  Content: 245 lines, 8934 characters

Markdown Content:
# API Design Principles

## Overview

Our API follows RESTful design principles...

## Authentication

We use OAuth 2.0 for authentication...

[... first 50 lines shown ...]

... 195 more lines
```

#### Example 4: Full Details

```bash
kg-forge parse --source ~/Downloads/confluence_export/ --show-links --show-content
```

Shows everything: metadata, links table, and content preview for all documents.

## Command 2: `ingest --output-dir` - Export to Markdown

Use the `ingest` command with `--output-dir` to export parsed HTML to markdown files.

### Basic Usage

```bash
kg-forge ingest --source <path/to/html> --output-dir <target/directory>
```

### What It Does

1. Parses all HTML files in the source directory
2. Creates one `.md` file per document (named using `doc_id`)
3. Includes metadata header with document information
4. Writes full markdown content to each file

### Examples

#### Example 1: Basic Export

```bash
kg-forge ingest --source ~/Downloads/confluence_export/ --output-dir ~/parsed_docs/
```

**Output:**
```
Parsing HTML and exporting markdown to: ~/parsed_docs/

✓ Parsed 3 documents

• Wrote: 3352431259.md
• Wrote: 3182532046.md
• Wrote: 3352234692.md

✓ Successfully exported 3 markdown files
```

#### Example 2: Export to Timestamped Directory

```bash
# Create timestamped directory
export_dir=~/confluence_$(date +%Y%m%d_%H%M%S)
kg-forge ingest --source ~/Downloads/confluence_export/ --output-dir $export_dir
```

### Output File Format

Each exported markdown file includes:

```markdown
# Document Title

**Document ID:** 3352431259  
**Source:** Original-Filename.html  
**Breadcrumb:** Home → Projects → Architecture  
**Content Hash:** d5ec0ac64fa45f947d2f1f4ebce51eda472dd1917de2f4a0e9a5ab10df54e41b

---

[Full markdown content here]

## Section Headings

Content with proper formatting...

- List items
- More items

### Subsections

More content...
```

## Use Cases

### Use Case 1: Quick Content Review

**Goal:** Review what's in your Confluence export before processing

```bash
# Get overview
kg-forge parse --source ~/Downloads/confluence_export/

# Deep dive on specific areas
kg-forge parse --source ~/Downloads/confluence_export/Architecture/ --show-links --show-content
```

### Use Case 2: Mass Conversion to Markdown

**Goal:** Convert entire Confluence space to markdown for documentation

```bash
# Export everything
kg-forge ingest --source ~/Downloads/confluence_export/ --output-dir ~/wiki_markdown/

# Now you have clean markdown files ready for:
# - Git repository
# - Static site generator (Hugo, Jekyll, etc.)
# - Documentation systems
```

### Use Case 3: Prepare for LLM Processing

**Goal:** Extract clean text for LLM analysis

```bash
# Export to markdown
kg-forge ingest --source ~/confluence/ --output-dir ~/llm_input/

# Files are now ready for:
# - RAG pipelines
# - Vector embeddings
# - Entity extraction
# - Summarization
```

### Use Case 4: Content Analysis

**Goal:** Analyze link structure and document relationships

```bash
# View all links
kg-forge parse --source ~/confluence/ --show-links > links_report.txt

# Analyze the output to find:
# - Broken internal links
# - External dependencies
# - Document relationships
```

## Practical Workflows

### Workflow 1: Incremental Processing

```bash
# 1. First, explore the content
kg-forge parse --source ~/new_confluence_export/

# 2. Check a specific problematic file
kg-forge parse --source ~/new_confluence_export/Complex-Doc.html --show-content

# 3. Once satisfied, export everything
kg-forge ingest --source ~/new_confluence_export/ --output-dir ~/processed/
```

### Workflow 2: Selective Processing

```bash
# Export only architecture docs
kg-forge ingest --source ~/confluence/architecture/ --output-dir ~/arch_docs/

# Export only API docs
kg-forge ingest --source ~/confluence/api/ --output-dir ~/api_docs/
```

### Workflow 3: Quality Assurance

```bash
# Parse and review
kg-forge parse --source ~/confluence/ --show-links

# Look for:
# - Documents with no content (0 characters)
# - Documents with many broken links
# - Missing breadcrumbs

# Fix source HTML if needed, then re-export
kg-forge ingest --source ~/confluence_fixed/ --output-dir ~/clean_export/
```

## Troubleshooting

### Problem: Empty Content

**Symptom:** Document shows `0 characters` in content

**Cause:** HTML might not have standard Confluence structure

**Solution:**
```bash
# Inspect the specific file
kg-forge parse --source path/to/empty-doc.html --show-content

# Check if content is in non-standard div
# Contact support if this happens frequently
```

### Problem: Missing Links

**Symptom:** `Links: 0 found` but you know there are links

**Cause:** Links might be JavaScript-generated or in non-content areas

**Solution:**
```bash
# View the raw content
kg-forge parse --source path/to/doc.html --show-content

# Links in markdown will be visible as [text](url)
```

### Problem: Garbled Markdown

**Symptom:** Markdown contains HTML tags or weird formatting

**Cause:** Complex HTML that markdownify struggles with

**Solution:**
- Check the markdown output in exported files
- Post-process with additional Markdown cleaners if needed
- Report specific issues for improvement

## Tips and Best Practices

### Tip 1: Start Small

```bash
# Don't parse thousands of files at once
# Start with a small subset
kg-forge parse --source ~/confluence/small_folder/
```

### Tip 2: Use Dry Runs

```bash
# The parse command is your dry run
# Review before exporting
kg-forge parse --source ~/confluence/
# Then export if happy
kg-forge ingest --source ~/confluence/ --output-dir ~/export/
```

### Tip 3: Organize Exports

```bash
# Use descriptive directory names
kg-forge ingest --source ~/confluence/ --output-dir ~/exports/confluence_2025_11_21/

# Or organize by namespace
kg-forge ingest --source ~/arch/ --output-dir ~/exports/architecture/
kg-forge ingest --source ~/api/ --output-dir ~/exports/api/
```

### Tip 4: Check Content Hashes

The content hash is useful for:
- Detecting duplicate content
- Tracking changes between exports
- Verifying file integrity

```bash
# Export once
kg-forge ingest --source ~/v1/ --output-dir ~/export_v1/

# Export again after updates
kg-forge ingest --source ~/v2/ --output-dir ~/export_v2/

# Compare hashes in the markdown files to see what changed
```

## Integration with Other Tools

### With Git

```bash
# Export to git repo
kg-forge ingest --source ~/confluence/ --output-dir ~/docs_repo/content/

cd ~/docs_repo
git add content/
git commit -m "Update from Confluence export"
git push
```

### With Static Site Generators

```bash
# Export for Hugo
kg-forge ingest --source ~/confluence/ --output-dir ~/hugo_site/content/confluence/

# Export for Jekyll
kg-forge ingest --source ~/confluence/ --output-dir ~/jekyll_site/_posts/confluence/
```

### With Vector Databases

```bash
# Export clean markdown for embedding
kg-forge ingest --source ~/confluence/ --output-dir ~/embedding_input/

# Process with your embedding pipeline
python embed_documents.py ~/embedding_input/
```

## Next Steps

After parsing HTML:

1. **Entity Extraction** (Coming in Step 6)
   - Extract entities from markdown
   - Build knowledge graph

2. **LlamaIndex Integration** (Coming in Step 3)
   - Chunk documents
   - Generate embeddings
   - Build RAG pipeline

3. **Neo4j Storage** (Coming in Step 5)
   - Store in graph database
   - Query relationships
   - Visualize knowledge graph

## Getting Help

- Check the main README: `kg_forge/ReadMe.md`
- View command help: `kg-forge parse --help` or `kg-forge ingest --help`
- Report issues using the `/reportbug` command
