"""
Pipeline orchestrator for end-to-end knowledge graph construction.

Coordinates document loading, entity extraction, and graph ingestion
with progress tracking, error handling, and hook support.
"""

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from kg_forge.models.pipeline import (
    PipelineConfig,
    DocumentProcessingResult,
    PipelineStatistics,
)
from kg_forge.models.document import ParsedDocument
from kg_forge.models.extraction import ExtractionRequest, ExtractedEntity, ExtractedRelationship
from kg_forge.extractors.base import EntityExtractor
from kg_forge.parsers.html_parser import ConfluenceHTMLParser
from kg_forge.parsers.document_loader import DocumentLoader
from kg_forge.graph.base import GraphClient
from kg_forge.graph.neo4j.document_repo import Neo4jDocumentRepository
from kg_forge.graph.neo4j.entity_repo import Neo4jEntityRepository
from kg_forge.graph.exceptions import GraphError, DuplicateEntityError
from kg_forge.pipeline.hooks import get_hook_registry, InteractiveSession

logger = logging.getLogger(__name__)


class PipelineError(Exception):
    """Raised when the pipeline encounters a catastrophic failure."""
    pass


class PipelineOrchestrator:
    """
    Orchestrates the end-to-end knowledge graph construction pipeline.
    
    Coordinates:
    - Document loading from HTML files
    - Entity extraction via LLM
    - Graph ingestion into Neo4j
    - Progress tracking and error handling
    - Hook execution for extensibility
    """
    
    def __init__(
        self,
        config: PipelineConfig,
        extractor: EntityExtractor,
        graph_client: GraphClient
    ):
        """
        Initialize pipeline orchestrator.
        
        Args:
            config: Pipeline configuration
            extractor: Entity extractor (LLM-based)
            graph_client: Neo4j graph database client
        """
        self.config = config
        self.extractor = extractor
        self.graph_client = graph_client
        
        # Initialize repositories
        self.document_repo = Neo4jDocumentRepository(graph_client)
        self.entity_repo = Neo4jEntityRepository(graph_client)
        
        # Initialize document loader with parser
        parser = ConfluenceHTMLParser()
        self.document_loader = DocumentLoader(parser)
        
        # Statistics tracking
        self.stats = PipelineStatistics()
        
        # Hook registry
        self.hook_registry = get_hook_registry()
        
        # Interactive session (if enabled)
        self.interactive_session = InteractiveSession(enabled=config.interactive)
        
        # Track processed entities for after_batch hooks
        self.batch_entities: List[ExtractedEntity] = []
        
        logger.info(f"Initialized pipeline for namespace: {config.namespace}")
        logger.info(f"Interactive mode: {config.interactive}, Dry run: {config.dry_run}")
    
    def run(self) -> PipelineStatistics:
        """
        Execute the complete pipeline.
        
        Returns:
            Pipeline statistics
            
        Raises:
            PipelineError: If pipeline fails catastrophically
        """
        self.stats.start_time = datetime.now()
        
        try:
            # Find HTML files (don't parse yet - one at a time)
            html_files = self._load_documents()
            self.stats.total_documents = len(html_files)
            
            logger.info(f"ℹ️  Loaded {len(html_files)} documents from {self.config.source_dir}\n")
            
            if len(html_files) == 0:
                logger.warning("No documents found to process")
                self.stats.end_time = datetime.now()
                return self.stats
            
            # Process each file one at a time
            consecutive_failures = 0
            processed_count = 0  # Track processed docs (excludes skipped)
            
            for file_path in html_files:
                # Check if we've reached the batch limit (only count processed docs)
                if self.config.max_batch_docs is not None and processed_count >= self.config.max_batch_docs:
                    logger.info(f"Reached batch limit of {self.config.max_batch_docs} processed documents")
                    break
                
                # Parse document on demand
                try:
                    doc = self.document_loader.parser.parse_file(file_path)
                except Exception as e:
                    logger.error(f"Failed to parse {file_path.name}: {e}")
                    result = DocumentProcessingResult(
                        document_id=file_path.stem,
                        success=False,
                        error=f"Parse error: {e}",
                        processing_time=0.0
                    )
                    self._update_statistics(result)
                    self._log_progress(result)
                    consecutive_failures += 1
                    if consecutive_failures >= self.config.max_failures:
                        raise PipelineError(
                            f"Aborting: {consecutive_failures} consecutive failures exceeded threshold"
                        )
                    continue
                
                result = self._process_document(doc)
                
                # Update statistics
                self._update_statistics(result)
                
                # Track processed count (excluding skipped documents)
                if result.success and not result.skipped:
                    processed_count += 1
                
                # Track consecutive failures
                if result.success:
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                    
                    if consecutive_failures >= self.config.max_failures:
                        raise PipelineError(
                            f"Aborting: {consecutive_failures} consecutive failures exceeded threshold"
                        )
                
                # Log progress
                self._log_progress(result)
            
            # Run after_batch hooks if any entities were processed
            if self.batch_entities and self.hook_registry.after_batch_hooks:
                logger.info("Running after_batch hooks...")
                self.hook_registry.run_after_batch(
                    self.batch_entities,
                    self.graph_client,
                    self.interactive_session,
                    namespace=self.config.namespace  # Pass namespace to hooks
                )
            
            self.stats.end_time = datetime.now()
            logger.info(f"Pipeline completed: {self.stats.processed} processed, "
                       f"{self.stats.skipped} skipped, {self.stats.failed} failed")
            
            return self.stats
            
        except Exception as e:
            self.stats.end_time = datetime.now()
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            raise
    
    def _load_documents(self) -> List[Path]:
        """
        Find all HTML files in source directory (don't parse yet).
        
        Returns:
            List of HTML file paths
            
        Raises:
            PipelineError: If loading fails
        """
        try:
            # Convert source_dir string to Path object
            source_path = Path(self.config.source_dir)
            
            if not source_path.exists():
                raise FileNotFoundError(f"Directory not found: {source_path}")
            
            if not source_path.is_dir():
                raise ValueError(f"Not a directory: {source_path}")
            
            # Find all HTML files
            html_files = list(source_path.glob("*.html"))
            
            if not html_files:
                raise ValueError(f"No HTML files found in {source_path}")
            
            logger.info(f"Found {len(html_files)} HTML files in {source_path}")
            return html_files
            
        except Exception as e:
            raise PipelineError(f"Failed to load documents: {e}") from e
    
    def _process_document(self, doc: ParsedDocument) -> DocumentProcessingResult:
        """
        Process a single document through the pipeline.
        
        Args:
            doc: Document to process
            
        Returns:
            Processing result with statistics
        """
        start_time = time.time()
        
        try:
            # Check if already processed (hash-based idempotency)
            if self.config.skip_processed and not self.config.dry_run:
                if self._document_already_processed(doc):
                    return DocumentProcessingResult(
                        document_id=doc.doc_id,
                        success=True,
                        skipped=True,
                        skip_reason="Already processed (hash match)",
                        processing_time=time.time() - start_time
                    )
            
            # Extract entities via LLM
            extraction_result = self._extract_entities(doc)
            
            if not extraction_result.success:
                return DocumentProcessingResult(
                    document_id=doc.doc_id,
                    success=False,
                    error=extraction_result.error or "Extraction failed",
                    processing_time=time.time() - start_time
                )
            
            # Run before_store hooks
            entities = extraction_result.entities
            relationships = extraction_result.relationships  # Extract relationships
            if self.hook_registry.before_store_hooks:
                entities = self.hook_registry.run_before_store(
                    doc,
                    entities,
                    self.graph_client,
                    self.interactive_session  # Pass interactive session to hooks
                )
            
            # Ingest into graph (unless dry run)
            entities_created = 0
            relationships_created = 0
            
            if not self.config.dry_run:
                entities_created, relationships_created = self._ingest_to_graph(
                    doc,
                    entities,
                    relationships  # Pass relationships to ingestion
                )
                
                # Track entities for after_batch hooks
                self.batch_entities.extend(entities)
            else:
                logger.debug(f"Dry run: Would have stored {len(entities)} entities and {len(relationships)} relationships from {doc.doc_id}")
            
            return DocumentProcessingResult(
                document_id=doc.doc_id,
                success=True,
                entities_found=len(entities),
                relationships_created=relationships_created,
                processing_time=time.time() - start_time
            )
            
        except Exception as e:
            logger.error(f"Error processing document {doc.doc_id}: {e}", exc_info=True)
            return DocumentProcessingResult(
                document_id=doc.doc_id,
                success=False,
                error=str(e),
                processing_time=time.time() - start_time
            )
    
    def _document_already_processed(self, doc: ParsedDocument) -> bool:
        """
        Check if document has already been processed based on content hash.
        
        Args:
            doc: Document to check
            
        Returns:
            True if document with same hash exists in graph
        """
        try:
            return self.document_repo.document_hash_exists(
                self.config.namespace,
                doc.content_hash
            )
        except GraphError as e:
            logger.warning(f"Error checking document hash: {e}")
            return False
    
    def _extract_entities(self, doc: ParsedDocument):
        """
        Extract entities from document using LLM.
        
        Args:
            doc: Document to extract entities from
            
        Returns:
            ExtractionResult from the LLM
        """
        request = ExtractionRequest(
            content=doc.text,
            entity_types=self.config.entity_types,
            min_confidence=self.config.min_confidence,
            max_tokens=4000  # TODO: Make configurable
        )
        
        logger.debug(f"Extracting entities from {doc.doc_id}")
        return self.extractor.extract(request)
    
    def _ingest_to_graph(
        self,
        doc: ParsedDocument,
        entities: List[ExtractedEntity],
        relationships: List[ExtractedRelationship] = None
    ) -> tuple:
        """
        Ingest document, entities, and relationships into Neo4j.
        
        Args:
            doc: Document to store
            entities: Extracted entities to store
            relationships: Extracted relationships to store (with entity indices)
            
        Returns:
            Tuple of (entities_created, relationships_created)
            
        Raises:
            GraphError: If ingestion fails
        """
        namespace = self.config.namespace
        entities_created = 0
        relationships_created = 0
        
        if relationships is None:
            relationships = []
        
        try:
            # Create/update document (correct parameter order)
            self.document_repo.create_document(
                namespace=namespace,
                doc_id=doc.doc_id,
                source_path=doc.source_file,
                content_hash=doc.content_hash,
                title=doc.title  # metadata
            )
            logger.debug(f"Created/updated document {doc.doc_id}")
            
            # Create/update entities and links
            for entity in entities:
                # Try to create entity (it's OK if it already exists)
                try:
                    self.entity_repo.create_entity(
                        namespace=namespace,
                        entity_type=entity.entity_type,
                        name=entity.name,
                        **entity.properties  # Spread properties as kwargs (entity_repo wraps them)
                    )
                    entities_created += 1
                    logger.debug(f"Created entity: {entity.entity_type}/{entity.name}")
                except DuplicateEntityError:
                    # Entity already exists - this is normal in a knowledge graph
                    logger.debug(f"Entity already exists: {entity.entity_type}/{entity.name}")
                
                # Link document to entity (MENTIONS relationship)
                self.document_repo.add_mention(
                    namespace=namespace,
                    doc_id=doc.doc_id,
                    entity_type=entity.entity_type,
                    entity_name=entity.name,
                    confidence=entity.confidence
                )
                relationships_created += 1
            
            logger.debug(f"Ingested {len(entities)} entities from {doc.doc_id}")
            
            # Create entity-to-entity relationships (resolve indices AFTER hooks have run)
            entity_relationships_created = 0
            for relation in relationships:
                try:
                    # Resolve indices to entities
                    from_entity = entities[relation.from_index]
                    to_entity = entities[relation.to_index]
                    
                    # Verify both entities exist in graph
                    from_entity_data = self.entity_repo.get_entity(
                        namespace=namespace,
                        entity_type=from_entity.entity_type,
                        name=from_entity.name
                    )
                    
                    to_entity_data = self.entity_repo.get_entity(
                        namespace=namespace,
                        entity_type=to_entity.entity_type,
                        name=to_entity.name
                    )
                    
                    if not from_entity_data or not to_entity_data:
                        logger.warning(
                            f"Skipping relationship {relation.relation_type}: "
                            f"entity not found in graph "
                            f"({from_entity.entity_type}/{from_entity.name} -> "
                            f"{to_entity.entity_type}/{to_entity.name})"
                        )
                        continue
                    
                    # Create relationship using resolved entity names
                    self.entity_repo.create_relationship(
                        namespace=namespace,
                        from_entity_type=from_entity.entity_type,
                        from_entity_name=from_entity_data['name'],
                        to_entity_type=to_entity.entity_type,
                        to_entity_name=to_entity_data['name'],
                        rel_type=relation.relation_type,
                        confidence=relation.confidence,
                        **relation.properties
                    )
                    entity_relationships_created += 1
                    logger.debug(
                        f"Created relationship: {from_entity.entity_type}/{from_entity.name} "
                        f"-[{relation.relation_type}]-> {to_entity.entity_type}/{to_entity.name}"
                    )
                    
                except IndexError as e:
                    logger.warning(
                        f"Skipping relationship {relation.relation_type}: "
                        f"invalid entity index ({e})"
                    )
                except GraphError as e:
                    logger.warning(
                        f"Failed to create relationship {relation.relation_type}: {e}"
                    )
            
            if entity_relationships_created > 0:
                logger.debug(f"Created {entity_relationships_created} entity relationships from {doc.doc_id}")
            
        except GraphError as e:
            logger.error(f"Graph ingestion failed for {doc.doc_id}: {e}")
            raise
        
        return entities_created, relationships_created + entity_relationships_created
    
    def _update_statistics(self, result: DocumentProcessingResult):
        """
        Update pipeline statistics based on document processing result.
        
        Args:
            result: Processing result to incorporate into stats
        """
        if result.skipped:
            self.stats.skipped += 1
        elif result.success:
            self.stats.processed += 1
            self.stats.total_entities += result.entities_found
            self.stats.total_relationships += result.relationships_created
        else:
            self.stats.failed += 1
            if result.error:
                error_msg = f"{result.document_id}: {result.error}"
                self.stats.errors.append(error_msg)
    
    def _log_progress(self, result: DocumentProcessingResult):
        """
        Log processing progress with percentage complete.
        
        Args:
            result: Processing result to log
        """
        progress = self.stats.processed + self.stats.skipped + self.stats.failed
        total = self.stats.total_documents
        percentage = (progress / total * 100) if total > 0 else 0
        
        if result.skipped:
            logger.info(
                f"[{progress}/{total} {percentage:.1f}%] "
                f"SKIPPED {result.document_id}: {result.skip_reason}"
            )
        elif result.success:
            logger.info(
                f"[{progress}/{total} {percentage:.1f}%] "
                f"PROCESSED {result.document_id}: "
                f"{result.entities_found} entities in {result.processing_time:.2f}s"
            )
        else:
            logger.error(
                f"[{progress}/{total} {percentage:.1f}%] "
                f"FAILED {result.document_id}: {result.error}"
            )
