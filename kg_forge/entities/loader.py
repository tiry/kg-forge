"""Entity definitions loader."""

import logging
from pathlib import Path
from typing import Set

from kg_forge.entities.models import EntityDefinitions
from kg_forge.entities.parser import EntityMarkdownParser

logger = logging.getLogger(__name__)


class EntityDefinitionsLoader:
    """Load entity definitions from directory."""
    
    # Files to exclude from loading
    EXCLUDED_FILES: Set[str] = {
        "prompt_template.md",
        "readme.md",
        "README.md",
    }
    
    def __init__(self, entities_dir: Path):
        """
        Initialize loader.
        
        Args:
            entities_dir: Path to directory containing entity markdown files
        """
        self.entities_dir = Path(entities_dir)
        self.parser = EntityMarkdownParser()
    
    def load_all(self) -> EntityDefinitions:
        """
        Load all entity definitions from directory.
        
        Returns:
            EntityDefinitions containing all loaded definitions
            
        Raises:
            FileNotFoundError: If entities directory doesn't exist
        """
        if not self.entities_dir.exists():
            raise FileNotFoundError(f"Entities directory not found: {self.entities_dir}")
        
        if not self.entities_dir.is_dir():
            raise NotADirectoryError(f"Not a directory: {self.entities_dir}")
        
        definitions = EntityDefinitions()
        loaded_count = 0
        
        # Find all markdown files
        for md_file in sorted(self.entities_dir.glob("*.md")):
            if self._should_process_file(md_file):
                try:
                    definition = self._load_file(md_file)
                    definitions.definitions[definition.entity_type_id] = definition
                    loaded_count += 1
                    logger.info(f"Loaded entity definition: {definition.entity_type_id} from {md_file.name}")
                except Exception as e:
                    logger.error(f"Failed to load {md_file.name}: {e}")
                    # Continue loading other files
        
        logger.info(f"Loaded {loaded_count} entity definitions from {self.entities_dir}")
        return definitions
    
    def _should_process_file(self, filepath: Path) -> bool:
        """
        Check if file should be processed.
        
        Excludes prompt_template.md, README.md, etc.
        
        Args:
            filepath: Path to file
            
        Returns:
            True if file should be processed
        """
        filename = filepath.name.lower()
        
        if filename in {f.lower() for f in self.EXCLUDED_FILES}:
            logger.debug(f"Skipping excluded file: {filepath.name}")
            return False
        
        return True
    
    def _load_file(self, filepath: Path) -> "EntityDefinition":
        """
        Load and parse a single entity definition file.
        
        Args:
            filepath: Path to markdown file
            
        Returns:
            Parsed EntityDefinition
            
        Raises:
            IOError: If file cannot be read
        """
        content = filepath.read_text(encoding='utf-8')
        return self.parser.parse(content, filepath.name)
