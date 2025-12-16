"""
AWS Bedrock implementation for entity extraction.

Uses boto3 to access Claude models hosted on AWS Bedrock.
"""

import json
import logging
from typing import Dict, Any, Optional

import boto3
from botocore.exceptions import ClientError, BotoCoreError

from kg_forge.extractors.llm_base import LLMEntityExtractor
from kg_forge.extractors.base import APIError
from kg_forge.utils.verbose import VerboseLogger

logger = logging.getLogger(__name__)


class BedrockExtractor(LLMEntityExtractor):
    """Entity extractor using AWS Bedrock with Claude models.
    
    Uses boto3 to access Claude models hosted on AWS Bedrock.
    
    Inherits common LLM functionality from LLMEntityExtractor:
    - Prompt building
    - Response parsing
    - Retry logic
    - Failure tracking
    """
    
    def __init__(
        self,
        model_name: str = "anthropic.claude-3-haiku-20240307-v1:0",
        region: str = "us-east-1",
        timeout: int = 30,
        max_retries: int = 1,
        max_consecutive_failures: int = 10,
        entities_dir: str = "entities_extract",
        verbose_logger: Optional[VerboseLogger] = None
    ):
        """Initialize Bedrock extractor.
        
        Args:
            model_name: Bedrock model ID
            region: AWS region
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
        
        # Bedrock-specific configuration
        self.region = region
        self.timeout = timeout
        
        # Initialize Bedrock client
        self.client = boto3.client(
            "bedrock-runtime",
            region_name=region
        )
        
        logger.info(f"Initialized Bedrock extractor with model: {model_name}")
    
    def _call_llm_api(self, prompt: str, max_tokens: int) -> Dict[str, Any]:
        """Call AWS Bedrock API.
        
        Args:
            prompt: Complete prompt to send
            max_tokens: Maximum tokens for response
            
        Returns:
            Dictionary with 'text' and optional 'tokens' keys
            
        Raises:
            ClientError: On API errors (handled by base class retry logic)
            BotoCoreError: On boto core errors
        """
        logger.debug(f"Calling Bedrock API with model {self.model_name}")
        
        # Format request for Claude models
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        })
        
        try:
            # Invoke model
            response = self.client.invoke_model(
                modelId=self.model_name,
                body=body
            )
            
            # Parse response
            response_body = json.loads(response.get("body").read())
            
            # Extract text from Claude response format
            if "content" not in response_body:
                raise APIError("No content in Bedrock response")
            
            content_blocks = response_body["content"]
            if not content_blocks:
                raise APIError("Empty content in Bedrock response")
            
            # Get text from first content block
            text = content_blocks[0].get("text", "")
            
            # Extract token usage
            tokens = None
            if "usage" in response_body:
                input_tokens = response_body["usage"].get("input_tokens", 0)
                output_tokens = response_body["usage"].get("output_tokens", 0)
                tokens = input_tokens + output_tokens
                logger.debug(f"Tokens used: {tokens} (in: {input_tokens}, out: {output_tokens})")
            
            return {
                "text": text,
                "tokens": tokens
            }
            
        except (ClientError, BotoCoreError) as e:
            # Re-raise for base class retry logic to handle
            raise
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """Check if Bedrock error is retryable.
        
        Overrides base class to add Bedrock-specific error handling.
        
        Args:
            error: The exception that occurred
            
        Returns:
            True if error should be retried
        """
        # Check for ClientError with specific error codes
        if isinstance(error, ClientError):
            error_code = error.response.get("Error", {}).get("Code", "")
            retryable_codes = [
                "ThrottlingException",
                "ServiceUnavailableException",
                "TooManyRequestsException",
            ]
            if error_code in retryable_codes:
                return True
        
        # Fall back to base class logic
        return super()._is_retryable_error(error)
