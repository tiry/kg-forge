"""Entity deduplication hooks."""

from kg_forge.pipeline.hooks.deduplication.fuzzy import (
    fuzzy_deduplicate_entities,
)
from kg_forge.pipeline.hooks.deduplication.vector import (
    vector_deduplicate_entities,
)

__all__ = [
    'fuzzy_deduplicate_entities',
    'vector_deduplicate_entities',
]
