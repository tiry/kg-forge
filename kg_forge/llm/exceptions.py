"""
Custom exceptions for LLM operations.
"""

class LLMError(Exception):
    """Base exception for LLM-related errors."""
    pass

class ParseError(LLMError):
    """Error parsing LLM response."""
    pass

class ValidationError(LLMError):
    """Error validating parsed LLM response."""
    pass

class ExtractionAbortError(LLMError):
    """Error indicating extraction should be aborted due to too many failures."""
    pass