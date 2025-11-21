"""Document loader for bulk HTML parsing."""

import logging
from pathlib import Path
from typing import List

from kg_forge.models.document import ParsedDocument
from kg_forge.parsers.html_parser import ConfluenceHTMLParser

logger = logging.getLogger(__name__)


class DocumentLoader:
    """Load and parse multiple HTML documents."""

    def __init__(self, parser: ConfluenceHTMLParser = None):
        """
        Initialize document loader.

        Args:
            parser: HTML parser instance (creates default if not provided)
        """
        self.parser = parser or ConfluenceHTMLParser()

    def load_from_directory(
        self, directory: Path, pattern: str = "*.html"
    ) -> List[ParsedDocument]:
        """
        Load all HTML files from a directory.

        Args:
            directory: Path to directory containing HTML files
            pattern: Glob pattern for matching files (default: "*.html")

        Returns:
            List of ParsedDocument objects

        Raises:
            FileNotFoundError: If directory doesn't exist
            ValueError: If no HTML files found
        """
        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")

        if not directory.is_dir():
            raise ValueError(f"Not a directory: {directory}")

        # Find all HTML files
        html_files = list(directory.glob(pattern))

        if not html_files:
            raise ValueError(f"No files matching '{pattern}' found in {directory}")

        logger.info(f"Found {len(html_files)} HTML files in {directory}")

        # Parse all files
        documents = []
        for filepath in html_files:
            try:
                doc = self.parser.parse_file(filepath)
                documents.append(doc)
                logger.debug(f"Successfully parsed: {filepath.name}")
            except Exception as e:
                logger.error(f"Failed to parse {filepath.name}: {e}")
                # Continue with other files
                continue

        logger.info(f"Successfully parsed {len(documents)}/{len(html_files)} files")

        return documents

    def load_files(self, filepaths: List[Path]) -> List[ParsedDocument]:
        """
        Load specific HTML files.

        Args:
            filepaths: List of file paths to parse

        Returns:
            List of ParsedDocument objects
        """
        documents = []

        for filepath in filepaths:
            try:
                doc = self.parser.parse_file(filepath)
                documents.append(doc)
                logger.debug(f"Successfully parsed: {filepath.name}")
            except Exception as e:
                logger.error(f"Failed to parse {filepath.name}: {e}")
                # Continue with other files
                continue

        logger.info(f"Successfully parsed {len(documents)}/{len(filepaths)} files")

        return documents
