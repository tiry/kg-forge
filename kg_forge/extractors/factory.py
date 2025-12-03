"""
Factory for creating entity extractors based on configuration.
"""

import logging
import os
from typing import Optional

from kg_forge.extractors.base import EntityExtractor, ConfigurationError

logger = logging.getLogger(__name__)


def create_extractor(
    entities_dir: str = "entities_extract",
    openrouter_api_key: Optional[str] = None,
    openrouter_model: Optional[str] = None,
    bedrock_model: Optional[str] = None,
    bedrock_region: Optional[str] = None
) -> EntityExtractor:
    """Create appropriate extractor based on available configuration.
    
    Priority:
    1. OpenRouter (if OPENROUTER_API_KEY set or provided)
    2. Bedrock (if AWS credentials available)
    3. Error (no valid configuration)
    
    Args:
        entities_dir: Directory containing entity definitions
        openrouter_api_key: OpenRouter API key (or read from env)
        openrouter_model: OpenRouter model name (or read from env)
        bedrock_model: Bedrock model ID (or read from env)
        bedrock_region: AWS region (or read from env)
        
    Returns:
        Configured EntityExtractor instance
        
    Raises:
        ConfigurationError: If no valid LLM configuration found
    """
    # Try OpenRouter first
    api_key = openrouter_api_key or os.getenv("OPENROUTER_API_KEY")
    
    if api_key:
        logger.info("OpenRouter API key found, using OpenRouter extractor")
        
        from kg_forge.extractors.openrouter import OpenRouterExtractor
        
        model = openrouter_model or os.getenv(
            "OPENROUTER_MODEL_NAME",
            "anthropic/claude-3-haiku"
        )
        
        return OpenRouterExtractor(
            api_key=api_key,
            model_name=model,
            entities_dir=entities_dir
        )
    
    # Try Bedrock as fallback
    if _has_aws_credentials():
        logger.info("AWS credentials found, using Bedrock extractor")
        
        from kg_forge.extractors.bedrock import BedrockExtractor
        
        model = bedrock_model or os.getenv(
            "BEDROCK_MODEL_NAME",
            "anthropic.claude-3-haiku-20240307-v1:0"
        )
        
        region = bedrock_region or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        
        return BedrockExtractor(
            model_name=model,
            region=region,
            entities_dir=entities_dir
        )
    
    # No valid configuration found
    raise ConfigurationError(
        "No LLM provider configured. Please set one of:\n"
        "  - OPENROUTER_API_KEY environment variable (recommended)\n"
        "  - AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY (for Bedrock)\n"
        "\n"
        "See .env.example for configuration details."
    )


def _has_aws_credentials() -> bool:
    """Check if AWS credentials are available.
    
    Returns:
        True if AWS credentials are configured
    """
    # Check environment variables
    if os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"):
        return True
    
    # Could also check ~/.aws/credentials file, but env vars are sufficient for now
    return False
