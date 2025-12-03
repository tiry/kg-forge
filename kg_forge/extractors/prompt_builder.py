"""
Build extraction prompts from entity definitions and templates.
"""

import logging
from pathlib import Path
from typing import Optional, List

from kg_forge.entities.loader import EntityDefinitionsLoader

logger = logging.getLogger(__name__)


class PromptBuilder:
    """Build extraction prompts by merging entity definitions with templates.
    
    Loads entity definitions from markdown files and merges them with
    a prompt template to create complete extraction prompts.
    """
    
    def __init__(
        self,
        entities_dir: Path = Path("entities_extract"),
        template_file: str = "prompt_template.md"
    ):
        """Initialize prompt builder.
        
        Args:
            entities_dir: Directory containing entity definition markdown files
            template_file: Name of the template file in entities_dir
        """
        self.entities_dir = Path(entities_dir)
        self.template_path = self.entities_dir / template_file
        self.loader = EntityDefinitionsLoader(self.entities_dir)
        
        # Load template
        if not self.template_path.exists():
            raise FileNotFoundError(f"Template not found: {self.template_path}")
        
        with open(self.template_path, 'r', encoding='utf-8') as f:
            self.template = f.read()
        
        logger.info(f"Loaded prompt template from {self.template_path}")
    
    def build_extraction_prompt(
        self,
        content: str,
        entity_types: Optional[List[str]] = None,
        max_content_length: int = 100000
    ) -> str:
        """Build complete extraction prompt for given content.
        
        Args:
            content: Document text to extract entities from
            entity_types: Specific entity types to extract, or None for all
            max_content_length: Maximum content length (truncate if exceeded)
            
        Returns:
            Complete prompt with instructions, entity definitions, and content
        """
        # Load entity definitions
        all_defs_obj = self.loader.load_all()
        all_definitions = all_defs_obj.definitions
        
        # Filter by types if specified (case-insensitive)
        if entity_types:
            # Normalize requested types to lowercase for matching
            entity_types_lower = [t.lower() for t in entity_types]
            definitions = {
                k: v for k, v in all_definitions.items()
                if k.lower() in entity_types_lower
            }
            if not definitions:
                logger.warning(
                    f"No definitions found for types: {entity_types}. "
                    f"Available types: {list(all_definitions.keys())}"
                )
                definitions = all_definitions
        else:
            definitions = all_definitions
        
        logger.info(f"Building prompt with {len(definitions)} entity types")
        
        # Build entity type definitions text
        entity_defs_text = self._build_entity_definitions(definitions)
        
        # Truncate content if too long
        if len(content) > max_content_length:
            logger.warning(
                f"Content length {len(content)} exceeds max {max_content_length}, truncating"
            )
            content = content[:max_content_length] + "\n\n[... content truncated ...]"
        
        # Replace placeholders in template
        prompt = self.template.replace("{{ENTITY_TYPE_DEFINITIONS}}", entity_defs_text)
        prompt = prompt.replace("{{TEXT}}", content)
        
        return prompt
    
    def _build_entity_definitions(self, definitions: dict) -> str:
        """Build entity definitions text from loaded definitions.
        
        Args:
            definitions: Dictionary of EntityDefinition objects
            
        Returns:
            Formatted entity definitions text
        """
        lines = []
        
        for entity_id, definition in definitions.items():
            # Use EntityDefinition attributes, not dictionary access
            name = definition.name if definition.name else entity_id
            lines.append(f"## {name}")
            lines.append(f"**ID**: `{entity_id}`")
            lines.append("")
            
            if definition.description:
                lines.append(f"**Description**: {definition.description}")
                lines.append("")
            
            if definition.relations:
                lines.append("**Relations**:")
                for relation in definition.relations:
                    lines.append(
                        f"- {relation.target_entity_type}: "
                        f"{relation.forward_label} / {relation.reverse_label}"
                    )
                lines.append("")
            
            if definition.examples:
                lines.append("**Examples**:")
                for example in definition.examples:
                    lines.append(f"- **{example.name}**: {example.description}")
                lines.append("")
            
            lines.append("---")
            lines.append("")
        
        return "\n".join(lines)
    
    def get_loaded_types(self) -> List[str]:
        """Get list of all loaded entity types.
        
        Returns:
            List of entity type IDs
        """
        defs_obj = self.loader.load_all()
        return list(defs_obj.definitions.keys())
