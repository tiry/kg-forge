"""Filesystem-based ontology pack implementation."""

import yaml
import logging
from pathlib import Path
from typing import List, Optional

from .base import OntologyPack, OntologyPackInfo, StyleConfig
from kg_forge.entities.models import EntityDefinition
from kg_forge.entities.definitions import EntityDefinitionLoader

logger = logging.getLogger(__name__)


class FilesystemOntologyPack(OntologyPack):
    """Ontology pack stored in filesystem directory."""
    
    def __init__(self, pack_path: Path):
        """Initialize filesystem ontology pack."""
        super().__init__(pack_path)
        self._config: Optional[dict] = None
    
    @property
    def info(self) -> OntologyPackInfo:
        """Load pack metadata from pack.yaml."""
        if self._info is None:
            config = self._load_config()
            
            # Extract required fields with defaults
            pack_id = config.get('id')
            if not pack_id:
                # Use directory name as fallback ID
                pack_id = self.pack_path.name
            
            self._info = OntologyPackInfo(
                id=pack_id,
                name=config.get('name', pack_id.title()),
                description=config.get('description', 'No description available'),
                version=config.get('version', '1.0.0'),
                author=config.get('author'),
                homepage=config.get('homepage'),
                license=config.get('license'),
                tags=config.get('tags', [])
            )
        
        return self._info
    
    def load_entity_definitions(self) -> List[EntityDefinition]:
        """Load entity definitions from entities/ directory."""
        entities_dir = self.pack_path / "entities"
        
        if not entities_dir.exists():
            logger.warning(f"Entities directory not found in pack: {self.pack_path}")
            return []
        
        loader = EntityDefinitionLoader()
        return loader.load_entity_definitions(entities_dir)
    
    def get_style_config(self) -> Optional[StyleConfig]:
        """Load style configuration from pack config."""
        config = self._load_config()
        style_config = config.get('styles')
        
        if not style_config:
            return None
        
        return StyleConfig(
            entity_colors=style_config.get('entity_colors', {}),
            entity_shapes=style_config.get('entity_shapes', {}),
            relationship_colors=style_config.get('relationship_colors', {}),
            relationship_styles=style_config.get('relationship_styles', {})
        )
    
    def get_prompt_template(self) -> Optional[str]:
        """Load prompt template from entities/prompt_template.md."""
        template_path = self.pack_path / "entities" / "prompt_template.md"
        
        if not template_path.exists():
            return None
        
        try:
            return template_path.read_text(encoding='utf-8')
        except Exception as e:
            logger.error(f"Failed to load prompt template from {template_path}: {e}")
            return None
    
    def _load_config(self) -> dict:
        """Load pack configuration from pack.yaml."""
        if self._config is None:
            config_path = self.pack_path / "pack.yaml"
            
            if not config_path.exists():
                logger.warning(f"Pack config not found: {config_path}")
                self._config = {}
            else:
                try:
                    with config_path.open('r', encoding='utf-8') as f:
                        self._config = yaml.safe_load(f) or {}
                except Exception as e:
                    logger.error(f"Failed to load pack config {config_path}: {e}")
                    self._config = {}
        
        return self._config
    
    def validate_pack(self) -> List[str]:
        """Validate filesystem ontology pack structure."""
        issues = super().validate_pack()
        
        # Additional filesystem-specific validation
        config_path = self.pack_path / "pack.yaml"
        if config_path.exists():
            try:
                config = self._load_config()
                
                # Validate required config fields
                if not config.get('id'):
                    issues.append("Missing required 'id' field in pack.yaml")
                
                if not config.get('name'):
                    issues.append("Missing required 'name' field in pack.yaml")
                    
            except Exception as e:
                issues.append(f"Invalid pack.yaml format: {e}")
        
        return issues