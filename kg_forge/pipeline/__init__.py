"""
Pipeline module for orchestrating knowledge graph construction.

This module provides the core pipeline infrastructure including:
- PipelineOrchestrator for running the complete ingestion pipeline
- Hook system for extensibility
- Default hooks (registered on demand)
"""

from kg_forge.pipeline.default_hooks import register_default_hooks
from kg_forge.pipeline.orchestrator import PipelineOrchestrator, PipelineError
from kg_forge.pipeline.hooks import get_hook_registry, InteractiveSession

# NOTE: Hooks are NOT auto-registered anymore
# Call register_default_hooks(interactive=True/False) explicitly from CLI

__all__ = [
    'PipelineOrchestrator',
    'PipelineError',
    'get_hook_registry',
    'InteractiveSession',
    'register_default_hooks',
]
