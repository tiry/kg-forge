"""
Base class for LLM-based entity extractors.

Provides common functionality for OpenRouter, Bedrock, and other LLM providers.
"""

import logging
import time
from abc import abstractmethod
from typing import Optional, Dict, Any

from kg_forge.models.extraction import ExtractionRequest, ExtractionResult
from kg_forge.extractors.base import EntityExtractor, APIError, ParseError
from kg_forge.extractors.parser import ResponseParser
from kg_forge.extractors.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)


class LLMEntityExtractor(EntityExtractor):
    """Base class for LLM-based entity extractors.
    
    Provides common functionality:
    - Prompt building from entity definitions
    - Response parsing
    - Retry logic with exponential backoff
    - Consecutive failure tracking
    - Confidence filtering
    
    Subclasses must implement:
    - _call_llm_api(): Make the actual LLM API call
    - get_model_name(): Return the model identifier
    """
    
    def __init__(
        self,
        model_name: str,
        entities_dir: str = "entities_extract",
        max_retries: int = 1,
        max_consecutive_failures: int = 10
    ):
        """Initialize LLM extractor.
        
        Args:
            model_name: LLM model identifier
            entities_dir: Directory containing entity definition files
            max_retries: Maximum retry attempts for failed calls
            max_consecutive_failures: Abort if this many consecutive failures
        """
        self.model_name = model_name
        self.max_retries = max_retries
        self.max_consecutive_failures = max_consecutive_failures
        
        # Initialize prompt builder and parser
        self.prompt_builder = PromptBuilder(entities_dir=entities_dir)
        self.parser = ResponseParser()
        
        # Track consecutive failures
        self._consecutive_failures = 0
        
        logger.info(f"Initialized LLM extractor with model: {model_name}")
    
    def extract(self, request: ExtractionRequest) -> ExtractionResult:
        """Extract entities from content using LLM.
        
        Template method pattern: orchestrates the extraction process
        and delegates API calls to subclasses.
        
        Args:
            request: Extraction request with content and configuration
            
        Returns:
            Extraction result with entities or error
            
        Raises:
            APIError: If too many consecutive failures occur
        """
        start_time = time.time()
        
        # Check consecutive failures
        if self._consecutive_failures >= self.max_consecutive_failures:
            raise APIError(
                f"Aborting after {self._consecutive_failures} consecutive failures"
            )
        
        # Build prompt
        try:
            prompt = self.prompt_builder.build_extraction_prompt(
                content=request.content,
                entity_types=request.entity_types if request.entity_types else None
            )
        except Exception as e:
            logger.error(f"Failed to build prompt: {e}")
            return ExtractionResult(
                entities=[],
                success=False,
                error=f"Prompt building failed: {e}"
            )
        
        # Call LLM with retry logic
        response_text = None
        tokens_used = None
        retry_count = 0
        
        while retry_count <= self.max_retries:
            try:
                # Delegate to subclass for actual API call
                response = self._call_llm_api(prompt, request.max_tokens)
                response_text = response["text"]
                tokens_used = response.get("tokens")
                
                # Reset consecutive failures on success
                self._consecutive_failures = 0
                break
                
            except Exception as e:
                retry_count += 1
                
                # Check if retryable error
                if self._is_retryable_error(e) and retry_count <= self.max_retries:
                    # Exponential backoff
                    wait_time = 2 ** retry_count
                    logger.warning(f"Retryable error, waiting {wait_time}s: {e}")
                    time.sleep(wait_time)
                else:
                    # Non-retryable or max retries exceeded
                    self._consecutive_failures += 1
                    logger.error(f"LLM API error: {e}")
                    return ExtractionResult(
                        entities=[],
                        model_name=self.model_name,
                        extraction_time=time.time() - start_time,
                        success=False,
                        error=f"LLM API error: {e}"
                    )
        
        # Parse response
        try:
            entities = self.parser.parse(response_text)
            
            # Filter by confidence if specified
            if request.min_confidence > 0.0:
                original_count = len(entities)
                entities = [e for e in entities if e.confidence >= request.min_confidence]
                if original_count > len(entities):
                    logger.info(
                        f"Filtered {original_count - len(entities)} entities "
                        f"below confidence threshold {request.min_confidence}"
                    )
            
            extraction_time = time.time() - start_time
            
            return ExtractionResult(
                entities=entities,
                raw_response=response_text,
                model_name=self.model_name,
                tokens_used=tokens_used,
                extraction_time=extraction_time,
                success=True
            )
            
        except ParseError as e:
            self._consecutive_failures += 1
            logger.error(f"Parse error: {e}")
            return ExtractionResult(
                entities=[],
                raw_response=response_text,
                model_name=self.model_name,
                tokens_used=tokens_used,
                extraction_time=time.time() - start_time,
                success=False,
                error=f"Parse error: {e}"
            )
    
    @abstractmethod
    def _call_llm_api(self, prompt: str, max_tokens: int) -> Dict[str, Any]:
        """Call the LLM API.
        
        Subclasses must implement this to make the actual API call.
        
        Args:
            prompt: Complete prompt to send
            max_tokens: Maximum tokens for response
            
        Returns:
            Dictionary with keys:
                - 'text': Response text from LLM
                - 'tokens': Token count (optional)
                
        Raises:
            Exception: On API errors (will be handled by retry logic)
        """
        pass
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """Check if an error is retryable.
        
        Subclasses can override to customize retry behavior.
        By default, checks error class name and message.
        
        Args:
            error: The exception that occurred
            
        Returns:
            True if error should be retried
        """
        error_class_name = error.__class__.__name__
        error_message = str(error).lower()
        
        # Common retryable error patterns
        retryable_patterns = [
            "rate limit",
            "timeout",
            "connection",
            "503",  # Service Unavailable
            "429",  # Too Many Requests
        ]
        
        retryable_classes = [
            "RateLimitError",
            "APIConnectionError", 
            "TimeoutError",
            "ConnectionError",
        ]
        
        # Check class name
        if error_class_name in retryable_classes:
            return True
        
        # Check error message
        if any(pattern in error_message for pattern in retryable_patterns):
            return True
        
        return False
    
    def get_model_name(self) -> str:
        """Get the model name being used.
        
        Returns:
            Model identifier
        """
        return self.model_name
    
    def get_consecutive_failures(self) -> int:
        """Get count of consecutive failures.
        
        Useful for testing and monitoring.
        
        Returns:
            Number of consecutive failures
        """
        return self._consecutive_failures
    
    def reset_consecutive_failures(self):
        """Reset consecutive failure counter.
        
        Useful for testing or manual recovery.
        """
        self._consecutive_failures = 0
