# Step 4: Load Entity Definitions

**Status**: Not Started  
**Created**: 2025-11-27  
**Related to**: Step 4 - Entity Type Loading and Prompt Assembly

## Overview

Step 4 implements the ontology loading system that reads entity type definitions from `entities_extract/*.md` files and assembles them into LLM-ready extraction prompts. This step provides a robust foundation for ontology-driven entity extraction by parsing markdown-based entity definitions and merging them with prompt templates using placeholder replacement.

Step 4 builds the bridge between the curated document content from Step 3 and the LLM-based entity extraction that will come in Step 6. It focuses purely on loading, parsing, and prompt assembly without performing any actual entity extraction, graph operations, or external service calls.

Step 3 explicitly does NOT:
- Call any LLMs or connect to Bedrock
- Write to or read from Neo4j
- Process HTML content or documents
- Perform entity deduplication, merging, or pruning operations

## Scope

### In Scope

- Parse entity type definition files from `entities_extract/*.md` following the canonical markdown structure
- Load and parse `entities_extract/prompt_template.md` with placeholder support
- Represent entity types, relations, and examples as strongly-typed Python models
- Build merged prompt strings by replacing `{{ENTITY_TYPE_DEFINITIONS}}` placeholder with concatenated entity definitions
- CLI commands to inspect loaded entity types and preview assembled prompts
- Comprehensive unit tests for parsing, validation, and prompt assembly
- Resilient error handling for malformed or incomplete entity definition files
- Deterministic ordering of entity definitions in merged prompts

### Out of Scope

- Actual LLM calls or AWS Bedrock integration
- Neo4j database reads, writes, or schema operations
- Graph construction, traversal, or deduplication logic  
- Changes to the ontology design or entity definition format
- HTML parsing or document content processing
- Interactive entity definition editing or validation UI

## Entity Definitions File Format

Each entity definition file in `entities_extract/` follows this canonical markdown structure based on the architecture specification:

```markdown
# ID: <unique_type_identifier>
## Name: <Label for the entity type>
## Description: <Text description provided to LLM for extraction>
## Relations
  - <linked_entity_type_1> : <to_label> : <from_label>
  - <linked_entity_type_2> : <to_label> : <from_label>
## Examples:

### <example 1>
<additional description>

### <example 2>  
<additional description>
```

### Field Requirements

**Required Fields:**
- `ID`: Unique type identifier (becomes `entity_type` in graph). If missing, defaults to filename without `.md` extension

**Optional Fields:**
- `Name`: Human-friendly label for the entity type
- `Description`: Text provided to LLM explaining what this entity type represents and when to extract it
- `Relations`: Schema-level relationships to other entity types using format `TargetType : TO_LABEL : FROM_LABEL`
- `Examples`: Concrete examples with titles and descriptions to guide LLM understanding

### Error Handling Policy

- **Missing ID**: Default to filename without extension, log DEBUG message
- **Missing optional sections**: Continue processing, log DEBUG message for missing sections
- **Malformed relation format**: Skip invalid relations, log WARNING with line details
- **Duplicate IDs across files**: Use last loaded definition, log WARNING with conflicting filenames
- **Unparseable files**: Skip entire file, log ERROR with parsing details, continue with remaining files

## Data Structures & Loader APIs

### Core Models

```python
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from pathlib import Path

@dataclass
class RelationDefinition:
    """Schema-level relation between entity types."""
    target_type: str      # Target entity type ID
    to_label: str        # Relation label from source to target  
    from_label: str      # Relation label from target to source
    
    @classmethod
    def parse(cls, relation_line: str) -> Optional['RelationDefinition']:
        """Parse relation from 'TargetType : TO_LABEL : FROM_LABEL' format."""

@dataclass
class ExampleDefinition:
    """Example entity instance with title and description."""
    title: str           # Example title (from ### heading)
    description: str     # Example body text

@dataclass  
class EntityDefinition:
    """Complete entity type definition from markdown file."""
    id: str                                    # Entity type identifier
    name: Optional[str] = None                 # Human-friendly name
    description: Optional[str] = None          # LLM extraction guidance  
    relations: List[RelationDefinition] = field(default_factory=list)
    examples: List[ExampleDefinition] = field(default_factory=list)
    source_file: Optional[str] = None          # Origin filename
    raw_markdown: Optional[str] = None         # Original markdown content
```

### Loader APIs

```python
# kg_forge/entities/definitions.py
class EntityDefinitionLoader:
    """Loads and parses entity definitions from markdown files."""
    
    def load_entity_definitions(self, entities_dir: Path) -> List[EntityDefinition]:
        """
        Load all entity definitions from directory.
        
        Args:
            entities_dir: Directory containing *.md files
            
        Returns:
            List of parsed EntityDefinition objects
            
        Raises:
            FileNotFoundError: If entities_dir doesn't exist
        """
    
    def load_single_definition(self, file_path: Path) -> EntityDefinition:
        """Load and parse single entity definition file."""
        
    def load_prompt_template(self, template_path: Path) -> str:
        """Load prompt template markdown content."""
        
    def build_merged_prompt(self, template: str, definitions: List[EntityDefinition]) -> str:
        """
        Replace {{ENTITY_TYPE_DEFINITIONS}} placeholder with concatenated definitions.
        
        Args:
            template: Prompt template with placeholder
            definitions: Parsed entity definitions
            
        Returns:
            Complete prompt with entity definitions merged
        """
```

### File Discovery Rules

- Scan `entities_extract/` directory for `*.md` files
- Exclude `prompt_template.md` from entity definitions  
- Process files in deterministic order (sorted by filename)
- Skip non-markdown files with DEBUG log message
- Handle missing directory gracefully with clear error message

## Prompt Template Handling

### Template Structure

The `entities_extract/prompt_template.md` file contains the base LLM prompt with placeholder for entity definitions:

```markdown
You are an entity extraction assistant.

Extract entities and relationships from the provided text using these definitions:

{{ENTITY_TYPE_DEFINITIONS}}

Return results as JSON with this structure:
{
  "entities": [...],
  "relations": [...]
}

Text to analyze:
{{TEXT}}
```

### Placeholder Replacement

- **Input placeholder**: `{{ENTITY_TYPE_DEFINITIONS}}`  
- **Replacement content**: Concatenated raw markdown from all parsed entity definition files
- **Concatenation order**: Deterministic (sorted by entity ID)
- **Preserved placeholders**: `{{TEXT}}` and other placeholders remain unchanged for later steps

### Assembly Process

1. Load all entity definition files from `entities_extract/`
2. Parse each file into `EntityDefinition` objects
3. Sort definitions by entity ID for consistent ordering
4. Concatenate raw markdown content with separator (e.g., `\n---\n`)
5. Replace `{{ENTITY_TYPE_DEFINITIONS}}` in template with concatenated content
6. Return assembled prompt ready for Step 5 LLM integration

## CLI Integration

### New CLI Commands

Add entity inspection commands under the main CLI structure:

```bash
# List all loaded entity types
kg-forge entities list-types

# Show details for specific entity type  
kg-forge entities show-type --id <entity_id>

# Preview assembled LLM prompt
kg-forge entities build-prompt

# Validate entity definitions
kg-forge entities validate
```

### Command Specifications

#### `entities list-types`
```bash
kg-forge entities list-types [--format json|text] [--entities-dir PATH]
```
- Lists all entity type IDs with basic metadata (name, source file, relation count)
- Default format: human-readable table
- JSON format: structured data for scripting
- Exit code 0 on success, 1 on parsing errors

#### `entities show-type`  
```bash
kg-forge entities show-type --id <entity_id> [--entities-dir PATH]
```
- Shows complete details for specified entity type
- Includes: ID, name, description, relations, examples, source file
- Exit code 0 if found, 1 if entity ID not found

#### `entities build-prompt`
```bash  
kg-forge entities build-prompt [--entities-dir PATH] [--template PATH] [--output PATH]
```
- Assembles complete LLM prompt with entity definitions merged
- Default output: stdout (for inspection)
- Optional file output for saving assembled prompt
- Exit code 0 on success, 1 on template or parsing errors

#### `entities validate`
```bash
kg-forge entities validate [--entities-dir PATH] [--strict]
```
- Validates all entity definition files without assembly
- Reports parsing warnings and errors
- Strict mode: fail on any warnings
- Exit code 0 if valid, 1 if validation errors found

## Project Structure

```
kg_forge/
├── kg_forge/
│   ├── entities/
│   │   ├── __init__.py
│   │   ├── definitions.py          # Core loading and parsing logic
│   │   └── models.py              # Data models (EntityDefinition, etc.)
│   ├── cli/
│   │   ├── entities.py            # Entity CLI commands
│   │   └── main.py               # Updated to include entity commands
│   └── utils/
│       └── markdown.py           # Markdown parsing utilities
├── tests/
│   ├── test_entities/
│   │   ├── __init__.py
│   │   ├── test_definitions_parsing.py    # Entity definition parsing tests  
│   │   ├── test_prompt_merging.py        # Prompt assembly tests
│   │   └── test_cli_entities.py          # CLI command tests
│   └── data/
│       └── entities_test/               # Test entity definitions
│           ├── product.md              # Well-formed entity definition
│           ├── team.md                # Entity with relations
│           ├── minimal.md             # Only ID field
│           ├── malformed.md          # Parsing edge cases
│           └── prompt_template.md    # Test prompt template
└── entities_extract/                    # Real entity definitions
    ├── product.md
    ├── component.md
    ├── workstream.md
    ├── engineering_team.md
    ├── ai_ml_domain.md
    ├── technology.md
    └── prompt_template.md
```

## Dependencies

Step 3 uses only existing dependencies from previous steps:

```python
# No new dependencies required
# Existing from Step 1:
# - pydantic>=1.10.0 (for configuration models)  
# - click>=8.0.0 (for CLI framework)
# - rich>=12.0.0 (for formatted CLI output)

# Standard library modules used:
# - pathlib (file operations)
# - re (regex for parsing)
# - logging (error handling and diagnostics)
```

The implementation uses standard library features for markdown parsing (regex-based line parsing) rather than introducing heavyweight markdown parsing dependencies.

## Implementation Details

### Markdown Parsing Strategy

Use simple, robust line-based parsing rather than full markdown parsing:

```python
def parse_entity_definition(content: str) -> EntityDefinition:
    """Parse entity definition using line-based approach."""
    lines = content.split('\n')
    current_section = None
    
    for line in lines:
        if line.startswith('# ID:'):
            entity_id = line[5:].strip()
        elif line.startswith('## Name:'):
            name = line[8:].strip()
        elif line.startswith('## Description'):
            current_section = 'description'
        elif line.startswith('## Relations'):
            current_section = 'relations'
        elif line.startswith('## Examples'):
            current_section = 'examples'
        # ... continue parsing based on current_section
```

### Logging Strategy

- **INFO**: "Loaded N entity definitions from {directory}"
- **DEBUG**: "Parsing entity definition: {filename}", "Missing optional section: {section}"  
- **WARNING**: "Duplicate entity ID '{id}' in {file1} and {file2}, using {file2}", "Invalid relation format: {line}"
- **ERROR**: "Failed to parse {filename}: {error}", "Template file not found: {path}"

### Configuration Integration

Integrate with Step 1 configuration system:

```python
# Add to existing configuration model
class EntitiesConfig(BaseModel):
    entities_dir: Path = Path("entities_extract")
    prompt_template_file: str = "prompt_template.md"
    strict_validation: bool = False
```

### Error Resilience

The parsing implementation prioritizes continuing operation over strict validation:

- Unknown markdown headings are ignored (not logged)
- Missing optional sections result in empty values, not errors
- Malformed relations are skipped with warnings
- Invalid files are logged and skipped, processing continues
- Only fatal errors (missing directory, template file) stop execution

## Testing Strategy

### Unit Test Categories

#### Parsing Tests (`test_definitions_parsing.py`)

```python
class TestEntityDefinitionParsing:
    def test_parse_complete_definition(self):
        """Test parsing entity with all sections present."""
        
    def test_parse_minimal_definition_id_only(self):
        """Test parsing entity with only ID section."""
        
    def test_default_id_from_filename(self):
        """Test ID defaults to filename when missing."""
        
    def test_parse_relations_section(self):
        """Test parsing various relation formats."""
        
    def test_parse_examples_section(self):
        """Test parsing examples with nested headings."""
        
    def test_handle_malformed_sections(self):
        """Test graceful handling of parsing errors."""
        
    def test_duplicate_id_handling(self):
        """Test policy for duplicate entity IDs."""

class TestDirectoryLoading:
    def test_load_all_definitions_success(self):
        """Test loading complete entity directory."""
        
    def test_exclude_prompt_template(self):
        """Test prompt_template.md is excluded from entities."""
        
    def test_handle_missing_directory(self):
        """Test error handling for missing entities directory."""
        
    def test_deterministic_ordering(self):
        """Test entities are loaded in consistent order."""
```

#### Prompt Assembly Tests (`test_prompt_merging.py`)

```python
class TestPromptAssembly:
    def test_replace_placeholder_success(self):
        """Test successful placeholder replacement."""
        
    def test_preserve_other_placeholders(self):
        """Test {{TEXT}} and other placeholders preserved."""
        
    def test_concatenate_definitions_ordered(self):
        """Test entity definitions concatenated in correct order."""
        
    def test_handle_missing_placeholder(self):
        """Test behavior when template lacks placeholder."""
        
    def test_empty_definitions_list(self):
        """Test prompt assembly with no entity definitions."""
```

#### CLI Tests (`test_cli_entities.py`)

```python
class TestEntitiesCLI:
    def test_list_types_command(self):
        """Test entities list-types command output."""
        
    def test_show_type_command(self):
        """Test entities show-type command."""
        
    def test_build_prompt_command(self):
        """Test entities build-prompt command."""
        
    def test_validate_command(self):
        """Test entities validate command."""
        
    def test_command_error_handling(self):
        """Test CLI error cases and exit codes."""
```

### Test Data Structure

```
tests/data/entities_test/
├── product.md              # Complete, well-formed entity definition
├── team.md                 # Entity with multiple relations  
├── minimal.md             # Only ID field present
├── no_id.md              # Missing ID (should default to filename)
├── malformed_relations.md # Invalid relation formats
├── empty.md              # Empty file
└── prompt_template.md    # Test template with placeholder
```

### Integration Tests

- End-to-end test: load test entity directory, build prompt, verify all entities appear
- CLI integration test: run commands against test data, verify output format and exit codes
- Configuration test: verify entities directory and template paths can be configured

## Success Criteria

### Functional Requirements

- [ ] `load_entity_definitions()` successfully parses all valid entity files in test directory  
- [ ] Missing optional fields (Name, Description, Relations, Examples) are handled gracefully
- [ ] Entity ID defaults to filename when missing from file content
- [ ] Duplicate entity IDs are resolved using "last wins" policy with warning logged
- [ ] `build_merged_prompt()` successfully replaces `{{ENTITY_TYPE_DEFINITIONS}}` placeholder
- [ ] All entity definitions appear in merged prompt in deterministic order
- [ ] CLI commands (`list-types`, `show-type`, `build-prompt`, `validate`) execute successfully

### Technical Requirements

- [ ] All parsing uses only standard library (no heavy markdown parsing dependencies)
- [ ] Error handling is resilient - malformed files don't crash the loader
- [ ] Logging follows established patterns (INFO/DEBUG/WARNING/ERROR levels)  
- [ ] Configuration integrates with Step 1 settings system
- [ ] API interfaces are ready for integration with Step 5 (LLM calls)

### Quality Requirements

- [ ] Unit test coverage >90% for entities module
- [ ] All edge cases covered: missing files, malformed content, empty sections
- [ ] CLI help text is clear and follows established patterns
- [ ] Error messages provide actionable guidance for fixing entity definition files
- [ ] No external service calls (Neo4j, LLMs) in Step 3 implementation

### Integration Requirements  

- [ ] Entity definitions from existing `entities_extract/` directory load successfully
- [ ] Assembled prompts are valid and ready for LLM consumption in Step 5
- [ ] CLI commands integrate cleanly with existing `kg-forge` command structure
- [ ] Configuration values can be overridden via existing mechanisms (CLI, env, YAML)

## Next Steps

Step 3 creates the ontology foundation that bridges curated content from Step 2 with LLM-based entity extraction in Step 5. The parsed entity definitions and assembled prompts will be consumed by the LLM integration layer to extract structured entities from the HTML-derived text content.

Step 4 (Neo4j Bootstrap) will use the entity type metadata from Step 3 to create appropriate graph schema constraints and indexes. Step 5 (LLM Integration) will use the assembled prompts to drive AWS Bedrock calls for actual entity extraction, with the results eventually stored in the graph database according to the relationships defined in the entity definitions.

The modular design ensures that ontology changes in `entities_extract/` can be quickly tested and validated through the CLI inspection commands before proceeding to the more expensive LLM extraction and graph storage operations.