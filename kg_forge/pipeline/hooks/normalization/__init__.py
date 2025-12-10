"""Entity normalization hooks."""

from kg_forge.pipeline.hooks.normalization.basic import (
    basic_normalize_entities,
    normalize_text,
)
from kg_forge.pipeline.hooks.normalization.dictionary import (
    dictionary_normalize_entities,
    DictionaryNormalizer,
)

__all__ = [
    'basic_normalize_entities',
    'normalize_text',
    'dictionary_normalize_entities',
    'DictionaryNormalizer',
]
