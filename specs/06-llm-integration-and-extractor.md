# Step 6: LLM Integration & Entity Extraction

## Overview

Step 6 introduces a pluggable LLM-based extraction engine that builds prompts using curated documents (from Step 3) and entity definition templates (from Step 4), calls AWS Bedrock (or a generic LLM client abstraction), and parses the response into a structured `{"entities": [...]}` payload suitable for ingestion into the Knowledge Graph. This step provides the core extraction capability that will be orchestrated by the ingest pipeline in Step 7.

Step 6 explicitly does NOT write anything to Neo4j (no graph persistence yet), orchestrate the full ingest pipeline over folders (that's Step 7), perform dedup/merge/pruning of entities, or handle visualization or rendering.

## Scope

### In Scope

- Implement a **prompt builder** that:
  - Takes curated document content (from Step 2's document model)
  - Takes entity definitions and merged prompt template (from Step 3)
  - Builds a final prompt string for the LLM extraction call
- Implement an **LLM client abstraction**:
  - Interface/protocol for "extract entities from text"
  - One concrete implementation for AWS Bedrock using LlamaIndex client
  - One local "fake LLM" implementation used in tests (no network calls)
- Implement **response parser**:
  - Parse LLM output (JSON or JSON-like) into a Python model `ExtractionResult` with `entities: list[ExtractedEntity]`
  - Validate parsed results against expected schema
- Implement **error handling & retry** rules as per architecture seeds:
  - Log error if output cannot be parsed
  - Retry once on failure
  - Maintain a counter of consecutive failures and abort after >10
  - Skip individual failing documents while continuing batch processing
- Implement a **CLI command** to:
  - Run the extraction pipeline on sample input
  - Display the parsed result for inspection
  - Support both real and fake LLM backends
- Unit tests for:
  - Prompt construction logic
  - Response parsing and validation
  - Error handling & retry mechanisms
  - Fake LLM implementation

### Out of Scope

- Writing to Neo4j or creating `:Doc` / `:Entity` nodes (covered in Step 6)
- Walking folder trees and orchestrating ingest over many files (that's Step 6)
- Deduplication, merging, or pruning entities
- Changes to the CLI foundation beyond what is needed for new subcommands
- Changes to the ontology design or entity definition format (those are defined in Step 3)
- Full ingest pipeline orchestration or batch processing workflows

## Prompt & Extraction Schema

### Expected LLM Output Schema

The LLM must return a JSON object with the following structure:

```json
{
  "entities": [
    {
      "type": "Product",
      "name": "Knowledge Discovery",
      "confidence": 0.92
    },
    {
      "type": "EngineeringTeam", 
      "name": "Platform Engineering",
      "confidence": 0.89
    }
  ]
}
```

### Schema Validation Rules

- `entities`: Required array, may be empty
- Each entity object must contain:
  - `type`: Required string that matches an `entity_type` ID from Step 3 definitions
  - `name`: Required non-empty string
  - `confidence`: Optional float between 0.0 and 1.0 (default: 1.0 if not provided)

### Prompt Composition

The prompt builder constructs the final prompt by combining:

1. **High-level instructions**: Task description and output format requirements
2. **Entity type definitions**: Merged content from Step 3's entity definition files
3. **Document content**: Curated text from Step 2's document model
4. **Formatting instructions**: JSON schema requirements and examples

Example prompt structure:
```
You are an expert at extracting entities from technical documentation.

Extract entities from the following text according to these definitions:

{{ENTITY_TYPE_DEFINITIONS}}

Document content:
{{DOCUMENT_CONTENT}}

Return valid JSON with entities found in the document:
{"entities": [...]}
```

## LLM Client & Adapter APIs

### Core Interfaces

Define abstractions in `kg_forge/llm/client.py`:

```python
from typing import Protocol
from dataclasses import dataclass
from abc import ABC, abstractmethod

@dataclass
class ExtractedEntity:
    type: str
    name: str
    confidence: float = 1.0

@dataclass 
class ExtractionResult:
    entities: list[ExtractedEntity]

class LLMExtractor(Protocol):
    def extract_entities(self, prompt: str) -> ExtractionResult:
        """Extract entities from prompt, return structured result."""
        ...
```

### Concrete Implementations

- **BedrockLLMExtractor**: 
  - Uses LlamaIndex Bedrock client as configured in architecture seeds
  - Takes model name, region, and credentials from Step 1 configuration
  - Implements timeout and token limit handling
  - Handles AWS-specific errors and retries

- **FakeLLMExtractor**: 
  - Returns deterministic, configurable outputs for given inputs
  - Loads canned responses from `tests/data/llm_responses/*.json`
  - Supports injecting malformed responses for negative testing
  - No network calls or external dependencies

### Configuration Integration

The LLM client uses configuration from Step 1's settings system:

```yaml
aws:
  access_key_id: ${AWS_ACCESS_KEY_ID}
  secret_access_key: ${AWS_SECRET_ACCESS_KEY}
  default_region: us-east-1
  bedrock_model_name: anthropic.claude-3-haiku-20240307-v1:0
  bedrock_max_tokens: 4000
  bedrock_temperature: 0.1
```

## Error Handling & Resilience

### Failure Classification

The following are considered extraction failures:
- HTTP/network errors from Bedrock API
- Timeout exceptions
- Invalid JSON responses that cannot be parsed
- Valid JSON that doesn't match the expected schema
- Empty or null responses from the LLM

### Retry Logic

- **Single failure**: Log warning, retry the exact same call once
- **Parse failure**: Log the raw response for debugging, attempt retry
- **Network failure**: Log error details, attempt retry after brief delay

### Consecutive Failure Handling

- Maintain a global consecutive failure counter across all extraction calls
- If more than 10 extraction calls in a row fail:
  - Log critical error with failure details
  - Raise `ExtractionAbortError` 
  - Calling process should exit with non-zero code
- Reset counter to 0 on any successful extraction

### Batch Processing Resilience

For batch scenarios (used by Step 6):
- Single document failure causes that document to be skipped
- Log document ID and error details
- Continue processing remaining documents
- Return partial results with failure summary

### Logging Strategy

- **INFO**: Successful extractions with entity counts
- **WARNING**: Recoverable failures, retries, skipped documents
- **ERROR**: Abort conditions, consecutive failure threshold reached
- **DEBUG**: Raw prompts, responses, parsing details

Include correlation context:
- Document ID or source identifier
- Attempt number for retries
- Failure count in current batch

## CLI Integration

### New Command: `llm-test`

Add a new CLI subcommand for testing LLM extraction:

```bash
kg-forge llm-test [OPTIONS] INPUT
```

#### Arguments and Options

- `INPUT`: Path to text file containing curated document content
- `--model TEXT`: Override Bedrock model name from config
- `--fake-llm`: Use fake LLM instead of Bedrock (for testing)
- `--output-format [json|text]`: Output format (default: text)
- `--namespace TEXT`: Namespace for entity definitions (default: "default")
- `--entities-dir PATH`: Override entity definitions directory
- `--template-file PATH`: Override prompt template file

#### Example Usage

```bash
# Test with real Bedrock
kg-forge llm-test sample_doc.txt --model anthropic.claude-3-sonnet

# Test with fake LLM
kg-forge llm-test sample_doc.txt --fake-llm

# JSON output for programmatic use
kg-forge llm-test sample_doc.txt --fake-llm --output-format json
```

#### Command Behavior

1. Load configuration from Step 1 settings
2. Load entity definitions from Step 3 (respecting `--entities-dir`)
3. Load and merge prompt template
4. Read input text content
5. Build extraction prompt
6. Initialize LLM client (real or fake based on `--fake-llm`)
7. Call extraction with error handling
8. Parse and validate result
9. Display entities in requested format
10. Exit with code 0 on success, non-zero on failure

The command does NOT write to Neo4j and is purely for debugging and verification.

## Project Structure

```
kg_forge/
├── llm/
│   ├── __init__.py
│   ├── client.py          # LLMExtractor protocol and implementations
│   ├── prompt_builder.py  # Prompt construction logic
│   ├── parser.py          # Response parsing and validation
│   └── exceptions.py      # LLM-specific exception classes
├── cli/
│   ├── llm_test.py        # CLI command implementation
│   └── main.py           # Updated to include llm-test command
└── config/
    └── settings.py       # Updated with AWS Bedrock configuration

tests/
├── test_llm/
│   ├── __init__.py
│   ├── test_client.py         # LLM client implementations
│   ├── test_prompt_builder.py # Prompt construction
│   ├── test_parser.py         # Response parsing
│   ├── test_error_handling.py # Retry and failure logic
│   └── test_fake_llm.py       # Fake LLM behavior
├── test_cli/
│   └── test_llm_test.py       # CLI command testing
└── data/
    └── llm_responses/
        ├── valid_response.json      # Sample valid responses
        ├── malformed_response.json  # Invalid JSON for testing
        └── schema_invalid.json      # Valid JSON, invalid schema
```

## Dependencies

### New Runtime Dependencies

Add to `requirements.txt`:

```
# LLM Integration
llama-index-llms-bedrock>=0.1.0
boto3>=1.34.0
botocore>=1.34.0
```

### Development Dependencies

Add to test requirements or dev section:

```
# LLM Testing
responses>=0.24.0    # For mocking HTTP calls in tests
moto[bedrock]>=4.0.0 # For AWS service mocking (optional)
```

### LlamaIndex Integration

Use the official LlamaIndex Bedrock LLM client:
- `llama-index-llms-bedrock` package provides `BedrockLLM` class
- Handles AWS credential management and region configuration
- Provides consistent interface with other LlamaIndex LLM clients
- Supports streaming and non-streaming responses

No heavy additional dependencies unrelated to LLM integration are introduced.

## Implementation Details

### Prompt Builder (`kg_forge/llm/prompt_builder.py`)

```python
class PromptBuilder:
    def __init__(self, entity_loader: EntityDefinitionLoader):
        self.entity_loader = entity_loader
    
    def build_prompt(self, document_content: str, entities_dir: Path, 
                    template_file: Path) -> str:
        # Load and merge entity definitions
        definitions = self.entity_loader.load_entity_definitions(entities_dir)
        template_content = self.entity_loader.load_prompt_template(template_file)
        merged_prompt = self.entity_loader.build_merged_prompt(template_content, definitions)
        
        # Inject document content
        return merged_prompt.replace('{{DOCUMENT_CONTENT}}', document_content)
```

### Response Parser (`kg_forge/llm/parser.py`)

```python
class ResponseParser:
    def parse_extraction_result(self, response_text: str) -> ExtractionResult:
        try:
            # Strict JSON parsing (preferred approach)
            data = json.loads(response_text.strip())
            
            # Validate top-level structure
            if not isinstance(data, dict) or 'entities' not in data:
                raise ValidationError("Response missing 'entities' field")
            
            # Parse entities
            entities = []
            for entity_data in data['entities']:
                entity = self._parse_entity(entity_data)
                entities.append(entity)
            
            return ExtractionResult(entities=entities)
            
        except json.JSONDecodeError as e:
            raise ParseError(f"Invalid JSON response: {e}")
    
    def _parse_entity(self, entity_data: dict) -> ExtractedEntity:
        # Validate required fields
        if 'type' not in entity_data or 'name' not in entity_data:
            raise ValidationError("Entity missing required 'type' or 'name' field")
        
        return ExtractedEntity(
            type=entity_data['type'],
            name=entity_data['name'],
            confidence=entity_data.get('confidence', 1.0)
        )
```

### Configuration Integration

LLM configuration uses Step 1's settings system:

```python
@dataclass
class AWSConfig:
    access_key_id: str
    secret_access_key: str  
    default_region: str = "us-east-1"
    bedrock_model_name: str = "anthropic.claude-3-haiku-20240307-v1:0"
    bedrock_max_tokens: int = 4000
    bedrock_temperature: float = 0.1
```

### Logging Strategy

Include structured logging with correlation context:

```python
logger.info("Starting entity extraction", extra={
    "doc_id": doc_id,
    "model": model_name,
    "prompt_length": len(prompt)
})

logger.warning("Extraction failed, retrying", extra={
    "doc_id": doc_id,
    "attempt": 2,
    "error": str(exception)
})

logger.error("Consecutive failure threshold exceeded", extra={
    "failure_count": consecutive_failures,
    "abort_threshold": 10
})
```

## Testing Strategy

### Unit Tests

**Prompt Builder Tests** (`test_prompt_builder.py`):
- Given fixed document content + entity definitions + template, assert prompt contains all required sections
- Test template variable substitution works correctly
- Test handling of missing or malformed entity definitions
- Test prompt length and structure validation

**Parser Tests** (`test_parser.py`):
- Parse valid JSON responses into `ExtractionResult` objects
- Handle missing optional fields (confidence defaults to 1.0)
- Gracefully reject invalid JSON with appropriate error messages  
- Validate entity type values against known types
- Test edge cases: empty entities list, malformed entity objects

**Error Handling Tests** (`test_error_handling.py`):
- Simulate LLM failures and verify retry behavior (exactly once)
- Test consecutive failure counter increments and reset logic
- Verify abort behavior after >10 consecutive failures
- Test individual document skip behavior in batch scenarios

**Fake LLM Tests** (`test_fake_llm.py`):
- Returns deterministic responses for known input prompts
- Supports injecting malformed responses for negative testing
- Configurable via test data files
- No network calls or external dependencies

### Integration Tests

**CLI Command Tests** (`test_llm_test.py`):
- Test `kg-forge llm-test` against sample curated document
- Verify exit codes: 0 for success, non-zero for failures
- Test both text and JSON output formats
- Verify fake LLM mode works without network calls
- Assert printed output contains expected entity information

### Test Data

Create realistic test data in `tests/data/`:
- `sample_document.txt`: Curated text from Confluence export
- `llm_responses/valid_response.json`: Complete valid extraction result
- `llm_responses/malformed.json`: Invalid JSON for error testing
- `llm_responses/missing_fields.json`: Valid JSON with schema violations

### CI/CD Considerations

- All tests use fake LLM by default - no real Bedrock calls required for CI
- Optional integration tests with real Bedrock behind feature flag
- Environment variable `KG_FORGE_ENABLE_BEDROCK_TESTS=1` enables real API tests
- Coverage target: >90% for LLM module components

## Success Criteria

Step 5 is considered complete when:

- [ ] For a given curated document and entity definitions, the prompt builder produces a well-formed prompt containing all required sections
- [ ] Given a valid sample Bedrock-style JSON response, the parser produces the correct `ExtractionResult` with proper entity objects
- [ ] The retry logic behaves exactly as specified: retry once on failure, abort after >10 consecutive failures
- [ ] The consecutive failure counter increments on errors and resets on success
- [ ] `kg-forge llm-test --fake-llm sample.txt` runs end-to-end, exits with code 0, and prints parsed entities in human-readable format
- [ ] `kg-forge llm-test --fake-llm --output-format json sample.txt` produces valid JSON output
- [ ] No Neo4j writes occur anywhere in Step 5 implementations
- [ ] All unit tests pass with >90% coverage for LLM modules
- [ ] Integration tests demonstrate the fake LLM can substitute for real Bedrock during development
- [ ] Error handling gracefully manages network failures, parse errors, and invalid responses
- [ ] Configuration integration works with Step 1's settings system for AWS credentials and model parameters

## Next Steps

Step 5 provides the reusable LLM extraction component that Step 6 (Ingest Pipeline) will orchestrate as part of the `kg-forge ingest` command. Step 6 will combine the HTML parsing capabilities from Step 2, entity definitions from Step 3, Neo4j operations from Step 4, and the LLM extraction from Step 5 to create the complete ingestion workflow that reads HTML files, extracts entities, and populates the Knowledge Graph. The extraction engine developed in Step 5 will be called for each curated document during batch ingestion, with the parsed results written to Neo4j using the schema and client from Step 4.