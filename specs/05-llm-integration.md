# Step 5: LLM Integration for Entity Extraction

**Status**: Planned  
**Previous Step**: [04-neo4j-bootstrap.md](./04-neo4j-bootstrap.md)  
**Next Step**: 06-ingest-pipeline.md (TBD)

## Overview

This step implements LLM integration for entity extraction from documents. We'll use AWS Bedrock with Claude to extract entities defined in our entity definition files, with an abstraction layer to potentially swap to Knowledge Enrichment API later.

## Goals

1. ✅ Generate extraction prompts from entity definitions and templates
2. ✅ Parse LLM responses into structured entity data
3. ✅ Abstract LLM calls behind an interface for future swapping
4. ✅ Implement AWS Bedrock client with Claude
5. ✅ Handle LLM failures gracefully (retry logic, error tracking)
6. ✅ Add CLI command to test extraction without full ingestion
7. ✅ Comprehensive testing (unit tests with mocked LLM, test data)

## Architecture

### Abstraction Layer

We want an abstraction that allows swapping between multiple LLM providers:
- **OpenRouter**: Unified API for multiple LLM providers (Claude, GPT-4, etc.)
- **AWS Bedrock**: AWS-hosted Claude models
- **Future**: Knowledge Enrichment REST API

**Provider Selection Logic:**
1. If `OPENROUTER_API_KEY` is set → use OpenRouterExtractor
2. Else if AWS credentials (`AWS_ACCESS_KEY_ID`) set → use BedrockExtractor  
3. Else → raise configuration error

```
Document → create_extractor() (factory)
              ↓
         EntityExtractor (interface)
              ↓
    ┌─────────┴──────────┐
    ↓                    ↓
OpenRouterExtractor  BedrockExtractor
    ↓                    ↓
OpenRouter API      AWS Bedrock API
```

### Components

```
kg_forge/
├── extractors/
│   ├── __init__.py
│   ├── base.py              # Abstract base class
│   ├── factory.py           # Factory to create extractor based on config
│   ├── bedrock.py           # AWS Bedrock implementation
│   ├── openrouter.py        # OpenRouter implementation
│   ├── prompt_builder.py    # Build prompts from templates
│   └── parser.py            # Parse LLM responses
├── cli/
│   └── extract.py           # New: test extraction command
└── models/
    └── extraction.py        # Extraction result models
```

## Data Structures

### ExtractionRequest
```python
@dataclass
class ExtractionRequest:
    """Request for entity extraction."""
    content: str                    # Document text to analyze
    entity_types: List[str]         # Types to extract (or [] for all)
    namespace: str = "default"      # For context
    max_tokens: int = 4000          # Max response tokens
```

### ExtractionResult
```python
@dataclass
class ExtractionResult:
    """Result of entity extraction."""
    entities: List[ExtractedEntity]
    raw_response: Optional[str] = None
    model_name: Optional[str] = None
    tokens_used: Optional[int] = None
    extraction_time: Optional[float] = None
    success: bool = True
    error: Optional[str] = None
```

### ExtractedEntity
```python
@dataclass
class ExtractedEntity:
    """Single extracted entity."""
    entity_type: str           # e.g., "Product", "Team"
    name: str                  # e.g., "Knowledge Discovery"
    confidence: float = 1.0    # 0.0-1.0, LLM confidence if provided
    properties: Dict[str, Any] = field(default_factory=dict)
```

## Implementation Details

### 1. PromptBuilder (`kg_forge/extractors/prompt_builder.py`)

**Responsibilities:**
- Load prompt template from `entities_extract/prompt_template.md`
- Load entity definitions from `entities_extract/*.md`
- Merge template with entity definitions
- Support filtering by entity types

**Key Methods:**
```python
class PromptBuilder:
    def __init__(self, entities_dir: Path = Path("entities_extract")):
        """Initialize with entity definitions directory."""
        
    def build_extraction_prompt(
        self, 
        content: str, 
        entity_types: Optional[List[str]] = None
    ) -> str:
        """Build complete prompt for entity extraction.
        
        Args:
            content: Document text to extract from
            entity_types: Specific types to extract, or None for all
            
        Returns:
            Complete prompt with instructions, entity defs, and content
        """
```

**Prompt Structure:**
```
1. System instructions from template
2. Entity type definitions (filtered if needed)
3. Output format requirements (JSON)
4. Document content to analyze
5. Reminder to output only valid JSON
```

### 2. ResponseParser (`kg_forge/extractors/parser.py`)

**Responsibilities:**
- Parse LLM JSON responses
- Handle various response formats
- Validate entity structure
- Extract confidence scores if present

**Key Methods:**
```python
class ResponseParser:
    def parse(self, response_text: str) -> List[ExtractedEntity]:
        """Parse LLM response into structured entities.
        
        Handles:
        - JSON wrapped in markdown code blocks
        - Missing confidence scores
        - Unexpected fields
        - Malformed JSON (raises ParseError)
        """
```

**Expected LLM Response Format:**
```json
{
  "entities": [
    {
      "type": "Product",
      "name": "Knowledge Discovery",
      "confidence": 0.92
    },
    {
      "type": "Team",
      "name": "Platform Engineering",
      "confidence": 0.89
    }
  ]
}
```

### 3. EntityExtractor Base (`kg_forge/extractors/base.py`)

**Abstract Interface:**
```python
from abc import ABC, abstractmethod

class EntityExtractor(ABC):
    """Abstract base for entity extraction."""
    
    @abstractmethod
    def extract(self, request: ExtractionRequest) -> ExtractionResult:
        """Extract entities from content.
        
        Args:
            request: Extraction request with content and config
            
        Returns:
            Extraction result with entities or error
            
        Raises:
            ExtractionError: On unrecoverable extraction failure
        """
        pass
    
    @abstractmethod
    def get_model_name(self) -> str:
        """Get the model/service name being used."""
        pass
```

### 4. Factory (`kg_forge/extractors/factory.py`)

**Auto-select implementation based on configuration:**
```python
def create_extractor(settings: Optional[Settings] = None) -> EntityExtractor:
    """Create appropriate extractor based on configuration.
    
    Priority:
    1. OpenRouter (if OPENROUTER_API_KEY set)
    2. Bedrock (if AWS credentials set)
    3. Error (no valid configuration)
    """
    if settings is None:
        settings = get_settings()
    
    # Check for OpenRouter first
    if settings.openrouter and settings.openrouter.api_key:
        logger.info("Using OpenRouter extractor")
        return OpenRouterExtractor(
            api_key=settings.openrouter.api_key,
            model_name=settings.openrouter.model_name,
            max_retries=settings.openrouter.max_retries,
        )
    
    # Fall back to Bedrock
    if settings.bedrock and has_aws_credentials():
        logger.info("Using AWS Bedrock extractor")
        return BedrockExtractor(
            model_name=settings.bedrock.model_name,
            region=settings.bedrock.region,
            max_retries=settings.bedrock.max_retries,
        )
    
    raise ConfigurationError(
        "No LLM provider configured. Set OPENROUTER_API_KEY or AWS credentials."
    )
```

### 5. OpenRouterExtractor (`kg_forge/extractors/openrouter.py`)

**Implementation:**
```python
from openai import OpenAI

class OpenRouterExtractor(EntityExtractor):
    """OpenRouter implementation (OpenAI-compatible API)."""
    
    def __init__(
        self,
        api_key: str,
        model_name: str = "anthropic/claude-3-haiku",
        base_url: str = "https://openrouter.ai/api/v1",
        max_retries: int = 1,
        timeout: int = 30
    ):
        """Initialize OpenRouter client."""
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        self.model_name = model_name
        self.max_retries = max_retries
        self.timeout = timeout
        
    def extract(self, request: ExtractionRequest) -> ExtractionResult:
        """Extract entities using OpenRouter."""
        # Build prompt
        prompt = self.prompt_builder.build_extraction_prompt(
            request.content,
            request.entity_types
        )
        
        # Call OpenRouter API
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=request.max_tokens,
            timeout=self.timeout
        )
        
        # Parse response
        # ... similar to Bedrock implementation
```

**Configuration (from .env):**
```env
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL_NAME=anthropic/claude-3-haiku
OPENROUTER_MAX_RETRIES=1
OPENROUTER_TIMEOUT=30
```

### 6. BedrockExtractor (`kg_forge/extractors/bedrock.py`)

**Implementation:**
```python
class BedrockExtractor(EntityExtractor):
    """AWS Bedrock implementation using Claude."""
    
    def __init__(
        self,
        model_name: str = "anthropic.claude-3-haiku-20240307-v1:0",
        region: str = "us-east-1",
        max_retries: int = 1,
        timeout: int = 30
    ):
        """Initialize Bedrock client."""
        
    def extract(self, request: ExtractionRequest) -> ExtractionResult:
        """Extract entities using Bedrock."""
```

**Error Handling:**
- **Parse errors**: Retry once, then skip document (log warning)
- **API errors** (rate limit, timeout): Retry once with exponential backoff
- **Auth errors**: Fail fast with clear error message
- **Tracking**: Count consecutive failures, abort if >10 in a row

**Configuration (from .env):**
```env
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=us-east-1
BEDROCK_MODEL_NAME=anthropic.claude-3-haiku-20240307-v1:0
BEDROCK_MAX_RETRIES=1
BEDROCK_TIMEOUT=30
```

### 7. CLI Command (`kg_forge/cli/extract.py`)

**New Command: `kg-forge extract`**

Test entity extraction without full ingestion pipeline.

**Usage:**
```bash
# Extract from a single file
kg-forge extract test-doc.html

# Extract specific entity types only
kg-forge extract test-doc.html --types Product Team

# Filter by confidence threshold
kg-forge extract test-doc.html --min-confidence 0.7

# Use alternate prompt template
kg-forge extract test-doc.html --prompt-template custom_prompt.md

# Override model
kg-forge extract test-doc.html --model anthropic.claude-3-sonnet-20240229-v1:0

# Output format
kg-forge extract test-doc.html --format json
kg-forge extract test-doc.html --format text
```

**Output (text format):**
```
Extracting entities from: test-doc.html
Model: anthropic.claude-3-haiku-20240307-v1:0

Found 5 entities:

Product:
  - Knowledge Discovery (confidence: 0.92)
  - Content Lake (confidence: 0.88)

Team:
  - Platform Engineer

ing (confidence: 0.89)
  - AI/ML Team (confidence: 0.85)

Technology:
  - Python (confidence: 0.91)

Extraction time: 2.3s
Tokens used: 1245
```

**Output (JSON format):**
```json
{
  "file": "test-doc.html",
  "model": "anthropic.claude-3-haiku-20240307-v1:0",
  "entities": [
    {"type": "Product", "name": "Knowledge Discovery", "confidence": 0.92},
    {"type": "Product", "name": "Content Lake", "confidence": 0.88}
  ],
  "metadata": {
    "extraction_time": 2.3,
    "tokens_used": 1245,
    "entity_types_requested": ["Product", "Team", "Technology"]
  }
}
```

## Testing Strategy

### Unit Tests

**`tests/test_extractors/test_prompt_builder.py`:**
- Test template loading
- Test entity definition merging
- Test filtering by entity types
- Test placeholder replacement

**`tests/test_extractors/test_parser.py`:**
- Test parsing valid JSON responses
- Test handling markdown-wrapped JSON
- Test missing confidence scores
- Test malformed JSON (should raise error)
- Test empty responses

**`tests/test_extractors/test_bedrock.py`:**
- Mock boto3 client
- Test successful extraction
- Test parse error with retry
- Test API error with retry
- Test consecutive failure tracking
- Test timeout handling

### Test Data

**`tests/test_data/llm_responses/`:**
```
llm_responses/
├── valid_response.json           # Well-formed response
├── markdown_wrapped.txt          # JSON in ```json...``` block
├── missing_confidence.json       # No confidence scores
├── malformed.txt                 # Invalid JSON
├── empty_entities.json           # {"entities": []}
└── partial_response.json         # Incomplete JSON
```

**`tests/test_data/documents/`:**
```
documents/
├── simple.txt                    # Short doc with 2-3 entities
├── complex.html                  # Real Confluence export
└── empty.txt                     # No meaningful content
```

### Integration Test (Optional)

If AWS credentials available:
```python
@pytest.mark.integration
@pytest.mark.skipif(not has_aws_creds(), reason="AWS credentials required")
def test_real_bedrock_extraction():
    """Test with real Bedrock API (requires credentials)."""
```

## File Structure

```
kg_forge/
├── kg_forge/
│   ├── extractors/
│   │   ├── __init__.py
│   │   ├── base.py              # EntityExtractor ABC
│   │   ├── factory.py           # create_extractor() factory
│   │   ├── bedrock.py           # BedrockExtractor
│   │   ├── openrouter.py        # OpenRouterExtractor
│   │   ├── prompt_builder.py   # PromptBuilder
│   │   └── parser.py            # ResponseParser
│   ├── models/
│   │   └── extraction.py        # ExtractionRequest, ExtractionResult, ExtractedEntity
│   └── cli/
│       └── extract.py           # CLI command
├── tests/
│   ├── test_extractors/
│   │   ├── __init__.py
│   │   ├── test_factory.py      # Factory selection logic
│   │   ├── test_prompt_builder.py
│   │   ├── test_parser.py
│   │   ├── test_bedrock.py
│   │   ├── test_openrouter.py
│   │   └── conftest.py          # Shared fixtures
│   └── test_data/
│       ├── llm_responses/       # Sample LLM responses
│       └── documents/           # Sample documents
└── requirements.txt             # Add: boto3, openai
```

## Dependencies

Add to `requirements.txt`:
```
# LLM Providers
boto3>=1.34.0          # AWS Bedrock
botocore>=1.34.0       # AWS Bedrock
openai>=1.12.0         # OpenRouter (OpenAI-compatible API)
```

## Configuration Updates

**Add to `kg_forge/config/settings.py`:**
```python
class OpenRouterConfig(BaseModel):
    """OpenRouter configuration."""
    api_key: Optional[str] = None
    model_name: str = "anthropic/claude-3-haiku"
    base_url: str = "https://openrouter.ai/api/v1"
    max_retries: int = 1
    timeout: int = 30
    min_confidence: float = 0.0
    max_tokens_per_request: int = 100000

class BedrockConfig(BaseModel):
    """AWS Bedrock configuration."""
    model_name: str = "anthropic.claude-3-haiku-20240307-v1:0"
    region: str = "us-east-1"
    max_retries: int = 1
    timeout: int = 30
    max_consecutive_failures: int = 10
    min_confidence: float = 0.0
    max_tokens_per_request: int = 100000

class Settings:
    # ... existing ...
    openrouter: Optional[OpenRouterConfig] = None
    bedrock: Optional[BedrockConfig] = None
```

**Add to `.env.example`:**
```env
# OpenRouter Configuration (preferred - easier to get started)
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL_NAME=anthropic/claude-3-haiku
OPENROUTER_MAX_RETRIES=1
OPENROUTER_TIMEOUT=30

# AWS Bedrock Configuration (alternative)
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here
AWS_DEFAULT_REGION=us-east-1
BEDROCK_MODEL_NAME=anthropic.claude-3-haiku-20240307-v1:0
BEDROCK_MAX_RETRIES=1
BEDROCK_TIMEOUT=30

# Note: If both are configured, OpenRouter takes priority
```

## Success Criteria

- [ ] PromptBuilder correctly merges templates and entity definitions
- [ ] ResponseParser handles all test response formats
- [ ] Factory correctly selects provider based on configuration
- [ ] OpenRouterExtractor successfully calls OpenRouter API (with mocks)
- [ ] BedrockExtractor successfully calls AWS Bedrock (with mocks)
- [ ] Error handling: retries work, consecutive failures tracked
- [ ] CLI `extract` command works with sample documents
- [ ] Unit tests: 25+ covering all components (including factory)
- [ ] Documentation: Updated README with extract command
- [ ] Can extract entities from test documents without errors

## Design Decisions (Finalized)

1. **Prompt optimization**: ✅ **One-shot prompting**
   - Simpler, cheaper, faster
   - Entity definitions already contain examples
   - Can add few-shot examples later if quality is poor

2. **Entity type filtering**: ✅ **One call for all types**
   - Single LLM call extracts all entity types at once
   - Cheaper and faster than separate calls
   - CLI still supports `--types` filter to limit extraction if needed

3. **Confidence threshold**: ✅ **Configurable with parameter**
   - Add `--min-confidence` parameter (default: 0.0, keep all)
   - Users can filter if desired: `--min-confidence 0.7`
   - Preserves all data by default, allows filtering on demand

4. **Context window**: ✅ **Truncate with warning**
   - Truncate documents exceeding context limit
   - Log warning with document ID and original length
   - Simple for Step 5, can add chunking in Step 6 if needed

5. **Cost tracking**: ✅ **Log token usage**
   - Track input/output tokens for each API call
   - Include in ExtractionResult metadata
   - Log to console/file
   - Users can calculate costs using token counts

## Next Steps (Step 6)

Once Step 5 is complete:
- Integrate extractor into ingestion pipeline
- Add document → entities → graph flow
- Implement `process_before_store` hook
- Implement `process_after_batch` hook
- Add deduplication logic
- Full end-to-end testing

---

**Ready for review and implementation!**
