"""Dictionary-based normalization for entity names."""

from pathlib import Path
from typing import Dict, TYPE_CHECKING

from kg_forge.pipeline.hooks.normalization.basic import normalize_text

if TYPE_CHECKING:
    from kg_forge.pipeline.orchestrator import PipelineContext
    from kg_forge.models.extraction import ExtractionResult


class DictionaryNormalizer:
    """Normalizes entities using a lookup dictionary."""
    
    def __init__(self, dict_path: Path):
        """
        Initialize dictionary normalizer.
        
        Args:
            dict_path: Path to normalization dictionary file
        """
        self.dict_path = dict_path
        self.dictionary = self._load_dictionary(dict_path)
    
    def _load_dictionary(self, path: Path) -> Dict[str, str]:
        """
        Load normalization dictionary from file.
        
        File format (one entry per line):
            KEY : Value
            
        Example:
            KD : Knowledge Discovery
            K8S : Kubernetes
            ML : Machine Learning
        
        Args:
            path: Path to dictionary file
            
        Returns:
            Dictionary mapping normalized keys to expansion values
        """
        dictionary = {}
        
        if not path.exists():
            return dictionary
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue
                    
                    # Parse key : value
                    if ':' not in line:
                        continue
                    
                    key, value = line.split(':', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    if key and value:
                        # Store normalized version as key for matching
                        normalized_key = normalize_text(key)
                        dictionary[normalized_key] = value
        
        except Exception as e:
            # Log error but don't fail - just return empty dictionary
            print(f"Warning: Failed to load dictionary from {path}: {e}")
        
        return dictionary
    
    def normalize(self, text: str) -> str:
        """
        Normalize text using dictionary lookup, then basic normalization.
        
        Process:
        1. Apply basic normalization to input
        2. Check if normalized version exists in dictionary
        3. If found, use expanded value
        4. Apply basic normalization to result
        
        Args:
            text: Text to normalize
            
        Returns:
            Normalized text
            
        Examples:
            >>> normalizer = DictionaryNormalizer(Path("dict.txt"))
            >>> normalizer.dictionary = {"k8s": "Kubernetes"}
            >>> normalizer.normalize("K8S")
            'kubernetes'
            >>> normalizer.normalize("K8s (Container)")
            'kubernetes container'
        """
        if not text:
            return ""
        
        # First apply basic normalization to input
        normalized_key = normalize_text(text)
        
        # Check dictionary
        if normalized_key in self.dictionary:
            # Use expanded value from dictionary
            text = self.dictionary[normalized_key]
        
        # Apply basic normalization to final result
        return normalize_text(text)


def dictionary_normalize_entities(
    context: "PipelineContext",
    extraction_result: "ExtractionResult"
) -> "ExtractionResult":
    """
    Normalize entities using dictionary lookup.
    
    This hook expands abbreviations and standardizes terminology
    using a configurable dictionary file.
    
    The dictionary file should be located at:
        config/normalization_dict.txt
    
    Or configured via settings:
        settings.pipeline.normalization_dict_path
    
    Args:
        context: Pipeline context with logger and settings
        extraction_result: Extraction result containing entities
        
    Returns:
        Modified extraction result with normalized entity names
    """
    if not extraction_result.entities:
        return extraction_result
    
    # Get dictionary path from settings
    settings = context.settings
    dict_path_str = getattr(
        settings.pipeline if hasattr(settings, 'pipeline') else settings.app,
        'normalization_dict_path',
        'config/normalization_dict.txt'
    )
    dict_path = Path(dict_path_str)
    
    # Make path absolute if relative
    if not dict_path.is_absolute():
        # Assume relative to project root (parent of kg_forge package)
        import kg_forge
        pkg_path = Path(kg_forge.__file__).parent
        dict_path = pkg_path.parent / dict_path
    
    # Create normalizer
    normalizer = DictionaryNormalizer(dict_path)
    
    if not normalizer.dictionary:
        context.logger.debug(
            f"Dictionary normalizer: No dictionary loaded from {dict_path}"
        )
        return extraction_result
    
    context.logger.debug(
        f"Dictionary normalizer: Loaded {len(normalizer.dictionary)} entries"
    )
    
    # Normalize entities
    normalized_count = 0
    
    for entity in extraction_result.entities:
        original_name = entity.name
        normalized = normalizer.normalize(original_name)
        
        # Update the entity
        entity.name = normalized
        entity.properties['normalized_name'] = normalized
        
        # Track changes
        if original_name != normalized:
            normalized_count += 1
            context.logger.debug(
                f"Dictionary normalized: '{original_name}' → '{normalized}'"
            )
    
    if normalized_count > 0:
        context.logger.info(
            f"Dictionary normalization applied to {normalized_count} entities"
        )
    
    return extraction_result
