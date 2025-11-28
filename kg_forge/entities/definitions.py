"""Entity definition loading and parsing logic."""

import re
import logging
from pathlib import Path
from typing import List, Dict, Optional

from .models import EntityDefinition, RelationDefinition, ExampleDefinition

logger = logging.getLogger(__name__)


class EntityDefinitionLoader:
    """Loads and parses entity definitions from markdown files."""
    
    def __init__(self):
        self.loaded_definitions: Dict[str, EntityDefinition] = {}
    
    def load_entity_definitions(self, entities_dir: Path) -> List[EntityDefinition]:
        """
        Load all entity definitions from directory.
        
        Args:
            entities_dir: Directory containing *.md files
            
        Returns:
            List of parsed EntityDefinition objects
            
        Raises:
            FileNotFoundError: If entities_dir doesn't exist
        """
        if not entities_dir.exists():
            raise FileNotFoundError(f"Entity definitions directory not found: {entities_dir}")
            
        if not entities_dir.is_dir():
            raise FileNotFoundError(f"Path is not a directory: {entities_dir}")
        
        logger.info(f"Loading entity definitions from {entities_dir}")
        
        definitions = []
        md_files = sorted(entities_dir.glob("*.md"))
        
        # Exclude prompt_template.md from entity definitions
        entity_files = [f for f in md_files if f.name != "prompt_template.md"]
        
        logger.debug(f"Found {len(entity_files)} entity definition files")
        
        for file_path in entity_files:
            try:
                definition = self.load_single_definition(file_path)
                
                # Check for duplicate IDs
                if definition.id in self.loaded_definitions:
                    existing_file = self.loaded_definitions[definition.id].source_file
                    logger.warning(
                        f"Duplicate entity ID '{definition.id}' in {file_path.name} and {existing_file}, "
                        f"using {file_path.name}"
                    )
                
                self.loaded_definitions[definition.id] = definition
                definitions.append(definition)
                
            except Exception as e:
                logger.error(f"Failed to parse {file_path.name}: {e}")
                continue
        
        logger.info(f"Loaded {len(definitions)} entity definitions from {entities_dir}")
        return definitions
    
    def load_single_definition(self, file_path: Path) -> EntityDefinition:
        """Load and parse single entity definition file."""
        logger.debug(f"Parsing entity definition: {file_path.name}")
        
        try:
            content = file_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            # Fallback to other encodings
            content = file_path.read_text(encoding='latin1')
            
        return self._parse_entity_definition(content, file_path)
    
    def _parse_entity_definition(self, content: str, file_path: Path) -> EntityDefinition:
        """Parse entity definition using line-based approach."""
        lines = content.split('\n')
        
        # Initialize with filename as default ID
        entity_id = file_path.stem
        name = None
        description_lines = []
        relations = []
        examples = []
        current_section = None
        current_example_title = None
        current_example_lines = []
        
        for line in lines:
            line_stripped = line.strip()
            
            # Parse ID section
            if line.startswith('# ID:'):
                entity_id = line[5:].strip()
                logger.debug(f"Found ID: {entity_id}")
                continue
            
            # Parse Name section  
            elif line.startswith('## Name:'):
                name = line[8:].strip()
                current_section = None
                logger.debug(f"Found Name: {name}")
                continue
            
            # Parse section headers
            elif line.startswith('## Description'):
                current_section = 'description'
                description_lines = []
                continue
                
            elif line.startswith('## Relations'):
                current_section = 'relations' 
                continue
                
            elif line.startswith('## Examples'):
                current_section = 'examples'
                # Save any pending example
                if current_example_title and current_example_lines:
                    examples.append(ExampleDefinition(
                        title=current_example_title,
                        description='\n'.join(current_example_lines).strip()
                    ))
                current_example_title = None
                current_example_lines = []
                continue
            
            # Parse example titles (### headings)
            elif line.startswith('### ') and current_section == 'examples':
                # Save previous example
                if current_example_title and current_example_lines:
                    examples.append(ExampleDefinition(
                        title=current_example_title,
                        description='\n'.join(current_example_lines).strip()
                    ))
                
                current_example_title = line[4:].strip()
                current_example_lines = []
                continue
            
            # Parse content based on current section
            if current_section == 'description':
                if line_stripped:  # Skip empty lines at start
                    description_lines.append(line)
                elif description_lines:  # Keep empty lines within content
                    description_lines.append(line)
                    
            elif current_section == 'relations':
                if line_stripped and line_stripped.startswith('-'):
                    relation = RelationDefinition.parse(line_stripped)
                    if relation:
                        relations.append(relation)
                        
            elif current_section == 'examples':
                if current_example_title:
                    current_example_lines.append(line)
        
        # Save final example if exists
        if current_example_title and current_example_lines:
            examples.append(ExampleDefinition(
                title=current_example_title,
                description='\n'.join(current_example_lines).strip()
            ))
        
        # Build description from collected lines
        description = None
        if description_lines:
            description = '\n'.join(description_lines).strip()
            if not description:  # Only whitespace
                description = None
        
        # Log missing optional sections
        if not name:
            logger.debug(f"Missing Name section in {file_path.name}")
        if not description:
            logger.debug(f"Missing Description section in {file_path.name}")
        if not relations:
            logger.debug(f"Missing Relations section in {file_path.name}")
        if not examples:
            logger.debug(f"Missing Examples section in {file_path.name}")
        
        return EntityDefinition(
            id=entity_id,
            name=name,
            description=description,
            relations=relations,
            examples=examples,
            source_file=file_path.name,
            raw_markdown=content
        )
    
    def load_prompt_template(self, template_path: Path) -> str:
        """Load prompt template markdown content."""
        if not template_path.exists():
            raise FileNotFoundError(f"Prompt template not found: {template_path}")
            
        logger.debug(f"Loading prompt template: {template_path}")
        
        try:
            content = template_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            content = template_path.read_text(encoding='latin1')
            
        return content
    
    def build_merged_prompt(self, template: str, definitions: List[EntityDefinition]) -> str:
        """
        Replace {{ENTITY_TYPE_DEFINITIONS}} placeholder with concatenated definitions.
        
        Args:
            template: Prompt template with placeholder
            definitions: Parsed entity definitions
            
        Returns:
            Complete prompt with entity definitions merged
        """
        if not definitions:
            logger.warning("No entity definitions provided for prompt merging")
            return template.replace('{{ENTITY_TYPE_DEFINITIONS}}', '')
        
        # Sort definitions by ID for consistent ordering
        sorted_definitions = sorted(definitions, key=lambda d: d.id)
        
        # Concatenate raw markdown with separators
        concatenated_content = []
        for definition in sorted_definitions:
            if definition.raw_markdown:
                concatenated_content.append(definition.raw_markdown.strip())
        
        entity_definitions_text = '\n\n---\n\n'.join(concatenated_content)
        
        # Replace placeholder
        merged_prompt = template.replace('{{ENTITY_TYPE_DEFINITIONS}}', entity_definitions_text)
        
        logger.debug(f"Built merged prompt with {len(sorted_definitions)} entity definitions")
        
        return merged_prompt
