"""Tests for pipeline models."""

import pytest
from datetime import datetime, timedelta

from kg_forge.models.pipeline import (
    PipelineConfig,
    DocumentProcessingResult,
    PipelineStatistics,
)


class TestPipelineConfig:
    """Tests for PipelineConfig."""
    
    def test_default_values(self):
        """Test default configuration values."""
        config = PipelineConfig(
            namespace="test",
            source_dir="/path/to/docs"
        )
        
        assert config.namespace == "test"
        assert config.source_dir == "/path/to/docs"
        assert config.entity_types is None
        assert config.min_confidence == 0.0
        assert config.skip_processed is True
        assert config.batch_size == 10
        assert config.max_failures == 5
        assert config.interactive is False
        assert config.dry_run is False
    
    def test_custom_values(self):
        """Test custom configuration values."""
        config = PipelineConfig(
            namespace="custom",
            source_dir="/custom/path",
            entity_types=["product", "component"],
            min_confidence=0.7,
            skip_processed=False,
            batch_size=20,
            max_failures=10,
            interactive=True,
            dry_run=True
        )
        
        assert config.namespace == "custom"
        assert config.entity_types == ["product", "component"]
        assert config.min_confidence == 0.7
        assert config.skip_processed is False
        assert config.batch_size == 20
        assert config.max_failures == 10
        assert config.interactive is True
        assert config.dry_run is True


class TestDocumentProcessingResult:
    """Tests for DocumentProcessingResult."""
    
    def test_success_result(self):
        """Test successful processing result."""
        result = DocumentProcessingResult(
            document_id="doc1.html",
            success=True,
            entities_found=5,
            relationships_created=10,
            processing_time=2.5
        )
        
        assert result.document_id == "doc1.html"
        assert result.success is True
        assert result.entities_found == 5
        assert result.relationships_created == 10
        assert result.processing_time == 2.5
        assert result.error is None
        assert result.skipped is False
    
    def test_failed_result(self):
        """Test failed processing result."""
        result = DocumentProcessingResult(
            document_id="doc2.html",
            success=False,
            error="Extraction failed",
            processing_time=1.0
        )
        
        assert result.document_id == "doc2.html"
        assert result.success is False
        assert result.error == "Extraction failed"
        assert result.entities_found == 0
        assert result.relationships_created == 0
    
    def test_skipped_result(self):
        """Test skipped processing result."""
        result = DocumentProcessingResult(
            document_id="doc3.html",
            success=True,
            skipped=True,
            skip_reason="Already processed",
            processing_time=0.1
        )
        
        assert result.document_id == "doc3.html"
        assert result.success is True
        assert result.skipped is True
        assert result.skip_reason == "Already processed"


class TestPipelineStatistics:
    """Tests for PipelineStatistics."""
    
    def test_default_values(self):
        """Test default statistics values."""
        stats = PipelineStatistics()
        
        assert stats.total_documents == 0
        assert stats.processed == 0
        assert stats.skipped == 0
        assert stats.failed == 0
        assert stats.total_entities == 0
        assert stats.total_relationships == 0
        assert stats.start_time is None
        assert stats.end_time is None
        assert stats.errors == []
    
    def test_duration_calculation(self):
        """Test duration property calculation."""
        stats = PipelineStatistics()
        
        # No times set
        assert stats.duration == 0.0
        
        # With times set
        start = datetime(2024, 1, 1, 12, 0, 0)
        end = datetime(2024, 1, 1, 12, 5, 30)
        stats.start_time = start
        stats.end_time = end
        
        expected_duration = 330.0  # 5 minutes 30 seconds
        assert stats.duration == expected_duration
    
    def test_success_rate_calculation(self):
        """Test success rate property calculation."""
        stats = PipelineStatistics()
        
        # No documents
        assert stats.success_rate == 0.0
        
        # With documents
        stats.total_documents = 10
        stats.processed = 8
        stats.skipped = 1
        stats.failed = 1
        
        assert stats.success_rate == 80.0
    
    def test_success_rate_all_processed(self):
        """Test success rate when all documents processed."""
        stats = PipelineStatistics()
        stats.total_documents = 5
        stats.processed = 5
        
        assert stats.success_rate == 100.0
    
    def test_success_rate_all_failed(self):
        """Test success rate when all documents failed."""
        stats = PipelineStatistics()
        stats.total_documents = 5
        stats.failed = 5
        
        assert stats.success_rate == 0.0
    
    def test_error_tracking(self):
        """Test error list tracking."""
        stats = PipelineStatistics()
        
        stats.errors.append("doc1: Network error")
        stats.errors.append("doc2: Timeout")
        
        assert len(stats.errors) == 2
        assert "doc1: Network error" in stats.errors
        assert "doc2: Timeout" in stats.errors
