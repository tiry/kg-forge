"""
Core ingest pipeline orchestrating HTML processing, LLM extraction, and Neo4j storage.
"""

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Set

from kg_forge.config.settings import Settings, get_settings
from kg_forge.entities.definitions import EntityDefinitionLoader
from kg_forge.graph.neo4j_client import Neo4jClient
from kg_forge.llm.bedrock_extractor import BedrockLLMExtractor
from kg_forge.llm.fake_extractor import FakeLLMExtractor
from kg_forge.llm.prompt_builder import PromptBuilder
from kg_forge.llm.exceptions import LLMError, ParseError, ValidationError, ExtractionAbortError
from kg_forge.models.document import ParsedDocument
from kg_forge.parsers.document_loader import DocumentLoader
from kg_forge.utils.hashing import compute_content_hash
from kg_forge.utils.interactive import InteractiveSession
from kg_forge.ontology_manager import get_ontology_manager

from .filesystem import FileDiscovery
from .hooks import HookRegistry, EntityRecord, get_global_registry
from .metrics import IngestMetrics


logger = logging.getLogger(__name__)


class IngestPipeline:
    """
    End-to-end ingest pipeline that orchestrates:
    1. HTML file discovery and parsing (Step 2)
    2. LLM entity extraction (Step 5) 
    3. Neo4j storage and relationship creation (Step 4)
    4. Hook execution for custom processing
    """
    
    def __init__(self, 
                 source_path: Path,
                 namespace: Optional[str] = None,
                 dry_run: bool = False,
                 refresh: bool = False,
                 interactive: bool = False,
                 prompt_template: Optional[Path] = None,
                 model: Optional[str] = None,
                 max_docs: Optional[int] = None,
                 fake_llm: bool = False,
                 config: Optional[Settings] = None,
                 hook_registry: Optional[HookRegistry] = None):
        """
        Initialize ingest pipeline.
        
        Args:
            source_path: Root directory containing HTML files
            namespace: Namespace for this ingest run
            dry_run: Run without writing to Neo4j
            refresh: Reprocess all documents ignoring content hash
            interactive: Enable interactive mode for hooks
            prompt_template: Override prompt template file
            model: Override LLM model name
            max_docs: Limit number of documents processed
            fake_llm: Use fake LLM for testing
            config: Application configuration (uses default if None)
            hook_registry: Hook registry (uses global if None)
        """
        self.source_path = Path(source_path).resolve()
        self.dry_run = dry_run
        self.refresh = refresh
        self.interactive_mode = interactive
        self.max_docs = max_docs
        self.fake_llm = fake_llm
        
        # Load configuration
        self.config = config or get_settings()
        self.namespace = namespace or self.config.app.default_namespace
        
        # Initialize components
        self.file_discovery = FileDiscovery(self.source_path)
        self.document_loader = DocumentLoader()
        
        # Initialize ontology manager and set active pack
        self.ontology_manager = get_ontology_manager()
        if self.config.app.ontology_pack:
            try:
                self.ontology_manager.set_active_ontology(self.config.app.ontology_pack)
                logger.info(f"Using ontology pack: {self.config.app.ontology_pack}")
            except Exception as e:
                logger.warning(f"Failed to activate configured ontology pack '{self.config.app.ontology_pack}': {e}")
        
        # Fallback to legacy entity loading if no ontology pack is available
        active_pack = self.ontology_manager.get_active_ontology()
        if active_pack:
            # Use ontology pack
            self.entity_definitions = active_pack.get_entity_definitions()
            self.prompt_builder = PromptBuilder(ontology_id=active_pack.info.id)
            logger.info(f"Loaded {len(self.entity_definitions)} entity definitions from ontology pack: {active_pack.info.id}")
        else:
            # Legacy fallback
            logger.warning("No ontology pack available, falling back to legacy entity loading")
            self.entity_loader = EntityDefinitionLoader()
            entities_dir = Path(self.config.app.entities_extract_dir)
            self.template_file = prompt_template or (entities_dir / "prompt_template.md")
            self.entities_dir = entities_dir
            self.entity_definitions = self.entity_loader.load_entity_definitions(entities_dir)
            self.prompt_builder = PromptBuilder(self.entity_loader)
            logger.info(f"Loaded {len(self.entity_definitions)} entity definitions from legacy path: {entities_dir}")
        
        # Initialize LLM client
        ontology_id = active_pack.info.id if active_pack else None
        if fake_llm:
            self.llm_client = FakeLLMExtractor(ontology_id=ontology_id)
        else:
            model_name = model or self.config.aws.bedrock_model_name
            self.llm_client = BedrockLLMExtractor(
                model_name=model_name,
                region=self.config.aws.default_region,
                access_key_id=self.config.aws.access_key_id,
                secret_access_key=self.config.aws.secret_access_key,
                session_token=self.config.aws.session_token,
                profile_name=self.config.aws.profile_name,
                max_tokens=self.config.aws.bedrock_max_tokens,
                temperature=self.config.aws.bedrock_temperature
            )
        
        # Initialize Neo4j client
        self.neo4j_client = Neo4jClient(self.config)
        
        # Set up hooks and session
        self.hook_registry = hook_registry or get_global_registry()
        self.interactive_session = InteractiveSession(enabled=interactive) if interactive else None
        
        # Initialize metrics and state
        self.metrics = IngestMetrics()
        self.processed_entities: List[EntityRecord] = []
        
        logger.info(f"Initialized IngestPipeline: source={source_path}, namespace={self.namespace}, "
                   f"dry_run={dry_run}, refresh={refresh}, fake_llm={fake_llm}")
    
    def run(self) -> IngestMetrics:
        """
        Execute the complete ingest pipeline.
        
        Returns:
            IngestMetrics object with processing statistics
            
        Raises:
            ExtractionAbortError: If consecutive failure threshold exceeded
            Exception: For critical configuration or connection errors
        """
        logger.info("Starting ingest pipeline")
        
        try:
            # Validate configuration and connections
            self._validate_setup()
            
            # Discover files
            html_files = list(self.file_discovery.discover_html_files())
            self.metrics.files_discovered = len(html_files)
            
            if self.max_docs:
                html_files = html_files[:self.max_docs]
                logger.info(f"Limited processing to {len(html_files)} documents")
            
            logger.info(f"Discovered {len(html_files)} HTML files to process")
            
            if not html_files:
                logger.warning("No HTML files found in source directory")
                self.metrics.finalize()
                return self.metrics
            
            # Process each document
            for i, file_path in enumerate(html_files, 1):
                logger.info(f"Processing document {i}/{len(html_files)}: {file_path.name}")
                
                try:
                    self._process_document(file_path)
                    
                    # Check for consecutive failure abort
                    if self.metrics.has_consecutive_failures:
                        raise ExtractionAbortError(
                            f"Exceeded maximum consecutive failures ({self.metrics.consecutive_failures})"
                        )
                        
                except ExtractionAbortError:
                    raise  # Re-raise abort errors
                except Exception as e:
                    logger.error(f"Failed to process {file_path}: {e}")
                    self.metrics.record_doc_failed(str(e))
            
            # Execute batch completion hooks
            if self.processed_entities:
                logger.info(f"Executing batch completion hooks for {len(self.processed_entities)} entities")
                self.hook_registry.execute_after_batch(
                    self.processed_entities, 
                    self.neo4j_client, 
                    self.interactive_session
                )
            
            self.metrics.finalize()
            logger.info(f"Ingest pipeline completed: {self.metrics}")
            
            return self.metrics
            
        except Exception as e:
            self.metrics.finalize()
            logger.error(f"Ingest pipeline failed: {e}")
            raise
    
    def _validate_setup(self) -> None:
        """Validate configuration and connections."""
        # Check source path
        if not self.source_path.exists():
            raise FileNotFoundError(f"Source path does not exist: {self.source_path}")
        
        # Test Neo4j connection (unless dry run)
        if not self.dry_run:
            try:
                with self.neo4j_client:
                    self.neo4j_client.test_connection()
            except Exception as e:
                raise ConnectionError(f"Neo4j connection failed: {e}")
        
        # Load entity definitions
        entities_dir = Path(self.config.app.entities_extract_dir)
        if not entities_dir.exists():
            raise FileNotFoundError(f"Entity definitions directory not found: {entities_dir}")
    
    def _process_document(self, file_path: Path) -> None:
        """Process a single HTML document through the complete pipeline."""
        doc_id = self.file_discovery.get_doc_id(file_path)
        
        try:
            # Parse HTML to curated document
            start_time = time.time()
            curated_doc = self._parse_html_document(file_path, doc_id)
            
            # Check if document needs processing (content hash comparison)
            content_hash = compute_content_hash(curated_doc)
            
            if not self.refresh and self._should_skip_document(doc_id, content_hash):
                logger.info(f"Skipping {doc_id} (unchanged content hash)")
                self.metrics.record_doc_skipped("unchanged content hash")
                return
            
            # Extract entities using LLM
            llm_start = time.time()
            extraction_result = self._extract_entities(curated_doc)
            self.metrics.add_llm_time(time.time() - llm_start)
            
            # Process hooks before storage
            metadata = {
                'entities': [entity.__dict__ for entity in extraction_result.entities],
                'extraction_time': time.time() - llm_start,
                'doc_id': doc_id,
                'namespace': self.namespace
            }
            
            processed_metadata = self.hook_registry.execute_before_store(
                curated_doc, metadata, self.neo4j_client
            )
            
            # Store in Neo4j
            if not self.dry_run:
                neo4j_start = time.time()
                self._store_document_and_entities(
                    curated_doc, doc_id, content_hash, extraction_result, processed_metadata
                )
                self.metrics.add_neo4j_time(time.time() - neo4j_start)
            else:
                logger.info(f"DRY RUN: Would store document {doc_id} with {len(extraction_result.entities)} entities")
            
            # Record successful processing
            self.metrics.record_doc_processed()
            
            # Track entities for batch hooks
            for entity in extraction_result.entities:
                entity_record = EntityRecord(
                    entity_type=entity.type,
                    name=entity.name,
                    confidence=entity.confidence,
                    doc_id=doc_id,
                    namespace=self.namespace
                )
                entity_record.created_at = datetime.utcnow()
                self.processed_entities.append(entity_record)
            
            logger.info(f"Successfully processed {doc_id}: {len(extraction_result.entities)} entities extracted")
            
        except Exception as e:
            logger.error(f"Error processing document {file_path}: {e}")
            raise
    
    def _parse_html_document(self, file_path: Path, doc_id: str) -> ParsedDocument:
        """Parse HTML file into CuratedDocument."""
        try:
            documents = self.document_loader.load_files([file_path])
            
            if not documents:
                raise ValueError(f"No documents could be loaded from {file_path}")
            
            # Use first document (1 file = 1 document in v1)
            return documents[0]
            
        except Exception as e:
            raise ValueError(f"Failed to parse HTML document {file_path}: {e}")
    
    def _should_skip_document(self, doc_id: str, content_hash: str) -> bool:
        """Check if document should be skipped based on content hash."""
        if self.dry_run:
            return False  # Don't skip in dry run mode
        
        try:
            with self.neo4j_client:
                # Query for existing document
                query = """
                MATCH (d:Doc {namespace: $namespace, doc_id: $doc_id})
                RETURN d.content_hash as content_hash
                """
                
                result = self.neo4j_client.execute_query(
                    query, 
                    {
                        "namespace": self.namespace, 
                        "doc_id": doc_id
                    }
                )
                
                if result and result[0] and result[0]['content_hash'] == content_hash:
                    return True  # Skip - content unchanged
                
        except Exception as e:
            logger.warning(f"Failed to check existing document {doc_id}: {e}")
            # Continue processing on error
        
        return False
    
    def _extract_entities(self, curated_doc: ParsedDocument):
        """Extract entities from document using LLM."""
        try:
            # Build prompt using ontology pack or cached entity definitions
            active_pack = self.ontology_manager.get_active_ontology()
            if active_pack:
                # Use ontology pack for prompt building
                prompt = self.prompt_builder.build_ontology_prompt(curated_doc.text)
            else:
                # Fallback to legacy method
                prompt = self.prompt_builder.build_prompt_with_definitions(
                    curated_doc.text, 
                    self.entity_definitions,
                    self.template_file
                )
            
            # Call LLM for entity extraction
            result = self.llm_client.extract_entities(prompt)
            
            logger.debug(f"Extracted {len(result.entities)} entities from document")
            return result
            
        except (LLMError, ParseError, ValidationError) as e:
            logger.error(f"LLM extraction failed: {e}")
            raise
    
    def _store_document_and_entities(self, curated_doc: ParsedDocument, doc_id: str, 
                                   content_hash: str, extraction_result, metadata: Dict[str, Any]) -> None:
        """Store document and extracted entities in Neo4j."""
        try:
            with self.neo4j_client:
                with self.neo4j_client.session() as session:
                    with session.begin_transaction() as tx:
                        # Store document node
                        self._create_document_node(tx, curated_doc, doc_id, content_hash)
                        
                        # Store entities and relationships
                        entity_ids = []
                        for entity in extraction_result.entities:
                            entity_id = self._create_entity_node(tx, entity)
                            entity_ids.append(entity_id)
                            
                            # Create MENTIONS relationship
                            self._create_mentions_relationship(tx, doc_id, entity_id, entity.confidence)
                        
                        # Create entity-entity relationships based on definitions
                        self._create_entity_relationships(tx, entity_ids)
                        
                        tx.commit()
                        
                        # Update metrics
                        self.metrics.record_entity_created(len(extraction_result.entities))
                        self.metrics.record_mentions_created(len(extraction_result.entities))
                        
        except Exception as e:
            logger.error(f"Failed to store document {doc_id} in Neo4j: {e}")
            raise
    
    def _create_document_node(self, tx, curated_doc: ParsedDocument, doc_id: str, content_hash: str) -> None:
        """Create or update document node in Neo4j."""
        query = """
        MERGE (d:Doc {namespace: $namespace, doc_id: $doc_id})
        SET d.title = $title,
            d.content = $content,
            d.content_hash = $content_hash,
            d.source_path = $source_path,
            d.last_processed_at = datetime()
        RETURN d
        """
        
        tx.run(query,
               namespace=self.namespace,
               doc_id=doc_id,
               title=curated_doc.title or "",
               content=curated_doc.text or "",
               content_hash=content_hash,
               source_path=str(self.source_path))
    
    def _create_entity_node(self, tx, entity) -> str:
        """Create or update entity node in Neo4j."""
        # Normalize entity name for merging
        normalized_name = entity.name.lower().strip()
        
        query = """
        MERGE (e:Entity {namespace: $namespace, entity_type: $entity_type, normalized_name: $normalized_name})
        SET e.name = $name,
            e.confidence = CASE 
                WHEN e.confidence IS NULL OR $confidence > e.confidence 
                THEN $confidence 
                ELSE e.confidence 
            END,
            e.last_seen_at = datetime()
        RETURN e
        """
        
        result = tx.run(query,
                       namespace=self.namespace,
                       entity_type=entity.type,
                       normalized_name=normalized_name,
                       name=entity.name,
                       confidence=entity.confidence)
        
        # Return entity identifier for relationships
        return f"{self.namespace}:{entity.type}:{normalized_name}"
    
    def _create_mentions_relationship(self, tx, doc_id: str, entity_id: str, confidence: float) -> None:
        """Create MENTIONS relationship between document and entity."""
        # Parse entity_id to get components
        namespace, entity_type, normalized_name = entity_id.split(':', 2)
        
        query = """
        MATCH (d:Doc {namespace: $namespace, doc_id: $doc_id})
        MATCH (e:Entity {namespace: $namespace, entity_type: $entity_type, normalized_name: $normalized_name})
        CREATE (d)-[:MENTIONS {confidence: $confidence, created_at: datetime()}]->(e)
        """
        
        tx.run(query,
               namespace=namespace,
               doc_id=doc_id,
               entity_type=entity_type,
               normalized_name=normalized_name,
               confidence=confidence)
    
    def _create_entity_relationships(self, tx, entity_ids: List[str]) -> None:
        """Create entity-entity relationships based on definitions."""
        # This is a placeholder for future relationship inference
        # Based on entity definitions and ontology rules
        
        # For now, we'll implement basic relationship creation
        # Future enhancement point for complex ontology-driven relationships
        relations_created = 0
        
        # Example: Create MENTIONED_TOGETHER relationships for entities in same document
        if len(entity_ids) > 1:
            for i, entity_id_1 in enumerate(entity_ids):
                for entity_id_2 in entity_ids[i+1:]:
                    try:
                        self._create_mentioned_together_relationship(tx, entity_id_1, entity_id_2)
                        relations_created += 1
                    except Exception as e:
                        logger.debug(f"Failed to create relationship {entity_id_1} -> {entity_id_2}: {e}")
        
        if relations_created > 0:
            self.metrics.record_relations_created(relations_created)
    
    def _create_mentioned_together_relationship(self, tx, entity_id_1: str, entity_id_2: str) -> None:
        """Create MENTIONED_TOGETHER relationship between entities."""
        # Parse entity IDs
        namespace_1, type_1, name_1 = entity_id_1.split(':', 2)
        namespace_2, type_2, name_2 = entity_id_2.split(':', 2)
        
        query = """
        MATCH (e1:Entity {namespace: $namespace1, entity_type: $type1, normalized_name: $name1})
        MATCH (e2:Entity {namespace: $namespace2, entity_type: $type2, normalized_name: $name2})
        MERGE (e1)-[r:MENTIONED_TOGETHER]-(e2)
        ON CREATE SET r.created_at = datetime(), r.count = 1
        ON MATCH SET r.count = r.count + 1, r.last_seen_at = datetime()
        """
        
        tx.run(query,
               namespace1=namespace_1, type1=type_1, name1=name_1,
               namespace2=namespace_2, type2=type_2, name2=name_2)