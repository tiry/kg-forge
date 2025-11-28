"""Ontology-aware entity management system."""

import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

from .ontology.base import OntologyPack, get_registry
from .ontology.filesystem_pack import FilesystemOntologyPack
from .entities.models import EntityDefinition
from .entities.definitions import EntityDefinitionLoader

logger = logging.getLogger(__name__)


class OntologyManager:
    """Manages ontology packs and provides unified entity access."""
    
    def __init__(self, ontology_packs_dir: Optional[Path] = None):
        """
        Initialize ontology manager.
        
        Args:
            ontology_packs_dir: Directory containing ontology packs. If None, uses default location.
        """
        self.registry = get_registry()
        self._current_pack: Optional[OntologyPack] = None
        
        if ontology_packs_dir is None:
            # Default to ontology_packs in project root
            ontology_packs_dir = Path(__file__).parent.parent / "ontology_packs"
        
        self.ontology_packs_dir = ontology_packs_dir
        self._auto_discover_packs()
    
    def _auto_discover_packs(self) -> None:
        """Automatically discover and register ontology packs."""
        if self.ontology_packs_dir.exists():
            discovered = self.registry.discover_packs(self.ontology_packs_dir)
            if discovered:
                logger.info(f"Auto-discovered {len(discovered)} ontology packs")
                for pack in discovered:
                    logger.debug(f"  - {pack.info.id}: {pack.info.name}")
    
    def list_available_ontologies(self) -> List[Dict[str, Any]]:
        """
        List all available ontology packs.
        
        Returns:
            List of ontology pack information dictionaries
        """
        packs = self.registry.list_packs()
        return [
            {
                "id": pack.id,
                "name": pack.name,
                "description": pack.description,
                "version": pack.version,
                "author": pack.author,
                "tags": pack.tags
            }
            for pack in packs
        ]
    
    def set_active_ontology(self, ontology_id: str) -> None:
        """
        Set the active ontology pack.
        
        Args:
            ontology_id: ID of the ontology pack to activate
            
        Raises:
            ValueError: If ontology_id is not found
        """
        try:
            pack = self.registry.get_pack(ontology_id)
            self._current_pack = pack
            logger.info(f"Activated ontology pack: {ontology_id}")
        except ValueError as e:
            logger.error(f"Failed to activate ontology '{ontology_id}': {e}")
            raise
    
    def get_active_ontology(self) -> Optional[OntologyPack]:
        """Get the currently active ontology pack."""
        if self._current_pack is None:
            # Try to get default pack
            default_pack = self.registry.get_default_pack()
            if default_pack:
                self._current_pack = default_pack
                logger.info(f"Using default ontology pack: {default_pack.info.id}")
        
        return self._current_pack
    
    def get_entity_definitions(self, ontology_id: Optional[str] = None) -> List[EntityDefinition]:
        """
        Get entity definitions from specified or active ontology.
        
        Args:
            ontology_id: Optional specific ontology ID. If None, uses active ontology.
            
        Returns:
            List of entity definitions
            
        Raises:
            ValueError: If no ontology is available or specified ontology not found
        """
        if ontology_id:
            pack = self.registry.get_pack(ontology_id)
        else:
            pack = self.get_active_ontology()
            if not pack:
                raise ValueError("No active ontology pack available")
        
        return pack.get_entity_definitions()
    
    def get_prompt_template(self, ontology_id: Optional[str] = None) -> Optional[str]:
        """
        Get LLM prompt template from specified or active ontology.
        
        Args:
            ontology_id: Optional specific ontology ID. If None, uses active ontology.
            
        Returns:
            Prompt template string or None if not found
        """
        if ontology_id:
            pack = self.registry.get_pack(ontology_id)
        else:
            pack = self.get_active_ontology()
            if not pack:
                return None
        
        return pack.get_prompt_template()
    
    def build_extraction_prompt(self, ontology_id: Optional[str] = None) -> str:
        """
        Build complete LLM extraction prompt with entity definitions.
        
        Args:
            ontology_id: Optional specific ontology ID. If None, uses active ontology.
            
        Returns:
            Complete prompt ready for LLM extraction
            
        Raises:
            ValueError: If no ontology is available or no template found
        """
        definitions = self.get_entity_definitions(ontology_id)
        template = self.get_prompt_template(ontology_id)
        
        if not template:
            raise ValueError("No prompt template found in active ontology pack")
        
        # Use legacy entity definition loader for prompt building
        loader = EntityDefinitionLoader()
        return loader.build_merged_prompt(template, definitions)
    
    def get_style_config(self, ontology_id: Optional[str] = None):
        """
        Get visualization style configuration from specified or active ontology.
        
        Args:
            ontology_id: Optional specific ontology ID. If None, uses active ontology.
            
        Returns:
            StyleConfig object or None if not available
        """
        if ontology_id:
            pack = self.registry.get_pack(ontology_id)
        else:
            pack = self.get_active_ontology()
            if not pack:
                return None
        
        return pack.get_style_config()
    
    def register_ontology_pack(self, pack_path: Path) -> OntologyPack:
        """
        Register a new ontology pack from filesystem path.
        
        Args:
            pack_path: Path to ontology pack directory
            
        Returns:
            Registered ontology pack
            
        Raises:
            ValueError: If pack is invalid or registration fails
        """
        pack = FilesystemOntologyPack(pack_path)
        
        # Validate pack before registration
        issues = pack.validate_pack()
        if issues:
            raise ValueError(f"Invalid ontology pack: {', '.join(issues)}")
        
        self.registry.register_pack(pack)
        logger.info(f"Registered ontology pack: {pack.info.id}")
        
        return pack
    
    def create_legacy_fallback(self, entities_dir: Path) -> List[EntityDefinition]:
        """
        Fallback method for loading entities from legacy entities_extract directory.
        
        Args:
            entities_dir: Directory containing entity definition files
            
        Returns:
            List of entity definitions
            
        Note:
            This is for backward compatibility only. Use ontology packs for new implementations.
        """
        logger.warning(
            f"Using legacy entity loading from {entities_dir}. "
            "Consider migrating to ontology packs."
        )
        
        loader = EntityDefinitionLoader()
        return loader.load_entity_definitions(entities_dir)


# Global ontology manager instance
_global_manager: Optional[OntologyManager] = None


def get_ontology_manager() -> OntologyManager:
    """Get the global ontology manager instance."""
    global _global_manager
    if _global_manager is None:
        _global_manager = OntologyManager()
    return _global_manager


def set_ontology_manager(manager: OntologyManager) -> None:
    """Set a custom ontology manager (for testing)."""
    global _global_manager
    _global_manager = manager