"""Tests for LLM base extractor."""

import pytest
from unittest.mock import Mock, patch
from typing import Dict, Any

from kg_forge.models.extraction import ExtractionRequest, ExtractionResult, ExtractedEntity
from kg_forge.extractors.llm_base import LLMEntityExtractor
from kg_forge.extractors.base import APIError, ParseError


class MockLLMExtractor(LLMEntityExtractor):
    """Mock implementation for testing."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_calls = []
        self.should_fail = False
        self.failure_count = 0
        
    def _call_llm_api(self, prompt: str, max_tokens: int) -> Dict[str, Any]:
        """Mock API call."""
        self.api_calls.append({"prompt": prompt, "max_tokens": max_tokens})
        
        if self.should_fail:
            self.failure_count += 1
            raise Exception("Mock API error")
        
        # Return valid JSON response
        return {
            "text": '''
            {
                "entities": [
                    {
                        "type": "test_entity",
                        "name": "Test Entity",
                        "confidence": 0.95
                    }
                ]
            }
            ''',
            "tokens": 100
        }


class TestLLMEntityExtractorInitialization:
    """Test LLM extractor initialization."""
    
    def test_initialization_with_defaults(self):
        """Test extractor initializes with default values."""
        extractor = MockLLMExtractor(model_name="test-model")
        
        assert extractor.model_name == "test-model"
        assert extractor.max_retries == 3  # Default is now 3 for better reliability
        assert extractor.max_consecutive_failures == 10
        assert extractor._consecutive_failures == 0
        assert extractor.prompt_builder is not None
        assert extractor.parser is not None
    
    def test_initialization_with_custom_values(self):
        """Test extractor initializes with custom values."""
        extractor = MockLLMExtractor(
            model_name="custom-model",
            max_retries=3,
            max_consecutive_failures=5
        )
        
        assert extractor.model_name == "custom-model"
        assert extractor.max_retries == 3
        assert extractor.max_consecutive_failures == 5
    
    def test_initialization_creates_prompt_builder(self):
        """Test that prompt builder is created."""
        extractor = MockLLMExtractor(
            model_name="test",
            entities_dir="entities_extract"
        )
        
        assert extractor.prompt_builder is not None
        # Verify it can load entity types
        types = extractor.prompt_builder.get_loaded_types()
        assert len(types) > 0


class TestLLMEntityExtractorExtraction:
    """Test extraction functionality."""
    
    def test_successful_extraction(self):
        """Test successful entity extraction."""
        extractor = MockLLMExtractor(model_name="test-model")
        request = ExtractionRequest(content="Test content", max_tokens=1000)
        
        result = extractor.extract(request)
        
        assert result.success is True
        assert len(result.entities) == 1
        assert result.entities[0].name == "Test Entity"
        assert result.tokens_used == 100
        assert result.model_name == "test-model"
        assert len(extractor.api_calls) == 1
    
    def test_extraction_filters_by_confidence(self):
        """Test that low confidence entities are filtered."""
        extractor = MockLLMExtractor(model_name="test-model")
        request = ExtractionRequest(
            content="Test content",
            max_tokens=1000,
            min_confidence=0.99  # Higher than 0.95 in mock response
        )
        
        result = extractor.extract(request)
        
        assert result.success is True
        assert len(result.entities) == 0  # Filtered out
    
    def test_extraction_keeps_high_confidence(self):
        """Test that high confidence entities are kept."""
        extractor = MockLLMExtractor(model_name="test-model")
        request = ExtractionRequest(
            content="Test content",
            max_tokens=1000,
            min_confidence=0.90  # Lower than 0.95 in mock response
        )
        
        result = extractor.extract(request)
        
        assert result.success is True
        assert len(result.entities) == 1
    
    def test_extraction_with_entity_types_filter(self):
        """Test extraction with entity type filtering."""
        extractor = MockLLMExtractor(model_name="test-model")
        request = ExtractionRequest(
            content="Test content",
            entity_types=["product"],
            max_tokens=1000
        )
        
        result = extractor.extract(request)
        
        assert result.success is True
        # Verify prompt was built with filtered types
        assert len(extractor.api_calls) == 1


class TestLLMEntityExtractorRetryLogic:
    """Test retry and failure handling."""
    
    def test_retry_on_failure(self):
        """Test that failed calls are retried."""
        extractor = MockLLMExtractor(model_name="test-model", max_retries=2)
        
        # Use a retryable error
        def failing_call(prompt, max_tokens):
            extractor.api_calls.append({"prompt": prompt, "max_tokens": max_tokens})
            raise Exception("Rate limit exceeded")  # Retryable error
        
        extractor._call_llm_api = failing_call
        
        request = ExtractionRequest(content="Test content", max_tokens=1000)
        result = extractor.extract(request)
        
        assert result.success is False
        assert "API error" in result.error
        # Should have tried initial + 2 retries = 3 attempts
        assert len(extractor.api_calls) == 3
    
    def test_retry_with_recovery(self):
        """Test retry logic recovers after transient failure."""
        extractor = MockLLMExtractor(model_name="test-model", max_retries=2)
        
        # Fail once with retryable error, then succeed
        call_count = [0]
        original_call = extractor._call_llm_api
        
        def failing_call(prompt, max_tokens):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("Rate limit exceeded")  # Retryable error
            return original_call(prompt, max_tokens)
        
        extractor._call_llm_api = failing_call
        
        request = ExtractionRequest(content="Test content", max_tokens=1000)
        result = extractor.extract(request)
        
        assert result.success is True
        assert call_count[0] == 2  # Failed once, succeeded on retry
    
    def test_consecutive_failure_tracking(self):
        """Test that consecutive failures are tracked."""
        extractor = MockLLMExtractor(model_name="test-model")
        extractor.should_fail = True
        
        assert extractor.get_consecutive_failures() == 0
        
        # First failure
        request = ExtractionRequest(content="Test", max_tokens=1000)
        extractor.extract(request)
        assert extractor.get_consecutive_failures() == 1
        
        # Second failure
        extractor.extract(request)
        assert extractor.get_consecutive_failures() == 2
    
    def test_consecutive_failures_reset_on_success(self):
        """Test that consecutive failures reset after success."""
        extractor = MockLLMExtractor(model_name="test-model")
        
        # Fail twice
        extractor.should_fail = True
        request = ExtractionRequest(content="Test", max_tokens=1000)
        extractor.extract(request)
        extractor.extract(request)
        assert extractor.get_consecutive_failures() == 2
        
        # Succeed
        extractor.should_fail = False
        extractor.extract(request)
        assert extractor.get_consecutive_failures() == 0
    
    def test_abort_after_max_consecutive_failures(self):
        """Test that extraction aborts after too many failures."""
        extractor = MockLLMExtractor(model_name="test-model", max_consecutive_failures=3)
        extractor.should_fail = True
        
        request = ExtractionRequest(content="Test", max_tokens=1000)
        
        # Fail 3 times
        for _ in range(3):
            extractor.extract(request)
        
        assert extractor.get_consecutive_failures() == 3
        
        # Next call should raise APIError
        with pytest.raises(APIError) as exc_info:
            extractor.extract(request)
        
        assert "consecutive failures" in str(exc_info.value)


class TestLLMEntityExtractorErrorHandling:
    """Test error handling."""
    
    def test_prompt_build_failure(self):
        """Test handling of prompt building errors."""
        extractor = MockLLMExtractor(model_name="test-model")
        
        # Make prompt builder raise an error
        def failing_prompt_build(content, entity_types=None):
            raise Exception("Template file not found")
        
        extractor.prompt_builder.build_extraction_prompt = failing_prompt_build
        
        request = ExtractionRequest(content="Test", max_tokens=1000)
        result = extractor.extract(request)
        
        assert result.success is False
        assert "Prompt building failed" in result.error
    
    def test_parse_error_handling(self):
        """Test handling of parse errors."""
        extractor = MockLLMExtractor(model_name="test-model")
        
        # Return invalid JSON
        def bad_call(prompt, max_tokens):
            return {"text": "Not valid JSON", "tokens": 10}
        
        extractor._call_llm_api = bad_call
        
        request = ExtractionRequest(content="Test", max_tokens=1000)
        result = extractor.extract(request)
        
        assert result.success is False
        assert "Parse error" in result.error
        assert extractor.get_consecutive_failures() == 1


class TestLLMEntityExtractorRetryableErrors:
    """Test retryable error detection."""
    
    def test_rate_limit_error_is_retryable(self):
        """Test that rate limit errors are detected as retryable."""
        extractor = MockLLMExtractor(model_name="test")
        
        error = Exception("Rate limit exceeded")
        assert extractor._is_retryable_error(error) is True
    
    def test_timeout_error_is_retryable(self):
        """Test that timeout errors are retryable."""
        extractor = MockLLMExtractor(model_name="test")
        
        error = Exception("Request timeout")
        assert extractor._is_retryable_error(error) is True
    
    def test_503_error_is_retryable(self):
        """Test that 503 errors are retryable."""
        extractor = MockLLMExtractor(model_name="test")
        
        error = Exception("503 Service Unavailable")
        assert extractor._is_retryable_error(error) is True
    
    def test_429_error_is_retryable(self):
        """Test that 429 errors are retryable."""
        extractor = MockLLMExtractor(model_name="test")
        
        error = Exception("429 Too Many Requests")
        assert extractor._is_retryable_error(error) is True
    
    def test_auth_error_is_not_retryable(self):
        """Test that auth errors are not retryable."""
        extractor = MockLLMExtractor(model_name="test")
        
        error = Exception("Invalid API key")
        assert extractor._is_retryable_error(error) is False
    
    def test_validation_error_is_not_retryable(self):
        """Test that validation errors are not retryable."""
        extractor = MockLLMExtractor(model_name="test")
        
        error = Exception("Invalid request format")
        assert extractor._is_retryable_error(error) is False


class TestLLMEntityExtractorUtilityMethods:
    """Test utility methods."""
    
    def test_get_model_name(self):
        """Test getting model name."""
        extractor = MockLLMExtractor(model_name="my-model")
        
        assert extractor.get_model_name() == "my-model"
    
    def test_reset_consecutive_failures(self):
        """Test manually resetting failure counter."""
        extractor = MockLLMExtractor(model_name="test")
        extractor.should_fail = True
        
        # Create some failures
        request = ExtractionRequest(content="Test", max_tokens=1000)
        extractor.extract(request)
        extractor.extract(request)
        assert extractor.get_consecutive_failures() == 2
        
        # Reset
        extractor.reset_consecutive_failures()
        assert extractor.get_consecutive_failures() == 0
    
    def test_extraction_time_is_recorded(self):
        """Test that extraction time is recorded."""
        extractor = MockLLMExtractor(model_name="test")
        
        request = ExtractionRequest(content="Test", max_tokens=1000)
        result = extractor.extract(request)
        
        assert result.extraction_time is not None
        assert result.extraction_time > 0
    
    def test_raw_response_is_stored(self):
        """Test that raw response is stored."""
        extractor = MockLLMExtractor(model_name="test")
        
        request = ExtractionRequest(content="Test", max_tokens=1000)
        result = extractor.extract(request)
        
        assert result.raw_response is not None
        assert "Test Entity" in result.raw_response
