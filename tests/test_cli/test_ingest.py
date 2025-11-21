"""Tests for ingest CLI command."""

import pytest
from pathlib import Path
from click.testing import CliRunner

from kg_forge.cli.main import cli


@pytest.fixture
def runner():
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def test_data_dir():
    """Get path to test data directory."""
    return Path(__file__).parent.parent.parent / "test_data"


def test_ingest_with_output_dir(runner, test_data_dir, tmp_path):
    """Test ingesting HTML files to markdown output directory."""
    output_dir = tmp_path / "output"
    
    result = runner.invoke(cli, [
        "ingest",
        "--source", str(test_data_dir),
        "--output-dir", str(output_dir)
    ])
    
    assert result.exit_code == 0
    assert "Successfully exported" in result.output
    assert output_dir.exists()
    
    # Check that markdown files were created
    md_files = list(output_dir.glob("*.md"))
    assert len(md_files) == 3  # Should have 3 markdown files
    
    # Check file naming (should be doc_id.md)
    file_names = {f.name for f in md_files}
    assert "3352431259.md" in file_names
    assert "3182532046.md" in file_names
    assert "3352234692.md" in file_names


def test_ingest_output_file_content(runner, test_data_dir, tmp_path):
    """Test that exported markdown files have correct content."""
    output_dir = tmp_path / "output"
    
    result = runner.invoke(cli, [
        "ingest",
        "--source", str(test_data_dir),
        "--output-dir", str(output_dir)
    ])
    
    assert result.exit_code == 0
    
    # Read one of the output files
    output_file = output_dir / "3352234692.md"
    assert output_file.exists()
    
    content = output_file.read_text()
    
    # Check for metadata header
    assert "Document ID:" in content
    assert "3352234692" in content
    assert "Source:" in content
    assert "Breadcrumb:" in content
    assert "Content Hash:" in content
    
    # Check for actual content
    assert "Content Lake" in content


def test_ingest_creates_output_dir(runner, test_data_dir, tmp_path):
    """Test that ingest creates output directory if it doesn't exist."""
    output_dir = tmp_path / "nested" / "output" / "path"
    assert not output_dir.exists()
    
    result = runner.invoke(cli, [
        "ingest",
        "--source", str(test_data_dir),
        "--output-dir", str(output_dir)
    ])
    
    assert result.exit_code == 0
    assert output_dir.exists()
    assert len(list(output_dir.glob("*.md"))) == 3


def test_ingest_without_output_dir(runner, test_data_dir):
    """Test ingest without output-dir shows stub message."""
    result = runner.invoke(cli, [
        "ingest",
        "--source", str(test_data_dir)
    ])
    
    assert result.exit_code == 0
    assert "will be implemented" in result.output.lower()


def test_ingest_invalid_source(runner, tmp_path):
    """Test ingest with invalid source directory."""
    output_dir = tmp_path / "output"
    
    result = runner.invoke(cli, [
        "ingest",
        "--source", "/nonexistent/path",
        "--output-dir", str(output_dir)
    ])
    
    assert result.exit_code != 0


def test_ingest_with_namespace(runner, test_data_dir, tmp_path):
    """Test ingest with custom namespace."""
    output_dir = tmp_path / "output"
    
    result = runner.invoke(cli, [
        "ingest",
        "--source", str(test_data_dir),
        "--output-dir", str(output_dir),
        "--namespace", "test"
    ])
    
    assert result.exit_code == 0
    assert "test" in result.output or "Successfully exported" in result.output
