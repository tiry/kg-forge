# Specification: HTML Parsing and Document Model

**Status**: Completed  
**Created**: 2025-11-21  
**Completed**: 2025-11-21  
**Related to**: Step 2 - HTML Loading and Parsing

## Overview

This specification defines how to parse Confluence HTML exports into structured documents compatible with LlamaIndex for downstream processing.

## Requirements Summary

1. Parse Confluence HTML exports to extract content and metadata
2. Convert HTML content to clean Markdown
3. Extract links (internal and external)
4. Generate content hash for change detection
5. Use Pydantic models compatible with LlamaIndex Document format
6. Support bulk processing of HTML files from a directory

## Data Model

### Document Structure

We'll use a Pydantic model that aligns with LlamaIndex's `Document` class for easy integration:

```python
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime

class DocumentLink(BaseModel):
    """Represents a link found in the document."""
    url: str
    text: str
    link_type: str  # 'internal' or 'external'

class ParsedDocument(BaseModel):
    """Parsed Confluence HTML document compatible with LlamaIndex."""
    
    # Core LlamaIndex-compatible fields
    doc_id: str = Field(..., description="Unique document identifier from filename")
    text: str = Field(..., description="Content in Markdown format")
    metadata: Dict[str, any] = Field(default_factory=dict)
    
    # Additional fields for our use case
    title: str = Field(..., description="Document title")
    breadcrumb: List[str] = Field(default_factory=list, description="Breadcrumb path")
    links: List[DocumentLink] = Field(default_factory=list, description="Links found in document")
    content_hash: str = Field(..., description="SHA-256 hash of markdown content")
    source_file: str = Field(..., description="Original HTML filename")
    parsed_at: datetime = Field(default_factory=datetime.now)
    
    def to_llamaindex_document(self):
        """Convert to LlamaIndex Document format when ready."""
        # Prepare metadata dict with all our custom fields
        metadata = {
            "title": self.title,
            "breadcrumb": self.breadcrumb,
            "links": [link.dict() for link in self.links],
            "content_hash": self.content_hash,
            "source_file": self.source_file,
            "parsed_at": self.parsed_at.isoformat(),
            **self.metadata  # Include any additional metadata
        }
        
        # Return dict compatible with LlamaIndex Document
        return {
            "doc_id": self.doc_id,
            "text": self.text,
            "metadata": metadata
        }
```

## HTML Parsing Strategy

### 1. Document Identification

```python
def extract_doc_id(filename: str) -> str:
    """
    Extract document ID from filename.
    
    Examples:
        "Content-Lake_3352431259.html" -> "3352431259"
        "Content-Lake---Content-Model_3182532046.html" -> "3182532046"
    """
    # Extract numeric ID from filename
    # Pattern: anything ending with _<digits>.html
```

### 2. Metadata Extraction

Extract from Confluence HTML structure:

```python
# Title: From <h1 id="title-heading">
title = soup.find('h1', id='title-heading').get_text(strip=True)

# Breadcrumb: From <ol id="breadcrumbs">
breadcrumb = [
    link.get_text(strip=True) 
    for link in soup.find('ol', id='breadcrumbs').find_all('a')
]
```

### 3. HTML to Markdown Conversion

Use `markdownify` library to convert HTML content:

```python
from markdownify import markdownify as md

# Extract main content
content_div = soup.find('div', id='main-content') or soup.find('div', class_='wiki-content')

# Convert to Markdown
markdown_content = md(
    str(content_div),
    heading_style="ATX",  # Use # for headings
    bullets="-",  # Use - for lists
    strip=['script', 'style']  # Remove these tags completely
)
```

### 4. Link Extraction

```python
def extract_links(soup) -> List[DocumentLink]:
    """Extract all links from content area."""
    links = []
    content = soup.find('div', id='main-content')
    
    for a_tag in content.find_all('a', href=True):
        href = a_tag['href']
        text = a_tag.get_text(strip=True)
        
        # Determine link type
        if href.startswith('http'):
            link_type = 'external'
        elif href.endswith('.html'):
            link_type = 'internal'
        else:
            continue  # Skip non-relevant links
            
        links.append(DocumentLink(
            url=href,
            text=text,
            link_type=link_type
        ))
    
    return links
```

### 5. Content Hashing

```python
import hashlib

def generate_content_hash(markdown_text: str) -> str:
    """Generate SHA-256 hash of markdown content."""
    return hashlib.sha256(markdown_text.encode('utf-8')).hexdigest()
```

## Implementation Plan

### Module Structure

```
kg_forge/
├── kg_forge/
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── html_parser.py      # Main HTML parsing logic
│   │   └── document_loader.py  # Bulk document loading
│   ├── models/
│   │   ├── __init__.py
│   │   └── document.py          # Pydantic models
```

### Dependencies

Add to `requirements.txt`:
```
beautifulsoup4>=4.12.0
markdownify>=0.11.0
lxml>=4.9.0
```

### Core Classes

#### 1. HTMLParser

```python
class ConfluenceHTMLParser:
    """Parse Confluence HTML exports to structured documents."""
    
    def parse_file(self, filepath: Path) -> ParsedDocument:
        """Parse a single HTML file."""
        
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract document title."""
        
    def _extract_breadcrumb(self, soup: BeautifulSoup) -> List[str]:
        """Extract breadcrumb path."""
        
    def _extract_content_as_markdown(self, soup: BeautifulSoup) -> str:
        """Convert HTML content to Markdown."""
        
    def _extract_links(self, soup: BeautifulSoup) -> List[DocumentLink]:
        """Extract all links."""
```

#### 2. DocumentLoader

```python
class DocumentLoader:
    """Load and parse multiple HTML documents."""
    
    def __init__(self, parser: ConfluenceHTMLParser):
        self.parser = parser
        
    def load_from_directory(
        self, 
        directory: Path,
        pattern: str = "*.html"
    ) -> List[ParsedDocument]:
        """Load all HTML files from a directory."""
        
    def load_files(self, filepaths: List[Path]) -> List[ParsedDocument]:
        """Load specific HTML files."""
```

## LlamaIndex Integration Strategy

### Current Phase (Step 2)

Focus on:
1. Parsing HTML correctly
2. Extracting clean Markdown
3. Capturing metadata and links
4. Storing in Pydantic models

### Future Integration (Step 3+)

When integrating with LlamaIndex:

```python
from llama_index.core import Document as LlamaDocument

def create_llamaindex_documents(parsed_docs: List[ParsedDocument]) -> List[LlamaDocument]:
    """Convert our documents to LlamaIndex format."""
    return [
        LlamaDocument(
            doc_id=doc.doc_id,
            text=doc.text,
            metadata=doc.to_llamaindex_document()["metadata"]
        )
        for doc in parsed_docs
    ]
```

This allows us to:
- Use LlamaIndex's text splitters for chunking
- Leverage LlamaIndex's embedding generators
- Use LlamaIndex's vector store integrations
- Apply LlamaIndex's query engines

## Testing Strategy

### Unit Tests

```python
# test_html_parser.py
def test_parse_simple_document():
    """Test parsing a simple Confluence page."""
    
def test_extract_title():
    """Test title extraction."""
    
def test_extract_breadcrumb():
    """Test breadcrumb extraction."""
    
def test_convert_to_markdown():
    """Test HTML to Markdown conversion."""
    
def test_extract_links():
    """Test link extraction."""
    
def test_content_hash_generation():
    """Test hash is consistent."""
```

### Integration Tests

```python
# test_document_loader.py
def test_load_from_test_directory():
    """Test loading from test_data directory."""
    
def test_parse_multiple_documents():
    """Test bulk document processing."""
```

## CLI Integration

Two commands were implemented for testing the HTML parser:

### 1. Parse Command (Interactive Exploration)

```python
@click.command(name="parse")
def parse_html(source: Path, show_content: bool, show_links: bool):
    """Parse HTML files and display extracted information."""
```

Features:
- Display document metadata (ID, title, hash, breadcrumb)
- Show extracted links in a formatted table
- Preview markdown content
- Summary statistics

### 2. Ingest Command (Export to Markdown)

Updated the `ingest` command with `--output-dir` option:

```python
@click.option("--output-dir", help="Output directory for parsed markdown files")
def ingest(source: Path, output_dir: Optional[Path] = None, ...):
    """Ingest HTML files and optionally export to markdown."""
```

Features:
- Parse all HTML files from source directory
- Export each document to `{doc_id}.md` file
- Include metadata header with document info
- Full markdown content in each file

## Success Criteria

1. ✓ Parse Confluence HTML correctly
2. ✓ Extract title and breadcrumb
3. ✓ Convert content to clean Markdown
4. ✓ Extract internal and external links
5. ✓ Generate consistent content hashes
6. ✓ Use Pydantic models compatible with LlamaIndex
7. ✓ Support bulk document loading
8. ✓ All tests pass
9. ✓ Documentation updated

## Next Steps (Future)

After this step is complete:

1. **Step 3**: Integrate with LlamaIndex
   - Set up document ingestion pipeline
   - Implement text chunking
   - Add embedding generation

2. **Step 4**: Add entity extraction
   - Load entity definitions
   - Use LLM to extract entities
   - Store in knowledge graph

3. **Step 5**: Neo4j integration
   - Design graph schema
   - Implement graph operations
   - Add query capabilities
