"""
Entity extraction from documents using LLMs.

This package provides an abstraction for entity extraction with multiple backend support:
- OpenRouter: Multi-model API (easier setup)
- AWS Bedrock: AWS-hosted models

The factory automatically selects the appropriate backend based on configuration.
"""

from kg_forge.extractors.base import EntityExtractor
from kg_forge.extractors.factory import create_extractor

__all__ = ["EntityExtractor", "create_extractor"]
