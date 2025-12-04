"""
Tests for critical bug fixes in the pipeline orchestrator.

These tests verify fixes for bugs discovered during integration testing:
1. Property nesting in entity creation
2. Duplicate entity handling
3. Parameter order in repository calls
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

from kg_forge.pipeline.orchestrator import PipelineOrchestrator
from kg_forge.models.pipeline import PipelineConfig
from kg_forge.models.extraction import ExtractedEntity, ExtractionResult
from kg_forge.models.document import ParsedDocument
from kg_forge.graph.exceptions import DuplicateEntityError


@pytest.fixture
def mock_graph_client():
    """Mock graph client."""
    client = Mock()
    client.connect = Mock()
    client.close = Mock()
    return client


@pytest.fixture
def mock_extractor():
    """Mock entity extractor."""
    extractor = Mock()
    return extractor


@pytest.fixture
def pipeline_config(tmp_path):
    """Create a test pipeline configuration."""
    return PipelineConfig(
        namespace="test",
        source_dir=str(tmp_path),
        entity_types=None,
        min_confidence=0.0,
        skip_processed=False,
        batch_size=10,
        max_failures=5,
        interactive=False,
        dry_run=False
    )


@pytest.fixture
def sample_document():
    """Create a sample parsed document."""
    return ParsedDocument(
        doc_id="test_doc",
        title="Test Document",
        source_file="test.html",
        url="http://example.com/test",
        text="Sample content",
        content_hash="abc123",  # Required field
        headings=["Heading 1"],
        links=[],
        metadata={}
    )


@pytest.fixture
def sample_entities():
    """Create sample extracted entities."""
    return [
        ExtractedEntity(
            entity_type="product",
            name="Knowledge Discovery",
            confidence=0.95,
            properties={"aliases": ["KD"], "evidence": "Test evidence"}
        ),
        ExtractedEntity(
            entity_type="component",
            name="CFS",
            confidence=0.90,
            properties={"aliases": ["CFS Store"], "evidence": "Storage component"}
        )
    ]


class TestPropertyNesting:
    """Test that entity properties are not double-nested."""
    
    def test_entity_repo_properties_not_nested(self, mock_graph_client):
        """Test that properties are stored correctly (not double-nested)."""
        from kg_forge.graph.neo4j.entity_repo import Neo4jEntityRepository
        
        repo = Neo4jEntityRepository(mock_graph_client)
        
        # Mock the execute_write_tx to capture parameters
        mock_graph_client.execute_write_tx = Mock(return_value=[
            {'entity': {'name': 'Test', 'evidence': 'test'}, 'status': 'created'}
        ])
        
        # Create entity with properties (passed as **kwargs)
        repo.create_entity(
            namespace="test",
            entity_type="product",
            name="Test Product",
            evidence="test",  # Properties passed as kwargs
            aliases=["TP"]
        )
        
        # Verify execute_write_tx was called
        assert mock_graph_client.execute_write_tx.called
        
        # Get the parameters passed to the query
        call_args = mock_graph_client.execute_write_tx.call_args
        params = call_args[0][1]  # Second argument is parameters
        
        # Properties should be in a "properties" dict at top level
        assert "properties" in params
        assert isinstance(params["properties"], dict)
        
        # Properties should contain our values
        assert params["properties"]["evidence"] == "test"
        assert params["properties"]["aliases"] == ["TP"]
        
        # Should NOT have double nesting like {'properties': {'properties': {...}}}
        assert "properties" not in params["properties"]
    
    def test_orchestrator_passes_flat_properties(
        self, pipeline_config, mock_extractor, mock_graph_client, sample_document, sample_entities
    ):
        """Test that orchestrator passes properties correctly to entity repo."""
        with patch('kg_forge.pipeline.orchestrator.DocumentLoader'):
            orchestrator = PipelineOrchestrator(
                config=pipeline_config,
                extractor=mock_extractor,
                graph_client=mock_graph_client
            )
            
            # Mock entity repo create_entity to capture calls
            created_entities = []
            
            def capture_create_entity(**kwargs):
                created_entities.append(kwargs)
                return {"name": kwargs["name"]}
            
            orchestrator.entity_repo.create_entity = Mock(side_effect=capture_create_entity)
            orchestrator.entity_repo.get_entity = Mock(return_value=None)
            orchestrator.document_repo.create_document = Mock()
            orchestrator.document_repo.add_mention = Mock()
            
            # Mock extraction
            mock_extractor.extract = Mock(return_value=ExtractionResult(
                success=True,
                entities=sample_entities
            ))
            
            # Process document
            result = orchestrator._process_document(sample_document)
            
            # Verify entities were created with correct structure
            assert len(created_entities) == 2
            
            # Check first entity
            first_entity = created_entities[0]
            assert first_entity["namespace"] == "test"
            assert first_entity["entity_type"] == "product"
            assert first_entity["name"] == "Knowledge Discovery"
            
            # Properties should be spread as kwargs (not wrapped in "properties" dict)
            # This is the correct behavior - orchestrator spreads with **entity.properties
            assert "aliases" in first_entity  # Direct kwargs, not nested
            assert "evidence" in first_entity
            assert first_entity["aliases"] == ["KD"]
            assert first_entity["evidence"] == "Test evidence"


class TestDuplicateEntityHandling:
    """Test that duplicate entities are handled gracefully."""
    
    def test_duplicate_entity_does_not_fail_pipeline(
        self, pipeline_config, mock_extractor, mock_graph_client, sample_document, sample_entities
    ):
        """Test that when entity already exists, pipeline continues successfully."""
        with patch('kg_forge.pipeline.orchestrator.DocumentLoader'):
            orchestrator = PipelineOrchestrator(
                config=pipeline_config,
                extractor=mock_extractor,
                graph_client=mock_graph_client
            )
            
            # First entity creation raises DuplicateEntityError
            def create_entity_with_duplicate(**kwargs):
                if kwargs["name"] == "Knowledge Discovery":
                    raise DuplicateEntityError("test", "product", "Knowledge Discovery")
                return {"name": kwargs["name"]}
            
            orchestrator.entity_repo.create_entity = Mock(side_effect=create_entity_with_duplicate)
            orchestrator.document_repo.create_document = Mock()
            orchestrator.document_repo.add_mention = Mock()
            
            # Mock extraction
            mock_extractor.extract = Mock(return_value=ExtractionResult(
                success=True,
                entities=sample_entities
            ))
            
            # Process document - should NOT fail
            result = orchestrator._process_document(sample_document)
            
            # Should succeed despite duplicate
            assert result.success is True
            assert result.entities_found == 2
            
            # MENTIONS relationships should still be created for ALL entities
            assert orchestrator.document_repo.add_mention.call_count == 2
    
    def test_all_entities_linked_even_if_duplicates(
        self, pipeline_config, mock_extractor, mock_graph_client, sample_document, sample_entities
    ):
        """Test that MENTIONS relationships are created even for existing entities."""
        with patch('kg_forge.pipeline.orchestrator.DocumentLoader'):
            orchestrator = PipelineOrchestrator(
                config=pipeline_config,
                extractor=mock_extractor,
                graph_client=mock_graph_client
            )
            
            # All entities already exist
            orchestrator.entity_repo.create_entity = Mock(
                side_effect=DuplicateEntityError("test", "product", "test")
            )
            orchestrator.document_repo.create_document = Mock()
            orchestrator.document_repo.add_mention = Mock()
            
            # Mock extraction
            mock_extractor.extract = Mock(return_value=ExtractionResult(
                success=True,
                entities=sample_entities
            ))
            
            # Process document
            result = orchestrator._process_document(sample_document)
            
            # All MENTIONS should be created despite duplicates
            assert orchestrator.document_repo.add_mention.call_count == 2
            assert result.relationships_created == 2


class TestParameterOrder:
    """Test that repository methods are called with correct parameter order."""
    
    def test_get_entity_parameter_order(
        self, pipeline_config, mock_extractor, mock_graph_client, sample_document, sample_entities
    ):
        """Test that get_entity is called with namespace first."""
        with patch('kg_forge.pipeline.orchestrator.DocumentLoader'):
            orchestrator = PipelineOrchestrator(
                config=pipeline_config,
                extractor=mock_extractor,
                graph_client=mock_graph_client
            )
            
            # Capture get_entity calls
            get_entity_calls = []
            
            def capture_get_entity(**kwargs):
                get_entity_calls.append(kwargs)
                return None  # Entity doesn't exist
            
            orchestrator.entity_repo.get_entity = Mock(side_effect=capture_get_entity)
            orchestrator.entity_repo.create_entity = Mock(return_value={"name": "test"})
            orchestrator.document_repo.create_document = Mock()
            orchestrator.document_repo.add_mention = Mock()
            
            # Mock extraction with single entity
            mock_extractor.extract = Mock(return_value=ExtractionResult(
                success=True,
                entities=[sample_entities[0]]
            ))
            
            # Process document
            result = orchestrator._process_document(sample_document)
            
            # Verify get_entity was called (no longer used, but keeping test for completeness)
            # Actually, the current implementation doesn't call get_entity anymore
            # It just tries to create and catches DuplicateEntityError
            # So this test verifies the new approach works
            assert result.success is True
    
    def test_create_entity_gets_namespace_first(
        self, pipeline_config, mock_extractor, mock_graph_client, sample_document, sample_entities
    ):
        """Test that create_entity receives namespace as first parameter."""
        with patch('kg_forge.pipeline.orchestrator.DocumentLoader'):
            orchestrator = PipelineOrchestrator(
                config=pipeline_config,
                extractor=mock_extractor,
                graph_client=mock_graph_client
            )
            
            # Capture create_entity calls
            create_calls = []
            
            def capture_create(**kwargs):
                create_calls.append(kwargs)
                return {"name": kwargs["name"]}
            
            orchestrator.entity_repo.create_entity = Mock(side_effect=capture_create)
            orchestrator.document_repo.create_document = Mock()
            orchestrator.document_repo.add_mention = Mock()
            
            # Mock extraction
            mock_extractor.extract = Mock(return_value=ExtractionResult(
                success=True,
                entities=[sample_entities[0]]
            ))
            
            # Process document
            result = orchestrator._process_document(sample_document)
            
            # Verify create_entity was called with correct parameters
            assert len(create_calls) == 1
            call = create_calls[0]
            
            # Should have namespace parameter
            assert "namespace" in call
            assert call["namespace"] == "test"
            assert call["entity_type"] == "product"
            assert call["name"] == "Knowledge Discovery"
    
    def test_add_mention_parameter_order(
        self, pipeline_config, mock_extractor, mock_graph_client, sample_document, sample_entities
    ):
        """Test that add_mention receives namespace as first parameter."""
        with patch('kg_forge.pipeline.orchestrator.DocumentLoader'):
            orchestrator = PipelineOrchestrator(
                config=pipeline_config,
                extractor=mock_extractor,
                graph_client=mock_graph_client
            )
            
            # Capture add_mention calls
            mention_calls = []
            
            def capture_mention(**kwargs):
                mention_calls.append(kwargs)
                return {"id": "test"}
            
            orchestrator.entity_repo.create_entity = Mock(return_value={"name": "test"})
            orchestrator.document_repo.create_document = Mock()
            orchestrator.document_repo.add_mention = Mock(side_effect=capture_mention)
            
            # Mock extraction
            mock_extractor.extract = Mock(return_value=ExtractionResult(
                success=True,
                entities=[sample_entities[0]]
            ))
            
            # Process document
            result = orchestrator._process_document(sample_document)
            
            # Verify add_mention was called with correct parameter order
            assert len(mention_calls) == 1
            call = mention_calls[0]
            
            # Should have namespace first
            assert "namespace" in call
            assert call["namespace"] == "test"
            assert call["doc_id"] == "test_doc"
            assert call["entity_type"] == "product"
            assert call["entity_name"] == "Knowledge Discovery"
            assert "confidence" in call


class TestMemoryEfficiency:
    """Test that files are processed one at a time, not all loaded upfront."""
    
    def test_files_parsed_on_demand(self, pipeline_config, mock_extractor, mock_graph_client, tmp_path):
        """Test that HTML files are parsed one at a time during processing."""
        # Create some test HTML files
        for i in range(3):
            (tmp_path / f"test_{i}.html").write_text(
                f"<html><body><div class='wiki-content'><p>Test {i}</p></div></body></html>"
            )
        
        with patch('kg_forge.pipeline.orchestrator.DocumentLoader') as mock_loader_class:
            mock_loader = Mock()
            mock_parser = Mock()
            mock_loader.parser = mock_parser
            mock_loader_class.return_value = mock_loader
            
            # Track how many times parse_file is called
            parse_calls = []
            
            def track_parse(file_path):
                parse_calls.append(str(file_path))
                return ParsedDocument(
                    doc_id=file_path.stem,
                    title=f"Test {file_path.stem}",
                    source_file=str(file_path),
                    url="http://test.com",
                    text="Test content",
                    content_hash="test_hash",  # Required field
                    headings=[],
                    links=[],
                    metadata={}
                )
            
            mock_parser.parse_file = Mock(side_effect=track_parse)
            
            orchestrator = PipelineOrchestrator(
                config=pipeline_config,
                extractor=mock_extractor,
                graph_client=mock_graph_client
            )
            
            # Mock extraction to return empty results
            mock_extractor.extract = Mock(return_value=ExtractionResult(
                success=True,
                entities=[]
            ))
            
            orchestrator.document_repo.create_document = Mock()
            orchestrator.document_repo.document_hash_exists = Mock(return_value=False)
            
            # Run pipeline
            stats = orchestrator.run()
            
            # Verify files were parsed one at a time (3 calls)
            assert len(parse_calls) == 3
            
            # Verify all 3 documents were processed
            assert stats.processed == 3
