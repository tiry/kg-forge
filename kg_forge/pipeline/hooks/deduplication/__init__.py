"""Entity deduplication hooks."""

from kg_forge.pipeline.hooks.deduplication.fuzzy import (
    fuzzy_deduplicate_entities,
)

__all__ = [
    'fuzzy_deduplicate_entities',
]
