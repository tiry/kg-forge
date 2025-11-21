"""HTML parser for Confluence exports."""

import hashlib
import logging
import re
from pathlib import Path
from typing import List, Optional

from bs4 import BeautifulSoup
from markdownify import markdownify as md

from kg_forge.models.document import DocumentLink, ParsedDocument

logger = logging.getLogger(__name__)


class ConfluenceHTMLParser:
    """Parse Confluence HTML exports to structured documents."""

    def parse_file(self, filepath: Path) -> ParsedDocument:
        """
        Parse a single HTML file.

        Args:
            filepath: Path to the HTML file

        Returns:
            ParsedDocument with extracted content and metadata

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file cannot be parsed
        """
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        logger.info(f"Parsing file: {filepath}")

        # Read and parse HTML
        with open(filepath, "r", encoding="utf-8") as f:
            html_content = f.read()

        soup = BeautifulSoup(html_content, "lxml")

        # Extract all components
        doc_id = self._extract_doc_id(filepath.name)
        title = self._extract_title(soup)
        breadcrumb = self._extract_breadcrumb(soup)
        markdown_content = self._extract_content_as_markdown(soup)
        links = self._extract_links(soup)
        content_hash = self._generate_content_hash(markdown_content)

        # Create and return ParsedDocument
        return ParsedDocument(
            doc_id=doc_id,
            title=title,
            text=markdown_content,
            breadcrumb=breadcrumb,
            links=links,
            content_hash=content_hash,
            source_file=filepath.name,
        )

    def _extract_doc_id(self, filename: str) -> str:
        """
        Extract document ID from filename.

        Examples:
            "Content-Lake_3352431259.html" -> "3352431259"
            "Content-Lake---Content-Model_3182532046.html" -> "3182532046"

        Args:
            filename: HTML filename

        Returns:
            Document ID (numeric part before .html)
        """
        # Pattern: anything ending with _<digits>.html
        match = re.search(r"_(\d+)\.html$", filename)
        if match:
            return match.group(1)

        # Fallback: use filename without extension
        return Path(filename).stem

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """
        Extract document title from HTML.

        Args:
            soup: BeautifulSoup object

        Returns:
            Document title
        """
        # Try to find title in h1#title-heading
        title_elem = soup.find("h1", id="title-heading")
        if title_elem:
            # Get text from span#title-text if available
            title_text = title_elem.find("span", id="title-text")
            if title_text:
                return title_text.get_text(strip=True)
            return title_elem.get_text(strip=True)

        # Fallback to <title> tag
        title_tag = soup.find("title")
        if title_tag:
            return title_tag.get_text(strip=True)

        return "Untitled Document"

    def _extract_breadcrumb(self, soup: BeautifulSoup) -> List[str]:
        """
        Extract breadcrumb path from HTML.

        Args:
            soup: BeautifulSoup object

        Returns:
            List of breadcrumb items
        """
        breadcrumbs = []

        # Find breadcrumb list
        breadcrumb_list = soup.find("ol", id="breadcrumbs")
        if breadcrumb_list:
            # Extract all links in breadcrumb
            links = breadcrumb_list.find_all("a")
            breadcrumbs = [link.get_text(strip=True) for link in links]

        return breadcrumbs

    def _extract_content_as_markdown(self, soup: BeautifulSoup) -> str:
        """
        Convert HTML content to Markdown.

        Args:
            soup: BeautifulSoup object

        Returns:
            Content as Markdown string
        """
        # Try to find main content div
        content_div = soup.find("div", id="main-content")

        # Fallback to wiki-content class
        if not content_div:
            content_div = soup.find("div", class_="wiki-content")

        # If still no content, return empty
        if not content_div:
            logger.warning("No content div found in document")
            return ""

        # Convert to Markdown
        markdown_content = md(
            str(content_div),
            heading_style="ATX",  # Use # for headings
            bullets="-",  # Use - for lists
            strip=["script", "style"],  # Remove these tags
        )

        # Clean up excessive whitespace
        markdown_content = self._clean_markdown(markdown_content)

        return markdown_content

    def _clean_markdown(self, markdown: str) -> str:
        """
        Clean up markdown content.

        Args:
            markdown: Raw markdown string

        Returns:
            Cleaned markdown string
        """
        # Remove excessive blank lines (more than 2)
        markdown = re.sub(r"\n{3,}", "\n\n", markdown)

        # Strip leading/trailing whitespace
        markdown = markdown.strip()

        return markdown

    def _extract_links(self, soup: BeautifulSoup) -> List[DocumentLink]:
        """
        Extract all links from content area.

        Args:
            soup: BeautifulSoup object

        Returns:
            List of DocumentLink objects
        """
        links = []

        # Find content area
        content_div = soup.find("div", id="main-content")
        if not content_div:
            content_div = soup.find("div", class_="wiki-content")

        if not content_div:
            return links

        # Extract all links
        for a_tag in content_div.find_all("a", href=True):
            href = a_tag["href"]
            text = a_tag.get_text(strip=True)

            # Skip empty links or anchors
            if not href or href.startswith("#"):
                continue

            # Determine link type
            if href.startswith("http://") or href.startswith("https://"):
                link_type = "external"
            elif href.endswith(".html"):
                link_type = "internal"
            else:
                # Skip other types (attachments, etc.)
                continue

            links.append(DocumentLink(url=href, text=text, link_type=link_type))

        return links

    def _generate_content_hash(self, markdown_text: str) -> str:
        """
        Generate SHA-256 hash of markdown content.

        Args:
            markdown_text: Markdown content string

        Returns:
            SHA-256 hash hexdigest
        """
        return hashlib.sha256(markdown_text.encode("utf-8")).hexdigest()
