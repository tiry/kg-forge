"""Markdown parser for entity definitions."""

import re
import logging
from typing import List, Optional
from pathlib import Path

from kg_forge.entities.models import (
    EntityDefinition,
    EntityRelation,
    EntityExample,
)

logger = logging.getLogger(__name__)


class EntityMarkdownParser:
    """Parse entity definition from markdown text."""
    
    def parse(self, content: str, source_file: str) -> EntityDefinition:
        """
        Parse markdown content into EntityDefinition.
        
        Args:
            content: Markdown content to parse
            source_file: Source filename for reference
            
        Returns:
            Parsed EntityDefinition
        """
        # Extract entity_type_id (required, fallback to filename)
        fallback_id = Path(source_file).stem.lower()
        entity_type_id = self._extract_id(content, fallback_id)
        
        # Extract optional fields
        name = self._extract_name(content)
        description = self._extract_description(content)
        relations = self._extract_relations(content)
        examples = self._extract_examples(content)
        
        return EntityDefinition(
            entity_type_id=entity_type_id,
            name=name,
            description=description,
            relations=relations,
            examples=examples,
            source_file=source_file,
        )
    
    def _extract_id(self, content: str, fallback: str) -> str:
        """
        Extract ID from markdown or use fallback.
        
        Flexible parsing: handles variations in spacing and case.
        Pattern: # ID: <value> or #ID:<value> etc.
        
        Args:
            content: Markdown content
            fallback: Fallback ID (typically filename stem)
            
        Returns:
            Extracted or fallback ID (lowercased, stripped)
        """
        # Flexible pattern: optional spaces around "ID" and ":"
        pattern = r'^#\s*ID\s*:\s*(.+)$'
        
        for line in content.split('\n'):
            match = re.match(pattern, line.strip(), re.IGNORECASE)
            if match:
                extracted_id = match.group(1).strip().lower()
                logger.debug(f"Extracted ID: {extracted_id}")
                return extracted_id
        
        logger.debug(f"No ID found, using fallback: {fallback}")
        return fallback
    
    def _extract_name(self, content: str) -> Optional[str]:
        """
        Extract Name from markdown.
        
        Pattern: ## Name: <value>
        
        Args:
            content: Markdown content
            
        Returns:
            Extracted name or None
        """
        pattern = r'^##\s*Name\s*:\s*(.+)$'
        
        for line in content.split('\n'):
            match = re.match(pattern, line.strip(), re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                logger.debug(f"Extracted Name: {name}")
                return name
        
        return None
    
    def _extract_description(self, content: str) -> Optional[str]:
        """
        Extract Description from markdown.
        
        Collects all content from ## Description: until next ## heading.
        
        Args:
            content: Markdown content
            
        Returns:
            Extracted description or None
        """
        lines = content.split('\n')
        description_lines = []
        in_description = False
        
        for line in lines:
            # Check if we're starting the description section
            if re.match(r'^##\s*Description\s*:?\s*$', line.strip(), re.IGNORECASE):
                in_description = True
                continue
            
            # Check if we hit another ## heading (end of description)
            if in_description and re.match(r'^##\s+\w', line.strip()):
                break
            
            # Collect description lines
            if in_description:
                description_lines.append(line)
        
        if description_lines:
            description = '\n'.join(description_lines).strip()
            logger.debug(f"Extracted Description ({len(description)} chars)")
            return description
        
        return None
    
    def _extract_relations(self, content: str) -> List[EntityRelation]:
        """
        Extract Relations from markdown.
        
        Pattern:
        ## Relations
          - <target> : <forward> : <reverse>
          * <target> : <forward> : <reverse>
        
        Args:
            content: Markdown content
            
        Returns:
            List of EntityRelation objects
        """
        relations = []
        lines = content.split('\n')
        in_relations = False
        
        for line in lines:
            # Check if we're in the relations section
            if re.match(r'^##\s*Relations\s*$', line.strip(), re.IGNORECASE):
                in_relations = True
                continue
            
            # Check if we hit another ## heading (end of relations)
            if in_relations and re.match(r'^##\s+\w', line.strip()):
                break
            
            # Parse relation bullet points
            if in_relations:
                # Match bullet point: - or *
                bullet_match = re.match(r'^\s*[-*]\s+(.+)$', line)
                if bullet_match:
                    relation_text = bullet_match.group(1).strip()
                    
                    # Parse: <target> : <forward> : <reverse>
                    parts = [p.strip() for p in relation_text.split(':')]
                    if len(parts) == 3:
                        target, forward, reverse = parts
                        relations.append(EntityRelation(
                            target_entity_type=target,
                            forward_label=forward,
                            reverse_label=reverse,
                        ))
                        logger.debug(f"Extracted Relation: {target} : {forward} : {reverse}")
                    else:
                        logger.warning(f"Malformed relation line: {relation_text}")
        
        return relations
    
    def _extract_examples(self, content: str) -> List[EntityExample]:
        """
        Extract Examples from markdown.
        
        Pattern:
        ## Examples:
        ### <example name>
        <example description>
        ### <another example>
        <description>
        
        Args:
            content: Markdown content
            
        Returns:
            List of EntityExample objects
        """
        examples = []
        lines = content.split('\n')
        in_examples = False
        current_example_name = None
        current_example_lines = []
        
        for line in lines:
            # Check if we're in the examples section
            if re.match(r'^##\s*Examples\s*:?\s*$', line.strip(), re.IGNORECASE):
                in_examples = True
                continue
            
            # Check if we hit another ## heading (end of examples)
            if in_examples and re.match(r'^##\s+\w', line.strip()):
                # Save last example if any
                if current_example_name:
                    examples.append(EntityExample(
                        name=current_example_name,
                        description='\n'.join(current_example_lines).strip(),
                    ))
                break
            
            # Parse example headings and content
            if in_examples:
                # Check for ### heading (new example)
                example_match = re.match(r'^###\s+(.+)$', line.strip())
                if example_match:
                    # Save previous example if any
                    if current_example_name:
                        examples.append(EntityExample(
                            name=current_example_name,
                            description='\n'.join(current_example_lines).strip(),
                        ))
                        logger.debug(f"Extracted Example: {current_example_name}")
                    
                    # Start new example
                    current_example_name = example_match.group(1).strip()
                    current_example_lines = []
                else:
                    # Accumulate content for current example
                    if current_example_name:
                        current_example_lines.append(line)
        
        # Save last example if any
        if current_example_name:
            examples.append(EntityExample(
                name=current_example_name,
                description='\n'.join(current_example_lines).strip(),
            ))
            logger.debug(f"Extracted Example: {current_example_name}")
        
        return examples
