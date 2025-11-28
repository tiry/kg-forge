"""
LLM prompt builder for entity extraction.
"""

from pathlib import Path
from typing import List
from kg_forge.entities.definitions import EntityDefinitionLoader


class PromptBuilder:
    """Builds prompts for entity extraction from document content and entity definitions."""
    
    def __init__(self, entity_loader: EntityDefinitionLoader):
        self.entity_loader = entity_loader
    
    def build_prompt(self, document_content: str, entities_dir: Path, 
                    template_file: Path) -> str:
        """
        Build extraction prompt from document content and entity definitions.
        
        Args:
            document_content: Curated text from Step 2 document model
            entities_dir: Directory containing entity definition files
            template_file: Prompt template file
            
        Returns:
            Complete prompt string ready for LLM
        """
        # Load and merge entity definitions from Step 3
        definitions = self.entity_loader.load_entity_definitions(entities_dir)
        template_content = self.entity_loader.load_prompt_template(template_file)
        merged_prompt = self.entity_loader.build_merged_prompt(template_content, definitions)
        
        # Inject document content into the template
        # Replace placeholder with actual document content
        final_prompt = merged_prompt.replace('{{DOCUMENT_CONTENT}}', document_content)
        
        return final_prompt
    
    def build_prompt_with_definitions(
        self, 
        document_content: str, 
        entity_definitions: List, 
        template_file: Path
    ) -> str:
        """
        Build complete prompt with pre-loaded entity definitions.
        
        This is more efficient than build_prompt() when processing multiple documents
        as it avoids reloading entity definitions for each document.
        
        Args:
            document_content: The content to inject into template
            entity_definitions: Pre-loaded entity definitions
            template_file: Path to prompt template file
            
        Returns:
            Complete prompt string ready for LLM
        """
        # Load template and merge with cached definitions
        template_content = self.entity_loader.load_prompt_template(template_file)
        merged_prompt = self.entity_loader.build_merged_prompt(template_content, entity_definitions)
        
        # Inject document content into the template
        final_prompt = merged_prompt.replace('{{DOCUMENT_CONTENT}}', document_content)
        
        return final_prompt