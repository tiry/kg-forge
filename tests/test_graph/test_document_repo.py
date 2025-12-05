"""Unit tests for Neo4j document repository."""

import pytest
from unittest.mock import Mock
from kg_forge.graph.neo4j.document_repo import Neo4jDocumentRepository
from kg_forge.models.document import ParsedDocument


@pytest.fixture
def doc_repo():
    """Create document repository with mocked client."""
    mock_client = Mock()
    return Neo4jDocumentRepository(mock_client), mock_client


@pytest.fixture
def sample_document():
    """Sample document for testing."""
    return ParsedDocument(
        doc_id="test-doc-123",
        title="Test Document",
        text="Test content",
        source_file="doc.html",
        content_hash="abc123"
    )


class TestDocumentExists:
    """Test document existence checks."""
    
    def test_document_exists_by_id_true(self, doc_repo):
        """Test checking if document exists by ID."""
        repo, client = doc_repo
        client.execute_query.return_value = [{'count': 1}]
        
        result = repo.document_exists("default", "test-doc-123")
        
        assert result is True
    
    def test_document_exists_by_id_false(self, doc_repo):
        """Test document doesn't exist."""
        repo, client = doc_repo
        client.execute_query.return_value = [{'count': 0}]
        
        result = repo.document_exists("default", "nonexistent")
        
        assert result is False
    
    def test_document_hash_exists_true(self, doc_repo):
        """Test checking if document exists by hash."""
        repo, client = doc_repo
        client.execute_query.return_value = [{'count': 1}]
        
        result = repo.document_hash_exists("default", "abc123")
        
        assert result is True


class TestCreateDocument:
    """Test document creation."""
    
    def test_create_document_success(self, doc_repo, sample_document):
        """Test successful document creation."""
        repo, client = doc_repo
        client.execute_write_tx.return_value = [{'d': {
            'doc_id': 'test-doc-123',
            'title': 'Test Document',
            'namespace': 'default'
        }}]
        
        result = repo.create_document(
            namespace="default",
            doc_id=sample_document.doc_id,
            source_path=sample_document.source_file,
            content_hash=sample_document.content_hash,
            title=sample_document.title
        )
        
        assert result is not None
        assert result['doc_id'] == 'test-doc-123'
    
    def test_create_document_with_error(self, doc_repo, sample_document):
        """Test document creation with error."""
        repo, client = doc_repo
        client.execute_write_tx.side_effect = Exception("DB error")
        
        from kg_forge.graph.exceptions import GraphError
        with pytest.raises(GraphError):
            repo.create_document(
                namespace="default",
                doc_id=sample_document.doc_id,
                source_path=sample_document.source_file,
                content_hash=sample_document.content_hash
            )


class TestGetDocument:
    """Test document retrieval."""
    
    def test_get_document_by_id_success(self, doc_repo):
        """Test getting document by ID."""
        repo, client = doc_repo
        client.execute_query.return_value = [{'d': {
            'doc_id': 'test-doc-123',
            'title': 'Test Document'
        }}]
        
        result = repo.get_document("default", "test-doc-123")
        
        assert result is not None
        assert result['doc_id'] == 'test-doc-123'
    
    def test_get_document_not_found(self, doc_repo):
        """Test getting non-existent document."""
        repo, client = doc_repo
        client.execute_query.return_value = []
        
        result = repo.get_document("default", "nonexistent")
        
        assert result is None


class TestAddMention:
    """Test adding entity mentions to documents."""
    
    def test_add_mention_success(self, doc_repo):
        """Test successfully adding mention."""
        repo, client = doc_repo
        client.execute_write_tx.return_value = [{'r': {'confidence': 0.9}}]
        
        result = repo.add_mention(
            "default", "test-doc-123",
            "Product", "Test Product",
            confidence=0.9
        )
        
        assert result is not None
        assert result['confidence'] == 0.9
    
    def test_add_mention_with_properties(self, doc_repo):
        """Test adding mention with extra properties."""
        repo, client = doc_repo
        client.execute_write_tx.return_value = [{'r': {
            'confidence': 0.95,
            'context': 'test context'
        }}]
        
        result = repo.add_mention(
            "default", "test-doc-123",
            "Product", "Test Product",
            confidence=0.95,
            context="test context"
        )
        
        assert result['context'] == 'test context'


class TestDocumentQueries:
    """Test document query operations."""
    
    def test_get_document_entities(self, doc_repo):
        """Test getting entities mentioned in document."""
        repo, client = doc_repo
        client.execute_query.return_value = [
            {
                'e': {'name': 'Entity 1', 'entity_type': 'Product'},
                'r': {'confidence': 0.9}
            },
            {
                'e': {'name': 'Entity 2', 'entity_type': 'Team'},
                'r': {'confidence': 0.8}
            }
        ]
        
        result = repo.get_document_entities("default", "test-doc-123")
        
        assert len(result) == 2
        assert result[0]['name'] == 'Entity 1'
        assert 'mention_properties' in result[0]
    
    def test_find_related_documents(self, doc_repo):
        """Test finding documents with shared entities."""
        repo, client = doc_repo
        client.execute_query.return_value = [
            {
                'd': {'doc_id': 'related-1', 'title': 'Related Doc 1'},
                'r': {'confidence': 0.9}
            },
            {
                'd': {'doc_id': 'related-2', 'title': 'Related Doc 2'},
                'r': {'confidence': 0.8}
            }
        ]
        
        result = repo.find_related_documents(
            namespace="default",
            entity_type="Product",
            entity_name="Test Product",
            limit=10
        )
        
        assert len(result) == 2
        assert result[0]['doc_id'] == 'related-1'
        assert 'mention_properties' in result[0]


class TestErrorHandling:
    """Test error handling."""
    
    def test_document_exists_handles_exception(self, doc_repo):
        """Test that document_exists handles exceptions."""
        repo, client = doc_repo
        client.execute_query.side_effect = Exception("DB error")
        
        result = repo.document_exists("default", "test-doc")
        
        assert result is False
    
    def test_get_document_handles_exception(self, doc_repo):
        """Test that get_document handles exceptions."""
        repo, client = doc_repo
        client.execute_query.side_effect = Exception("DB error")
        
        result = repo.get_document("default", "test-doc")
        
        assert result is None
