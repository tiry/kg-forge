# Spec 10: Verbose Mode for CLI Commands

## Overview

Add a `--verbose` flag to CLI commands to provide detailed visibility into internal operations. Initially implemented for the `extract` command to show LLM interactions, the feature is designed for easy extension to other commands.

## Motivation

- **Debugging**: See exactly what prompts are sent to the LLM and what responses are received
- **Transparency**: Understand how the tool processes data, especially during entity extraction
- **Cost tracking**: Monitor token usage and LLM interactions
- **Development**: Easier troubleshooting when tuning prompts or investigating issues

## Requirements

### 1. Verbose Flag

Add a global `--verbose` flag that can be used with any command:

```bash
kg-forge extract --verbose entities_extract/ test_data/doc.html
kg-forge pipeline run --verbose test_data/
kg-forge ingest --verbose test_data/ --namespace test
```

### 2. Extract Command - LLM Interaction Display

When `--verbose` is enabled for the `extract` command, display:

**Before LLM Call:**
- The complete prompt text being sent
- Entity type being extracted
- Model being used (OpenRouter, Bedrock, etc.)
- Token count estimate (if available)

**After LLM Call:**
- Raw LLM response (before parsing)
- Response time/latency
- Token usage (if provided by the API)
- Success/failure status

**Output Format:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 LLM EXTRACTION REQUEST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Entity Type: Technology
Model: openrouter/anthropic/claude-3-haiku
Estimated Tokens: ~1,250

──────────────────────────────────────────────────────────
📤 PROMPT
──────────────────────────────────────────────────────────
[Full prompt text here...]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📥 LLM RESPONSE (took 2.3s)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tokens Used: 1,245 input + 187 output = 1,432 total
Status: ✓ Success

──────────────────────────────────────────────────────────
📄 RAW RESPONSE
──────────────────────────────────────────────────────────
[Full JSON response here...]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 3. Extensibility Design

The verbose mode should be designed as a reusable component:

**VerboseLogger Utility:**
```python
class VerboseLogger:
    """Handles verbose output formatting across commands."""
    
    def __init__(self, enabled: bool, logger):
        self.enabled = enabled
        self.logger = logger
    
    def section_header(self, title, icon=""):
        """Print a section header."""
        
    def llm_request(self, entity_type, model, prompt, tokens=None):
        """Log LLM request details."""
        
    def llm_response(self, response, elapsed_time, tokens=None, status="success"):
        """Log LLM response details."""
        
    def operation(self, operation_name, details):
        """Log a generic operation (for future commands)."""
```

### 4. Configuration

Verbose mode can be enabled via:

1. **CLI Flag** (highest priority): `--verbose`
2. **Environment Variable**: `KG_FORGE_VERBOSE=1`
3. **Config File**: 
   ```yaml
   app:
     verbose: true
   ```

## Implementation Plan

### Phase 1: Infrastructure
1. Add `--verbose` flag to main CLI parser
2. Create `kg_forge/utils/verbose.py` with `VerboseLogger` class
3. Pass verbose flag through settings/context

### Phase 2: Extract Command
1. Update `kg_forge/extractors/llm_base.py`:
   - Add verbose logger integration
   - Log prompt before LLM call
   - Log response after LLM call
2. Update `kg_forge/cli/extract.py`:
   - Pass verbose flag to extractors
3. Test with both OpenRouter and Bedrock extractors

### Phase 3: Testing
1. Unit tests for VerboseLogger
2. Integration tests for extract command with `--verbose`
3. Verify output formatting

### Phase 4: Documentation (Future)
1. Update CLI usage documentation
2. Add examples to README
3. Document extension pattern for other commands

## Files to Modify

### New Files
- `kg_forge/utils/verbose.py` - VerboseLogger utility class
- `tests/test_utils/test_verbose.py` - Tests for verbose logger

### Modified Files
- `kg_forge/cli/main.py` - Add `--verbose` global flag
- `kg_forge/cli/extract.py` - Pass verbose to extractors
- `kg_forge/config/settings.py` - Add verbose config option
- `kg_forge/extractors/llm_base.py` - Add verbose logging
- `kg_forge/extractors/openrouter.py` - Integrate verbose logger
- `kg_forge/extractors/bedrock.py` - Integrate verbose logger

## Future Extensions

Commands that could benefit from verbose mode:

- **pipeline run**: Show each hook execution, entity processing steps
- **ingest**: Display document parsing, Neo4j transactions
- **parse**: Show HTML parsing details, section extraction
- **query**: Display Cypher queries being executed

## Example Usage

```bash
# Extract with verbose output
kg-forge extract --verbose entities_extract/ test_data/doc.html

# Pipeline with verbose (future)
kg-forge pipeline run --verbose --namespace test test_data/

# Combination with other flags
kg-forge extract --verbose --namespace prod --dry-run entities_extract/ docs/
```

## Success Criteria

- ✅ `--verbose` flag works with extract command
- ✅ Complete LLM prompts and responses are displayed
- ✅ Output is well-formatted and readable
- ✅ Token counts are shown when available
- ✅ VerboseLogger is reusable for other commands
- ✅ No performance impact when verbose mode is disabled
- ✅ Can be enabled via CLI, env var, or config file
- ✅ Unit tests cover VerboseLogger functionality

## Notes

- Verbose output should go to stderr or a separate stream to avoid mixing with normal command output
- Consider adding `--verbose-file` option to write verbose output to a file instead of console
- Token counting should be best-effort (not all LLM providers return token counts)
- Response time measurement should use high-precision timing
