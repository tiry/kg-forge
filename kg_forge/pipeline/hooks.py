"""
Hook system for pipeline extensibility.

Provides:
- InteractiveSession for human-in-the-loop interactions
- HookRegistry for managing before_store and after_batch hooks
- Type definitions for hook functions
"""

import logging
from typing import List, Callable, Optional

logger = logging.getLogger(__name__)

# Forward references for type hints
try:
    from kg_forge.models.extraction import ExtractedEntity
    from kg_forge.models.document import Document
    from kg_forge.graph.base import GraphClient
except ImportError:
    # Handle circular imports during initial load
    ExtractedEntity = 'ExtractedEntity'
    Document = 'Document'
    GraphClient = 'GraphClient'


# Hook type definitions
ProcessBeforeStoreHook = Callable[
    ['Document', List['ExtractedEntity'], 'GraphClient'],
    List['ExtractedEntity']
]

ProcessAfterBatchHook = Callable[
    [List['ExtractedEntity'], 'GraphClient', Optional['InteractiveSession']],
    None
]


class InteractiveSession:
    """
    Interactive session for human-in-the-loop processing.
    
    Provides methods to prompt the user for decisions during pipeline execution.
    When disabled (interactive=False), returns default values without prompting.
    """
    
    def __init__(self, enabled: bool = False):
        """
        Initialize interactive session.
        
        Args:
            enabled: Whether interactive mode is enabled
        """
        self.enabled = enabled
        logger.debug(f"InteractiveSession initialized: enabled={enabled}")
    
    def confirm(self, message: str, default: bool = True) -> bool:
        """
        Ask user for yes/no confirmation.
        
        Args:
            message: Question to ask user
            default: Default answer if user just hits enter or if not interactive
            
        Returns:
            True if user confirms, False otherwise
        """
        if not self.enabled:
            return default
        
        import click
        return click.confirm(message, default=default)
    
    def prompt(self, message: str, default: Optional[str] = None) -> str:
        """
        Prompt user for text input.
        
        Args:
            message: Prompt message
            default: Default value if user just hits enter or if not interactive
            
        Returns:
            User's input or default value
        """
        if not self.enabled:
            return default or ""
        
        import click
        return click.prompt(message, default=default or "")
    
    def choose(
        self,
        message: str,
        choices: List[str],
        default: Optional[str] = None
    ) -> str:
        """
        Prompt user to choose from a list of options.
        
        Args:
            message: Prompt message
            choices: List of options to choose from
            default: Default choice if user just hits enter or if not interactive
            
        Returns:
            Selected choice
        """
        if not self.enabled:
            return default or choices[0]
        
        import click
        return click.prompt(
            message,
            type=click.Choice(choices),
            default=default or choices[0]
        )


class HookRegistry:
    """
    Registry for pipeline hooks.
    
    Manages two types of hooks:
    - before_store: Called before storing entities to graph (can modify entities)
    - after_batch: Called after processing a batch of documents (cleanup/merge operations)
    """
    
    def __init__(self):
        """Initialize empty hook registries."""
        self.before_store_hooks: List[ProcessBeforeStoreHook] = []
        self.after_batch_hooks: List[ProcessAfterBatchHook] = []
        logger.debug("HookRegistry initialized")
    
    def register_before_store(self, hook: ProcessBeforeStoreHook):
        """
        Register a before-store hook.
        
        Args:
            hook: Function to call before storing entities
        """
        self.before_store_hooks.append(hook)
        logger.info(f"Registered before_store hook: {hook.__name__}")
    
    def register_after_batch(self, hook: ProcessAfterBatchHook):
        """
        Register an after-batch hook.
        
        Args:
            hook: Function to call after processing a batch
        """
        self.after_batch_hooks.append(hook)
        logger.info(f"Registered after_batch hook: {hook.__name__}")
    
    def run_before_store(
        self,
        doc: 'Document',
        entities: List['ExtractedEntity'],
        graph_client: 'GraphClient'
    ) -> List['ExtractedEntity']:
        """
        Run all before-store hooks in sequence.
        
        Each hook receives the output of the previous hook, allowing
        for a chain of transformations.
        
        Args:
            doc: The document being processed
            entities: Extracted entities
            graph_client: Neo4j client for queries/updates
            
        Returns:
            Modified list of entities after all hooks have run
        """
        result = entities
        
        
        for hook in self.before_store_hooks:
            try:
                logger.debug(f"Running before_store hook: {hook.__name__}")
                result = hook(doc, result, graph_client)
            except Exception as e:
                logger.error(f"Error in before_store hook {hook.__name__}: {e}")
                # Continue with other hooks despite error
        
        return result
    
    def run_after_batch(
        self,
        entities: List['ExtractedEntity'],
        graph_client: 'GraphClient',
        interactive: Optional[InteractiveSession] = None
    ):
        """
        Run all after-batch hooks in sequence.
        
        Args:
            entities: All entities added in this batch
            graph_client: Neo4j client for queries/updates
            interactive: Interactive session for user prompts (None if not interactive)
        """
        for hook in self.after_batch_hooks:
            try:
                logger.debug(f"Running after_batch hook: {hook.__name__}")
                hook(entities, graph_client, interactive)
            except Exception as e:
                logger.error(f"Error in after_batch hook {hook.__name__}: {e}")
                # Continue with other hooks despite error


# Global registry instance
_hook_registry = HookRegistry()


def get_hook_registry() -> HookRegistry:
    """
    Get the global hook registry instance.
    
    Returns:
        The singleton HookRegistry instance
    """
    return _hook_registry
