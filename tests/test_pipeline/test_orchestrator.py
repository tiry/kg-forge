"""Tests for pipeline orchestrator."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from kg_forge.pipeline.orchestrator import PipelineOrchestrator, PipelineError
from kg_forge.models.pipeline import PipelineConfig, DocumentProcessingResult
from kg_forge.models.document import ParsedDocument
from kg_forge.models.extraction import ExtractionResult, ExtractedEntity


@pytest.fixture
def mock_config():
    """Create a mock pipeline configuration."""
    return PipelineConfig(
        namespace="test",
        source_dir="/fake/path",
        entity_types=["Product", "Component"],
        min_confidence=0.7,
        skip_processed=True,
        dry_run=False
    )


@pytest.fixture
def mock_extractor():
    """Create a mock entity extractor."""
    extractor = Mock()
    # Default to successful extraction
    extractor.extract.return_value = ExtractionResult(
        success=True,
        entities=[
            ExtractedEntity(
                entity_type="Product",
                name="Test Product",
                confidence=0.9,
                properties={}
            )
        ]
    )
    return extractor


@pytest.fixture
def mock_graph_client():
    """Create a mock graph client."""
    return Mock()


@pytest.fixture
def sample_document():
    """Create a sample parsed document."""
    return ParsedDocument(
        doc_id="test123",
        title="Test Document",
        text="This is test content",
        content_hash="abc123hash",
        source_file="test.html",
        metadata={}
    )


class TestPipelineOrchestratorInit:
    """Tests for orchestrator initialization."""
    
    def test_initialization(self, mock_config, mock_extractor, mock_graph_client):
        """Test that orchestrator initializes correctly."""
        orchestrator = PipelineOrchestrator(
            mock_config,
            mock_extractor,
            mock_graph_client
        )
        
        assert orchestrator.config == mock_config
        assert orchestrator.extractor == mock_extractor
        assert orchestrator.graph_client == mock_graph_client
        assert orchestrator.stats.total_documents == 0
        assert len(orchestrator.batch_entities) == 0
    
    def test_init_creates_repositories(self, mock_config, mock_extractor, mock_graph_client):
        """Test that initialization creates document and entity repositories."""
        orchestrator = PipelineOrchestrator(
            mock_config,
            mock_extractor,
            mock_graph_client
        )
        
        assert orchestrator.document_repo is not None
        assert orchestrator.entity_repo is not None


class TestProcessDocument:
    """Tests for document processing."""
    
    def test_process_document_success(
        self,
        mock_config,
        mock_extractor,
        mock_graph_client,
        sample_document
    ):
        """Test successful document processing."""
        orchestrator = PipelineOrchestrator(
            mock_config,
            mock_extractor,
            mock_graph_client
        )
        
        # Mock repositories
        orchestrator.document_repo = Mock()
        orchestrator.entity_repo = Mock()
        orchestrator.document_repo.document_hash_exists.return_value = False
        orchestrator.entity_repo.get_entity.return_value = None
        
        result = orchestrator._process_document(sample_document)
        
        assert result.success is True
        assert result.document_id == "test123"
        assert result.entities_found == 1
        assert result.processing_time > 0
    
    def test_process_document_skipped_already_processed(
        self,
        mock_config,
        mock_extractor,
        mock_graph_client,
        sample_document
    ):
        """Test that already processed documents are skipped."""
        orchestrator = PipelineOrchestrator(
            mock_config,
            mock_extractor,
            mock_graph_client
        )
        
        # Mock document as already processed
        orchestrator.document_repo = Mock()
        orchestrator.document_repo.document_hash_exists.return_value = True
        
        result = orchestrator._process_document(sample_document)
        
        assert result.success is True
        assert result.skipped is True
        assert result.skip_reason == "Already processed (hash match)"
    
    def test_process_document_extraction_failure(
        self,
        mock_config,
        mock_extractor,
        mock_graph_client,
        sample_document
    ):
        """Test handling of extraction failures."""
        # Configure extractor to fail
        mock_extractor.extract.return_value = ExtractionResult(
            success=False,
            entities=[],
            error="LLM timeout"
        )
        
        orchestrator = PipelineOrchestrator(
            mock_config,
            mock_extractor,
            mock_graph_client
        )
        
        orchestrator.document_repo = Mock()
        orchestrator.document_repo.document_hash_exists.return_value = False
        
        result = orchestrator._process_document(sample_document)
        
        assert result.success is False
        assert result.error == "LLM timeout"
    
    def test_process_document_dry_run(
        self,
        mock_extractor,
        mock_graph_client,
        sample_document
    ):
        """Test that dry run doesn't write to graph."""
        config = PipelineConfig(
            namespace="test",
            source_dir="/fake",
            dry_run=True
        )
        
        orchestrator = PipelineOrchestrator(
            config,
            mock_extractor,
            mock_graph_client
        )
        
        orchestrator.document_repo = Mock()
        orchestrator.entity_repo = Mock()
        orchestrator.document_repo.document_hash_exists.return_value = False
        
        result = orchestrator._process_document(sample_document)
        
        assert result.success is True
        # In dry run, no entities are created
        orchestrator.document_repo.create_document.assert_not_called()
        orchestrator.entity_repo.create_entity.assert_not_called()


class TestLoadDocuments:
    """Tests for document loading."""
    
    def test_load_documents_success(
        self,
        mock_config,
        mock_extractor,
        mock_graph_client,
        tmp_path
    ):
        """Test successful document loading."""
        # Create test HTML files
        (tmp_path / "test1.html").write_text("<html><body>Test</body></html>")
        (tmp_path / "test2.html").write_text("<html><body>Test</body></html>")
        
        # Update config to point to temp path
        mock_config.source_dir = str(tmp_path)
        
        orchestrator = PipelineOrchestrator(
            mock_config,
            mock_extractor,
            mock_graph_client
        )
        
        file_paths = orchestrator._load_documents()
        
        assert len(file_paths) == 2
        # Should return Path objects, not ParsedDocument objects
        from pathlib import Path
        assert all(isinstance(p, Path) for p in file_paths)
    
    def test_load_documents_empty_directory(
        self,
        mock_config,
        mock_extractor,
        mock_graph_client,
        tmp_path
    ):
        """Test loading from empty directory."""
        # Update config to point to empty temp path
        mock_config.source_dir = str(tmp_path)
        
        orchestrator = PipelineOrchestrator(
            mock_config,
            mock_extractor,
            mock_graph_client
        )
        
        with pytest.raises(PipelineError, match="No HTML files found"):
            orchestrator._load_documents()
    
    def test_load_documents_error(
        self,
        mock_config,
        mock_extractor,
        mock_graph_client
    ):
        """Test handling of document loading errors."""
        # Config points to non-existent directory
        mock_config.source_dir = "/nonexistent/path"
        
        orchestrator = PipelineOrchestrator(
            mock_config,
            mock_extractor,
            mock_graph_client
        )
        
        with pytest.raises(PipelineError, match="Failed to load documents"):
            orchestrator._load_documents()


class TestRunPipeline:
    """Tests for full pipeline execution."""
    
    def test_run_empty_directory(
        self,
        mock_config,
        mock_extractor,
        mock_graph_client
    ):
        """Test running pipeline on empty directory."""
        orchestrator = PipelineOrchestrator(
            mock_config,
            mock_extractor,
            mock_graph_client
        )
        
        # Mock empty document list
        orchestrator._load_documents = Mock(return_value=[])
        
        stats = orchestrator.run()
        
        assert stats.total_documents == 0
        assert stats.processed == 0
        assert stats.failed == 0
    
    def test_run_with_consecutive_failures(
        self,
        mock_extractor,
        mock_graph_client,
        tmp_path
    ):
        """Test that pipeline aborts after max consecutive failures."""
        # Create temp HTML files
        for i in range(5):
            (tmp_path / f"test{i}.html").write_text(f"<html><body>Test {i}</body></html>")
        
        config = PipelineConfig(
            namespace="test",
            source_dir=str(tmp_path),
            max_failures=2  # Abort after 2 consecutive failures
        )
        
        # Configure extractor to always fail
        mock_extractor.extract.return_value = ExtractionResult(
            success=False,
            entities=[],
            error="Always fails"
        )
        
        orchestrator = PipelineOrchestrator(
            config,
            mock_extractor,
            mock_graph_client
        )
        
        orchestrator.document_repo = Mock()
        orchestrator.document_repo.document_hash_exists.return_value = False
        
        with pytest.raises(PipelineError, match="consecutive failures"):
            orchestrator.run()
    
    def test_statistics_tracking(
        self,
        mock_config,
        mock_extractor,
        mock_graph_client,
        tmp_path
    ):
        """Test that statistics are tracked correctly."""
        # Create temp HTML files
        for i in range(3):
            (tmp_path / f"test{i}.html").write_text(f"<html><body><div class='wiki-content'><p>Test {i}</p></div></body></html>")
        
        mock_config.source_dir = str(tmp_path)
        
        orchestrator = PipelineOrchestrator(
            mock_config,
            mock_extractor,
            mock_graph_client
        )
        
        orchestrator.document_repo = Mock()
        orchestrator.entity_repo = Mock()
        orchestrator.document_repo.document_hash_exists.return_value = False
        orchestrator.entity_repo.get_entity.return_value = None
        
        stats = orchestrator.run()
        
        assert stats.total_documents == 3
        assert stats.processed == 3
        assert stats.total_entities == 3  # 1 entity per document
        assert stats.duration > 0
        assert stats.success_rate == 100.0


class TestIngestToGraph:
    """Tests for graph ingestion."""
    
    def test_ingest_creates_document_and_entities(
        self,
        mock_config,
        mock_extractor,
        mock_graph_client,
        sample_document
    ):
        """Test that ingestion creates documents and entities."""
        orchestrator = PipelineOrchestrator(
            mock_config,
            mock_extractor,
            mock_graph_client
        )
        
        orchestrator.document_repo = Mock()
        orchestrator.entity_repo = Mock()
        orchestrator.entity_repo.get_entity.return_value = None  # Entity doesn't exist
        
        entities = [
            ExtractedEntity(
                entity_type="Product",
                name="Test Product",
                confidence=0.9,
                properties={}
            )
        ]
        
        entities_created, rels_created = orchestrator._ingest_to_graph(
            sample_document,
            entities
        )
        
        assert entities_created == 1
        assert rels_created == 1
        orchestrator.document_repo.create_document.assert_called_once()
        orchestrator.entity_repo.create_entity.assert_called_once()
    
    def test_ingest_skips_existing_entities(
        self,
        mock_config,
        mock_extractor,
        mock_graph_client,
        sample_document
    ):
        """Test that existing entities are not recreated (via DuplicateEntityError)."""
        from kg_forge.graph.exceptions import DuplicateEntityError
        
        orchestrator = PipelineOrchestrator(
            mock_config,
            mock_extractor,
            mock_graph_client
        )
        
        orchestrator.document_repo = Mock()
        orchestrator.entity_repo = Mock()
        # Simulate entity already exists by raising DuplicateEntityError
        orchestrator.entity_repo.create_entity.side_effect = DuplicateEntityError(
            "test", "Product", "Test Product"
        )
        
        entities = [
            ExtractedEntity(
                entity_type="Product",
                name="Test Product",
                confidence=0.9,
                properties={}
            )
        ]
        
        entities_created, rels_created = orchestrator._ingest_to_graph(
            sample_document,
            entities
        )
        
        assert entities_created == 0  # Entity already existed (DuplicateEntityError caught)
        assert rels_created == 1  # But relationship still created
        # create_entity WAS called, but raised DuplicateEntityError
        orchestrator.entity_repo.create_entity.assert_called_once()
