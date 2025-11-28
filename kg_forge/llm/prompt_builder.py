"""
LLM prompt builder for entity extraction.
"""

from pathlib import Path
from typing import List, Optional
from kg_forge.entities.definitions import EntityDefinitionLoader
from kg_forge.ontology_manager import get_ontology_manager


class PromptBuilder:
    """Builds prompts for entity extraction from document content and entity definitions."""
    
    def __init__(self, entity_loader: Optional[EntityDefinitionLoader] = None, ontology_id: Optional[str] = None):
        """
        Initialize prompt builder.
        
        Args:
            entity_loader: Legacy entity loader (for backward compatibility)
            ontology_id: ID of ontology pack to use for prompts
        """
        self.entity_loader = entity_loader
        self.ontology_id = ontology_id
        self.ontology_manager = get_ontology_manager()
    
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
    
    def build_ontology_prompt(self, document_content: str, ontology_id: Optional[str] = None) -> str:
        """
        Build extraction prompt using ontology pack.
        
        Args:
            document_content: Document content to analyze
            ontology_id: Specific ontology pack ID, or use configured default
            
        Returns:
            Complete prompt string ready for LLM
        """
        target_ontology = ontology_id or self.ontology_id
        
        # Build prompt using ontology manager
        merged_prompt = self.ontology_manager.build_extraction_prompt(target_ontology)
        
        # Inject document content
        final_prompt = merged_prompt.replace('{{DOCUMENT_CONTENT}}', document_content)
        
        return final_prompt