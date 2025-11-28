"""
Hook registry and management system for extending ingest pipeline behavior.
"""

import logging
from typing import Callable, Dict, List, Any, Optional

from kg_forge.models.document import ParsedDocument
from kg_forge.graph.neo4j_client import Neo4jClient


logger = logging.getLogger(__name__)


# Type definitions for hook functions
BeforeStoreHook = Callable[[ParsedDocument, Dict[str, Any], Neo4jClient], Dict[str, Any]]
AfterBatchHook = Callable[[List['EntityRecord'], Neo4jClient, Optional['InteractiveSession']], None]


class EntityRecord:
    """Represents an entity that was processed during ingest."""
    
    def __init__(self, entity_type: str, name: str, confidence: float, 
                 doc_id: str, namespace: str):
        self.entity_type = entity_type
        self.name = name
        self.confidence = confidence
        self.doc_id = doc_id
        self.namespace = namespace
        self.created_at = None  # Will be set by pipeline
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'entity_type': self.entity_type,
            'name': self.name,
            'confidence': self.confidence,
            'doc_id': self.doc_id,
            'namespace': self.namespace,
            'created_at': self.created_at
        }


class HookRegistry:
    """
    Registry for managing ingest pipeline hooks.
    
    Hooks allow custom behavior to be injected at specific points:
    - process_before_store: Modify extraction metadata before Neo4j storage
    - process_after_batch: Process all entities after batch completion
    """
    
    def __init__(self):
        self._before_store_hooks: List[BeforeStoreHook] = []
        self._after_batch_hooks: List[AfterBatchHook] = []
    
    def register_before_store(self, func: BeforeStoreHook) -> None:
        """
        Register a process_before_store hook.
        
        Args:
            func: Hook function with signature:
                  (content: ParsedDocument, metadata: dict, kg_client: Neo4jClient) -> dict
        """
        if not callable(func):
            raise ValueError("Hook must be callable")
            
        self._before_store_hooks.append(func)
        logger.debug(f"Registered before_store hook: {func.__name__}")
    
    def register_after_batch(self, func: AfterBatchHook) -> None:
        """
        Register a process_after_batch hook.
        
        Args:
            func: Hook function with signature:
                  (entities: List[EntityRecord], kg_client: Neo4jClient, 
                   interactive: InteractiveSession | None) -> None
        """
        if not callable(func):
            raise ValueError("Hook must be callable")
            
        self._after_batch_hooks.append(func)
        logger.debug(f"Registered after_batch hook: {func.__name__}")
    
    def execute_before_store(self, content: ParsedDocument, metadata: Dict[str, Any], 
                           kg_client: Neo4jClient) -> Dict[str, Any]:
        """
        Execute all registered before_store hooks.
        
        Args:
            content: Original curated document
            metadata: Extraction metadata from LLM
            kg_client: Neo4j client instance
            
        Returns:
            Modified metadata dictionary (chain of transformations)
            
        Notes:
            - Hooks are executed in registration order
            - Each hook receives the output of the previous hook
            - Hook exceptions are logged as warnings and do not abort pipeline
        """
        current_metadata = metadata.copy()
        
        for hook in self._before_store_hooks:
            try:
                result = hook(content, current_metadata, kg_client)
                if isinstance(result, dict):
                    current_metadata = result
                else:
                    logger.warning(f"Hook {hook.__name__} returned non-dict result, ignoring")
                    
            except Exception as e:
                logger.warning(f"Hook {hook.__name__} failed: {e}", exc_info=True)
                # Continue with current metadata
        
        return current_metadata
    
    def execute_after_batch(self, entities: List[EntityRecord], kg_client: Neo4jClient,
                          interactive: Optional['InteractiveSession'] = None) -> None:
        """
        Execute all registered after_batch hooks.
        
        Args:
            entities: List of all entities processed in this batch
            kg_client: Neo4j client instance
            interactive: Interactive session (if enabled)
            
        Notes:
            - Hook exceptions are logged as warnings and do not abort pipeline
            - No return value expected from hooks
        """
        for hook in self._after_batch_hooks:
            try:
                hook(entities, kg_client, interactive)
                
            except Exception as e:
                logger.warning(f"Hook {hook.__name__} failed: {e}", exc_info=True)
    
    def clear_hooks(self) -> None:
        """Clear all registered hooks (primarily for testing)."""
        self._before_store_hooks.clear()
        self._after_batch_hooks.clear()
        logger.debug("Cleared all hooks")
    
    @property
    def hook_count(self) -> Dict[str, int]:
        """Get count of registered hooks by type."""
        return {
            'before_store': len(self._before_store_hooks),
            'after_batch': len(self._after_batch_hooks)
        }


# Global registry instance
_global_registry = HookRegistry()


def register_before_store(func: BeforeStoreHook) -> BeforeStoreHook:
    """
    Decorator to register a before_store hook.
    
    Example:
        @register_before_store
        def enrich_metadata(content, metadata, kg_client):
            metadata['processed_by'] = 'my_plugin'
            return metadata
    """
    _global_registry.register_before_store(func)
    return func


def register_after_batch(func: AfterBatchHook) -> AfterBatchHook:
    """
    Decorator to register an after_batch hook.
    
    Example:
        @register_after_batch
        def report_entities(entities, kg_client, interactive):
            print(f"Processed {len(entities)} entities")
    """
    _global_registry.register_after_batch(func)
    return func


def get_global_registry() -> HookRegistry:
    """Get the global hook registry instance."""
    return _global_registry


def clear_global_hooks() -> None:
    """Clear all hooks from global registry (for testing)."""
    _global_registry.clear_hooks()