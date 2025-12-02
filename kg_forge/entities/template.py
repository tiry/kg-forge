"""Prompt template builder for entity extraction."""

import logging
from pathlib import Path
from typing import Optional

from kg_forge.entities.models import EntityDefinitions

logger = logging.getLogger(__name__)


class PromptTemplateBuilder:
    """Build prompts from template and entity definitions."""
    
    # Template placeholder for entity definitions
    ENTITY_DEFINITIONS_PLACEHOLDER = "{{ENTITY_TYPE_DEFINITIONS}}"
    TEXT_PLACEHOLDER = "{{TEXT}}"
    
    def merge_definitions(
        self,
        template_path: Path,
        definitions: EntityDefinitions
    ) -> str:
        """
        Merge entity definitions into template.
        
        Replaces {{ENTITY_TYPE_DEFINITIONS}} with concatenated markdown
        of all entity definitions.
        
        Args:
            template_path: Path to prompt template file
            definitions: Entity definitions to merge
            
        Returns:
            Template with entity definitions merged
            
        Raises:
            FileNotFoundError: If template file doesn't exist
        """
        if not template_path.exists():
            raise FileNotFoundError(f"Template file not found: {template_path}")
        
        # Read template
        template = template_path.read_text(encoding='utf-8')
        
        # Get concatenated entity definitions markdown
        entity_markdown = definitions.get_all_markdown()
        
        # Replace placeholder
        merged = template.replace(self.ENTITY_DEFINITIONS_PLACEHOLDER, entity_markdown)
        
        logger.debug(f"Merged {definitions.count()} entity definitions into template")
        return merged
    
    def prepare_extraction_prompt(
        self,
        template_path: Path,
        definitions: EntityDefinitions,
        text: str
    ) -> str:
        """
        Prepare complete prompt for entity extraction.
        
        Merges entity definitions and input text into template.
        Replaces both {{ENTITY_TYPE_DEFINITIONS}} and {{TEXT}}.
        
        Args:
            template_path: Path to prompt template file
            definitions: Entity definitions to merge
            text: Input text to analyze
            
        Returns:
            Complete prompt ready for LLM
            
        Raises:
            FileNotFoundError: If template file doesn't exist
        """
        # First merge entity definitions
        prompt = self.merge_definitions(template_path, definitions)
        
        # Then replace text placeholder
        prompt = prompt.replace(self.TEXT_PLACEHOLDER, text)
        
        logger.debug(f"Prepared extraction prompt ({len(prompt)} chars)")
        return prompt
    
    def get_default_template_path(self, entities_dir: Optional[Path] = None) -> Path:
        """
        Get default path to prompt template.
        
        Args:
            entities_dir: Optional path to entities directory.
                         If not provided, uses default location.
        
        Returns:
            Path to prompt_template.md
        """
        if entities_dir is None:
            # Use default location relative to project root
            project_root = Path(__file__).parent.parent.parent
            entities_dir = project_root / "entities_extract"
        
        return Path(entities_dir) / "prompt_template.md"
