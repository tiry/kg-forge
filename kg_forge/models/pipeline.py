"""Pipeline models for orchestrating knowledge graph construction."""

from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime


@dataclass
class PipelineConfig:
    """Configuration for pipeline execution."""
    
    namespace: str
    source_dir: str
    entity_types: Optional[List[str]] = None
    min_confidence: float = 0.0
    skip_processed: bool = True
    batch_size: int = 10
    max_failures: int = 5
    interactive: bool = False  # Enable interactive mode for human-in-the-loop
    dry_run: bool = False  # Extract but don't write to graph


@dataclass
class DocumentProcessingResult:
    """Result of processing a single document."""
    
    document_id: str
    success: bool
    entities_found: int = 0
    relationships_created: int = 0
    processing_time: float = 0.0
    error: Optional[str] = None
    skipped: bool = False
    skip_reason: Optional[str] = None


@dataclass
class PipelineStatistics:
    """Overall pipeline execution statistics."""
    
    total_documents: int = 0
    processed: int = 0
    skipped: int = 0
    failed: int = 0
    total_entities: int = 0
    total_relationships: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    errors: List[str] = field(default_factory=list)
    
    @property
    def duration(self) -> float:
        """
        Calculate total execution time in seconds.
        
        Returns:
            Duration in seconds, or 0 if not yet complete
        """
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0
    
    @property
    def success_rate(self) -> float:
        """
        Calculate success rate percentage.
        
        Returns:
            Success rate as percentage (0-100)
        """
        if self.total_documents == 0:
            return 0.0
        return (self.processed / self.total_documents) * 100.0
