"""Vector storage module for entity embeddings."""

from kg_forge.vector.base import VectorStore
from kg_forge.vector.chroma import ChromaVectorStore

__all__ = ['VectorStore', 'ChromaVectorStore']
