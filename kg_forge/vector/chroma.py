"""ChromaDB implementation of vector store."""

import logging
from typing import List, Dict, Any, Optional, Tuple
import chromadb
from chromadb.config import Settings as ChromaSettings

from kg_forge.vector.base import VectorStore

logger = logging.getLogger(__name__)


class ChromaVectorStore(VectorStore):
    """ChromaDB-based vector storage for entity embeddings."""
    
    def __init__(self, persist_directory: str = "./data/chroma_db"):
        """
        Initialize ChromaDB client.
        
        Args:
            persist_directory: Directory for ChromaDB persistence
        """
        self.persist_directory = persist_directory
        
        # Initialize ChromaDB with persistence
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        logger.info(f"Initialized ChromaDB at: {persist_directory}")
        self._collections = {}
    
    def _get_collection(self, namespace: str):
        """Get or create collection for namespace."""
        if namespace not in self._collections:
            # Collection name: namespace-based
            collection_name = f"entities_{namespace}"
            
            # Get or create collection
            try:
                collection = self.client.get_collection(collection_name)
                logger.debug(f"Retrieved existing ChromaDB collection: {collection_name}")
            except Exception:
                collection = self.client.create_collection(
                    name=collection_name,
                    metadata={"namespace": namespace}
                )
                logger.info(f"Created new ChromaDB collection: {collection_name}")
            
            self._collections[namespace] = collection
        
        return self._collections[namespace]
    
    def add_entity(
        self,
        entity_id: str,
        entity_type: str,
        entity_name: str,
        embedding: List[float],
        namespace: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add entity embedding to ChromaDB."""
        collection = self._get_collection(namespace)
        
        # Prepare metadata
        meta = {
            "entity_type": entity_type,
            "entity_name": entity_name,
            "namespace": namespace
        }
        if metadata:
            meta.update(metadata)
        
        # Add to collection
        collection.add(
            ids=[entity_id],
            embeddings=[embedding],
            metadatas=[meta]
        )
        
        logger.debug(f"Added embedding for entity: {entity_name} ({entity_type})")
    
    def search_similar(
        self,
        entity_type: str,
        embedding: List[float],
        namespace: str,
        limit: int = 5,
        threshold: float = 0.85
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        """Search for similar entities in ChromaDB."""
        collection = self._get_collection(namespace)
        
        # Query with entity_type filter
        results = collection.query(
            query_embeddings=[embedding],
            n_results=limit,
            where={"entity_type": entity_type}
        )
        
        # Process results
        similar_entities = []
        
        if results['ids'] and results['ids'][0]:
            for i, entity_id in enumerate(results['ids'][0]):
                # ChromaDB returns L2 distance, convert to cosine similarity
                # similarity = 1 - (distance / 2) for normalized vectors
                distance = results['distances'][0][i]
                score = 1 - (distance / 2)  # Approximate cosine similarity
                
                # Filter by threshold
                if score >= threshold:
                    metadata = results['metadatas'][0][i]
                    similar_entities.append((entity_id, score, metadata))
        
        return similar_entities
    
    def delete_namespace(self, namespace: str) -> int:
        """Delete ChromaDB collection for namespace."""
        collection_name = f"entities_{namespace}"
        
        try:
            collection = self.client.get_collection(collection_name)
            count = collection.count()
            self.client.delete_collection(collection_name)
            
            # Remove from cache
            if namespace in self._collections:
                del self._collections[namespace]
            
            logger.info(f"Deleted ChromaDB collection: {collection_name} ({count} entities)")
            return count
            
        except Exception as e:
            logger.warning(f"Could not delete collection {collection_name}: {e}")
            return 0
    
    def get_stats(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """Get ChromaDB statistics."""
        if namespace:
            try:
                collection = self._get_collection(namespace)
                count = collection.count()
                return {
                    "namespace": namespace,
                    "entity_count": count,
                    "collection_name": f"entities_{namespace}"
                }
            except Exception as e:
                return {"error": str(e)}
        else:
            # Global stats
            collections = self.client.list_collections()
            return {
                "total_collections": len(collections),
                "collections": [c.name for c in collections]
            }
