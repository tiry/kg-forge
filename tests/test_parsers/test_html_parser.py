"""Tests for ConfluenceHTMLParser."""

import hashlib
from pathlib import Path

import pytest

from kg_forge.parsers.html_parser import ConfluenceHTMLParser
from kg_forge.models.document import ParsedDocument, DocumentLink


@pytest.fixture
def parser():
    """Create parser instance."""
    return ConfluenceHTMLParser()


@pytest.fixture
def test_data_dir():
    """Get test data directory path."""
    return Path(__file__).parent.parent.parent / "test_data"


def test_extract_doc_id(parser):
    """Test document ID extraction from filename."""
    assert parser._extract_doc_id("Content-Lake_3352431259.html") == "3352431259"
    assert (
        parser._extract_doc_id("Content-Lake---Content-Model_3182532046.html")
        == "3182532046"
    )
    assert parser._extract_doc_id("test_file.html") == "test_file"


def test_parse_file_not_found(parser):
    """Test parsing non-existent file raises error."""
    with pytest.raises(FileNotFoundError):
        parser.parse_file(Path("/nonexistent/file.html"))


def test_parse_simple_document(parser, test_data_dir):
    """Test parsing a simple Confluence page."""
    # This test requires actual test files
    test_file = test_data_dir / "Content-Lake_3352431259.html"

    if not test_file.exists():
        pytest.skip("Test data file not found")

    doc = parser.parse_file(test_file)

    # Verify basic structure
    assert isinstance(doc, ParsedDocument)
    assert doc.doc_id == "3352431259"
    assert doc.source_file == "Content-Lake_3352431259.html"
    assert len(doc.content_hash) == 64  # SHA-256 hash length


def test_parse_document_with_content(parser, test_data_dir):
    """Test parsing document with actual content."""
    test_file = test_data_dir / "Content-Lake---Content-Model_3182532046.html"

    if not test_file.exists():
        pytest.skip("Test data file not found")

    doc = parser.parse_file(test_file)

    # Verify document structure
    assert doc.doc_id == "3182532046"
    assert "Content Lake" in doc.title
    assert len(doc.breadcrumb) > 0
    assert len(doc.text) > 0  # Should have markdown content

    # Verify content hash is consistent
    expected_hash = hashlib.sha256(doc.text.encode("utf-8")).hexdigest()
    assert doc.content_hash == expected_hash


def test_extract_title(parser, test_data_dir):
    """Test title extraction."""
    test_file = test_data_dir / "Content-Lake---Content-Model_3182532046.html"

    if not test_file.exists():
        pytest.skip("Test data file not found")

    doc = parser.parse_file(test_file)
    assert "Content" in doc.title
    assert len(doc.title) > 0


def test_extract_breadcrumb(parser, test_data_dir):
    """Test breadcrumb extraction."""
    test_file = test_data_dir / "Content-Lake---Content-Model_3182532046.html"

    if not test_file.exists():
        pytest.skip("Test data file not found")

    doc = parser.parse_file(test_file)
    assert len(doc.breadcrumb) >= 2  # Should have at least 2 breadcrumb items
    assert isinstance(doc.breadcrumb, list)
    assert all(isinstance(item, str) for item in doc.breadcrumb)


def test_extract_links(parser, test_data_dir):
    """Test link extraction."""
    test_file = test_data_dir / "Content-Lake---Content-Model_3182532046.html"

    if not test_file.exists():
        pytest.skip("Test data file not found")

    doc = parser.parse_file(test_file)

    # Should have extracted some links
    assert isinstance(doc.links, list)

    # Verify link structure
    for link in doc.links:
        assert isinstance(link, DocumentLink)
        assert link.link_type in ["internal", "external"]
        assert len(link.url) > 0


def test_markdown_conversion(parser, test_data_dir):
    """Test HTML to Markdown conversion."""
    test_file = test_data_dir / "Content-Lake---Content-Model_3182532046.html"

    if not test_file.exists():
        pytest.skip("Test data file not found")

    doc = parser.parse_file(test_file)

    # Markdown should contain headings
    assert "#" in doc.text  # Has headings

    # Should not have HTML tags
    assert "<div" not in doc.text
    assert "<p>" not in doc.text


def test_content_hash_consistency(parser, test_data_dir):
    """Test that content hash is consistent across multiple parses."""
    test_file = test_data_dir / "Content-Lake_3352431259.html"

    if not test_file.exists():
        pytest.skip("Test data file not found")

    doc1 = parser.parse_file(test_file)
    doc2 = parser.parse_file(test_file)

    assert doc1.content_hash == doc2.content_hash
