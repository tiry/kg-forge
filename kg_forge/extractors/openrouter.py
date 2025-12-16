"""
OpenRouter implementation for entity extraction.

Uses the OpenAI-compatible API provided by OpenRouter to access multiple LLM providers.
"""

import logging
from typing import Dict, Any, Optional

from openai import OpenAI
from openai import APIError as OpenAIAPIError

from kg_forge.extractors.llm_base import LLMEntityExtractor
from kg_forge.extractors.base import APIError
from kg_forge.utils.verbose import VerboseLogger

logger = logging.getLogger(__name__)


class OpenRouterExtractor(LLMEntityExtractor):
    """Entity extractor using OpenRouter's unified LLM API.
    
    OpenRouter provides access to multiple LLM providers (Claude, GPT-4, etc.)
    through an OpenAI-compatible API.
    
    Inherits common LLM functionality from LLMEntityExtractor:
    - Prompt building
    - Response parsing
    - Retry logic
    - Failure tracking
    """
    
    def __init__(
        self,
        api_key: str,
        model_name: str = "anthropic/claude-3-haiku",
        base_url: str = "https://openrouter.ai/api/v1",
        timeout: int = 30,
        max_retries: int = 1,
        max_consecutive_failures: int = 10,
        entities_dir: str = "entities_extract",
        verbose_logger: Optional[VerboseLogger] = None
    ):
        """Initialize OpenRouter extractor.
        
        Args:
            api_key: OpenRouter API key
            model_name: Model to use (e.g., 'anthropic/claude-3-haiku')
            base_url: OpenRouter API base URL
            timeout: Timeout for API calls in seconds
            max_retries: Maximum retry attempts for failed calls
            max_consecutive_failures: Abort if this many consecutive failures
            entities_dir: Directory containing entity definition files
            verbose_logger: Optional verbose logger for detailed output
        """
        # Initialize base class
        super().__init__(
            model_name=model_name,
            entities_dir=entities_dir,
            max_retries=max_retries,
            max_consecutive_failures=max_consecutive_failures,
            verbose_logger=verbose_logger
        )
        
        # OpenRouter-specific configuration
        self.timeout = timeout
        
        # Initialize OpenAI client with OpenRouter endpoint
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        
        logger.info(f"Initialized OpenRouter extractor with model: {model_name}")
    
    def _call_llm_api(self, prompt: str, max_tokens: int) -> Dict[str, Any]:
        """Call OpenRouter API.
        
        Args:
            prompt: Complete prompt to send
            max_tokens: Maximum tokens for response
            
        Returns:
            Dictionary with 'text' and optional 'tokens' keys
            
        Raises:
            OpenAIAPIError: On API errors (handled by base class retry logic)
        """
        logger.debug(f"Calling OpenRouter API with model {self.model_name}")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                timeout=self.timeout
            )
            
            # Extract response text
            if not response.choices:
                raise APIError("No choices in API response")
            
            text = response.choices[0].message.content
            
            # Extract token usage
            tokens = None
            if response.usage:
                tokens = response.usage.total_tokens
                logger.debug(f"Tokens used: {tokens}")
            
            return {
                "text": text,
                "tokens": tokens
            }
            
        except OpenAIAPIError as e:
            # Re-raise for base class retry logic to handle
            raise
