# Specification: Entity Definitions Loading

**Status**: Approved  
**Created**: 2025-11-21  
**Updated**: 2025-11-21  
**Related to**: Step 3 - Load Entity Definitions from Markdown Files

## Overview

This step implements the loading and parsing of entity type definitions from markdown files in the `entities_extract/` directory. These definitions will be used to:
1. Generate prompts for LLM-based entity extraction (Step 5)
2. Define the schema for the knowledge graph (Step 4)
3. Provide a CLI to inspect and validate entity definitions

## Requirements Summary

1. Load all `.md` files from `entities_extract/` directory
2. Parse markdown structure to extract entity metadata
3. Create Pydantic models for entity definitions
4. Provide CLI commands to inspect loaded definitions
5. Validate definitions (loosely - only ID is required)
6. Support prompt template merging with entity definitions

## Design Decisions (Approved)

### 1. Markdown Parsing
- **Flexible parsing** with accommodation for space and case variations
- Log warnings for malformed headings
- Only ID is required (defaults to filename)

### 2. Relations Format
Relations use format: `<target_entity_type> : <forward_label> : <reverse_label>`
- Parse and store both directions
- Canonical direction: from the entity whose `.md` file defines it
- Example: `team.md` with `Product : WORKS_ON : WORKED_ON_BY` means `(Team)-[:WORKS_ON]->(Product)`

### 3. Examples Parsing
- Extract both heading and full description text
- Include full examples in prompt template for LLM context

### 4. File Discovery
- Dynamically discover all `*.md` files in `entities_extract/`
- Exclude: `prompt_template.md` and `README.md`

### 5. Validation
- **Required**: ID only (defaults to filename if missing)
- **Warnings**: Missing Name, Description, or Relations
- No validation of relation targets at load time (may be added later)

### 6. CLI Commands
Four commands in the `entities` command group:
- `kg-forge entities list` - List all entity types
- `kg-forge entities show <type>` - Show details for specific type
- `kg-forge entities validate` - Validate all definitions
- `kg-forge entities template` - Show merged prompt template

## Data Model

### Entity Definition Structure

```python
class EntityRelation(BaseModel):
    """Represents a relation from this entity type to another."""
    target_entity_type: str  # e.g., "component"
    forward_label: str       # e.g., "uses_component"
    reverse_label: str       # e.g., "component_used_by_product"
    
class EntityExample(BaseModel):
    """Represents an example entity instance."""
    name: str                # Heading text, e.g., "Knowledge Discovery (KD)"
    description: str         # Description text below heading

class EntityDefinition(BaseModel):
    """Represents a complete entity type definition."""
    entity_type_id: str      # e.g., "product" (from ID or filename)
    name: Optional[str]      # e.g., "Software Product"
    description: Optional[str]  # Full description text
    relations: List[EntityRelation] = []
    examples: List[EntityExample] = []
    source_file: str         # Original filename for reference
    
class EntityDefinitions(BaseModel):
    """Collection of all entity definitions."""
    definitions: Dict[str, EntityDefinition]  # Key: entity_type_id
    
    def get_all_markdown(self) -> str:
        """Get concatenated markdown of all definitions for prompt."""
        
    def get_by_type(self, entity_type_id: str) -> Optional[EntityDefinition]:
        """Get definition by ID."""
```

## Markdown Parsing Strategy

### 1. File Structure Detection

```python
def parse_entity_markdown(filepath: Path) -> EntityDefinition:
    """
    Parse entity definition from markdown file.
    
    Expected structure:
    # ID: product
    ## Name: Software Product
    ## Description:
    <description text>
    ## Relations
      - component : uses_component : component_used_by_product
    ## Examples:
    ### Example 1
    <example description>
    """
```

### 2. Parsing Rules

1. **ID Extraction**: 
   - Look for `# ID: <value>` pattern
   - If not found, use filename (without `.md`)
   - Remove whitespace, lowercase

2. **Name Extraction**:
   - Look for `## Name: <value>` pattern
   - Extract text after `:`
   - Optional field

3. **Description Extraction**:
   - Look for `## Description:` heading
   - Collect all content until next `##` heading
   - Strip whitespace
   - Optional field

4. **Relations Extraction**:
   - Look for `## Relations` heading
   - Parse bullet points: `- <target> : <forward> : <reverse>`
   - Handle both `-` and `*` bullets
   - Optional (empty list if not found)

5. **Examples Extraction**:
   - Look for `## Examples:` heading
   - Parse `###` subheadings as example names
   - Collect content until next `###` or end
   - Optional (empty list if not found)

### 3. Template Integration

```python
def merge_with_prompt_template(
    definitions: EntityDefinitions,
    template_path: Path
) -> str:
    """
    Merge entity definitions with prompt template.
    
    Reads template, replaces {{ENTITY_TYPE_DEFINITIONS}}
    with concatenated markdown of all definitions.
    """
```

## Implementation Plan

### Module Structure

```
kg_forge/
├── kg_forge/
│   ├── entities/
│   │   ├── __init__.py
│   │   ├── models.py           # Pydantic models
│   │   ├── loader.py           # Markdown file loading
│   │   ├── parser.py           # Markdown parsing
│   │   └── template.py         # Prompt template merging
│   ├── cli/
│   │   └── entities.py         # CLI commands (new)
```

### Core Classes

#### 1. EntityMarkdownParser

```python
class EntityMarkdownParser:
    """Parse entity definition from markdown text."""
    
    def parse(self, content: str, source_file: str) -> EntityDefinition:
        """Parse markdown content into EntityDefinition."""
    
    def _extract_id(self, content: str, fallback: str) -> str:
        """Extract ID from markdown or use fallback."""
    
    def _extract_name(self, content: str) -> Optional[str]:
        """Extract Name from markdown."""
    
    def _extract_description(self, content: str) -> Optional[str]:
        """Extract Description from markdown."""
    
    def _extract_relations(self, content: str) -> List[EntityRelation]:
        """Extract Relations from markdown."""
    
    def _extract_examples(self, content: str) -> List[EntityExample]:
        """Extract Examples from markdown."""
```

#### 2. EntityDefinitionsLoader

```python
class EntityDefinitionsLoader:
    """Load entity definitions from directory."""
    
    def __init__(self, entities_dir: Path):
        self.entities_dir = entities_dir
        self.parser = EntityMarkdownParser()
    
    def load_all(self) -> EntityDefinitions:
        """Load all entity definitions from directory."""
    
    def _should_process_file(self, filepath: Path) -> bool:
        """Check if file should be processed (exclude template, README)."""
```

#### 3. PromptTemplateBuilder

```python
class PromptTemplateBuilder:
    """Build prompts from template and entity definitions."""
    
    def merge_definitions(
        self,
        template_path: Path,
        definitions: EntityDefinitions
    ) -> str:
        """Merge entity definitions into template."""
    
    def prepare_extraction_prompt(
        self,
        template_path: Path,
        definitions: EntityDefinitions,
        text: str
    ) -> str:
        """Prepare complete prompt for entity extraction."""
```

## CLI Integration

### New Command Group: `entities`

```python
@cli.group()
def entities():
    """Manage entity type definitions."""
    pass

@entities.command(name="list")
def list_entities():
    """List all entity type definitions."""
    # Load definitions
    # Display table: ID | Name | Relations | Examples
    
@entities.command(name="show")
@click.argument("entity_type")
def show_entity(entity_type: str):
    """Show details for a specific entity type."""
    # Load definitions
    # Find matching type
    # Display full details
    
@entities.command(name="validate")
def validate_entities():
    """Validate all entity definitions."""
    # Load definitions
    # Check for issues
    # Report warnings/errors
    
@entities.command(name="template")
@click.option("--output", help="Output file (default: stdout)")
def show_template(output: Optional[str]):
    """Show the merged prompt template with entity definitions."""
    # Load definitions
    # Merge with template
    # Output result
```

### Example Outputs

```bash
$ kg-forge entities list

Entity Type Definitions (6 found):

ID               Name                  Relations  Examples
─────────────────────────────────────────────────────────────
product          Software Product      6          3
component        Service/Component     4          5
workstream       Engineering Work      2          4
technology       Technology Stack      3          6
engineering_team Engineering Team      3          4
ai_ml_domain     AI/ML Domain          2          5
```

```bash
$ kg-forge entities show product

Entity Type: product
Name: Software Product
Source: entities_extract/product.md

Description:
A software product is a distinct, named solution we build and ship.
Examples in our ecosystem include Knowledge Enrichment (KE)...

Relations (6):
  → component : uses_component : component_used_by_product
  → workstream : driven_by_workstream : workstream_targets_product
  ...

Examples (3):
  • Knowledge Discovery (KD)
  • Knowledge Enrichment (KE)
  • Agent Builder (AB)
```

## Testing Strategy

### Unit Tests

```python
# test_entity_parser.py
def test_parse_complete_entity():
    """Test parsing entity with all fields."""

def test_parse_minimal_entity():
    """Test parsing entity with only ID."""

def test_extract_id_from_heading():
    """Test ID extraction from markdown."""

def test_extract_id_fallback_to_filename():
    """Test ID defaults to filename."""

def test_extract_relations():
    """Test relations parsing."""

def test_extract_examples():
    """Test examples parsing."""

# test_entity_loader.py
def test_load_from_directory():
    """Test loading all entities from test directory."""

def test_exclude_template_file():
    """Test template.md is not loaded as entity."""

def test_load_handles_missing_fields():
    """Test loading with optional fields missing."""

# test_prompt_template.py
def test_merge_definitions_into_template():
    """Test template merging."""

def test_complete_prompt_generation():
    """Test full prompt with text."""
```

### Test Data

Create `tests/test_entities/` with sample entity definitions for testing.

## Success Criteria

1. ✓ Load entity definitions from markdown files
2. ✓ Parse all required and optional fields correctly
3. ✓ Handle missing optional fields gracefully
4. ✓ CLI commands to list, show, and validate entities
5. ✓ Merge definitions with prompt template
6. ✓ All tests pass
7. ✓ Documentation updated

## Dependencies

Add to `requirements.txt`:
- No new dependencies needed (use existing Python stdlib)

## Future Extensions (Not in Step 3)

- Entity definition validation against graph schema
- Auto-detection of circular relations
- Export loaded entities back to markdown
- Support for entity inheritance/templates
