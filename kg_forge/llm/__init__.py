"""
LLM Integration & Entity Extraction module for KG Forge.

This module provides LLM-based entity extraction capabilities using:
- AWS Bedrock integration via LlamaIndex
- Fake LLM implementation for testing
- Prompt building from entity definitions
- Response parsing and validation
"""

from .client import LLMExtractor, ExtractedEntity, ExtractionResult
from .exceptions import LLMError, ParseError, ValidationError, ExtractionAbortError

__all__ = [
    "LLMExtractor", 
    "ExtractedEntity", 
    "ExtractionResult",
    "LLMError",
    "ParseError", 
    "ValidationError",
    "ExtractionAbortError"
]