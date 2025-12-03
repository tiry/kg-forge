"""Tests for extractor factory."""

import pytest
import os
from unittest.mock import patch

from kg_forge.extractors.factory import create_extractor, _has_aws_credentials
from kg_forge.extractors.base import ConfigurationError
from kg_forge.extractors.openrouter import OpenRouterExtractor
from kg_forge.extractors.bedrock import BedrockExtractor


class TestFactoryAWSCredentials:
    """Test AWS credentials detection."""
    
    def test_has_aws_credentials_with_env_vars(self):
        """Test AWS credentials detection when env vars are set."""
        with patch.dict(os.environ, {
            "AWS_ACCESS_KEY_ID": "test-key",
            "AWS_SECRET_ACCESS_KEY": "test-secret"
        }):
            assert _has_aws_credentials() is True
    
    def test_has_aws_credentials_missing_key_id(self):
        """Test AWS credentials detection when access key ID is missing."""
        with patch.dict(os.environ, {
            "AWS_SECRET_ACCESS_KEY": "test-secret"
        }, clear=True):
            assert _has_aws_credentials() is False
    
    def test_has_aws_credentials_missing_secret(self):
        """Test AWS credentials detection when secret key is missing."""
        with patch.dict(os.environ, {
            "AWS_ACCESS_KEY_ID": "test-key"
        }, clear=True):
            assert _has_aws_credentials() is False
    
    def test_has_aws_credentials_both_missing(self):
        """Test AWS credentials detection when both are missing."""
        with patch.dict(os.environ, {}, clear=True):
            assert _has_aws_credentials() is False


class TestCreateExtractor:
    """Test create_extractor factory function."""
    
    def test_create_openrouter_extractor_with_api_key(self):
        """Test creating OpenRouter extractor when API key is provided."""
        with patch.dict(os.environ, {}, clear=True):
            extractor = create_extractor(
                openrouter_api_key="sk-or-test-key"
            )
            
            assert isinstance(extractor, OpenRouterExtractor)
            assert extractor.model_name == "anthropic/claude-3-haiku"
    
    def test_create_openrouter_extractor_from_env(self):
        """Test creating OpenRouter extractor from environment variable."""
        with patch.dict(os.environ, {
            "OPENROUTER_API_KEY": "sk-or-env-key"
        }):
            extractor = create_extractor()
            
            assert isinstance(extractor, OpenRouterExtractor)
    
    def test_create_openrouter_with_custom_model(self):
        """Test creating OpenRouter extractor with custom model."""
        extractor = create_extractor(
            openrouter_api_key="sk-or-test-key",
            openrouter_model="anthropic/claude-3-sonnet"
        )
        
        assert isinstance(extractor, OpenRouterExtractor)
        assert extractor.model_name == "anthropic/claude-3-sonnet"
    
    def test_create_openrouter_model_from_env(self):
        """Test OpenRouter model name from environment variable."""
        with patch.dict(os.environ, {
            "OPENROUTER_API_KEY": "sk-or-test-key",
            "OPENROUTER_MODEL_NAME": "openai/gpt-4"
        }):
            extractor = create_extractor()
            
            assert isinstance(extractor, OpenRouterExtractor)
            assert extractor.model_name == "openai/gpt-4"
    
    def test_create_bedrock_extractor_when_aws_available(self):
        """Test creating Bedrock extractor when AWS credentials available."""
        with patch.dict(os.environ, {
            "AWS_ACCESS_KEY_ID": "test-key",
            "AWS_SECRET_ACCESS_KEY": "test-secret"
        }, clear=True):
            extractor = create_extractor()
            
            assert isinstance(extractor, BedrockExtractor)
            assert extractor.model_name == "anthropic.claude-3-haiku-20240307-v1:0"
    
    def test_create_bedrock_with_custom_model(self):
        """Test creating Bedrock extractor with custom model."""
        with patch.dict(os.environ, {
            "AWS_ACCESS_KEY_ID": "test-key",
            "AWS_SECRET_ACCESS_KEY": "test-secret"
        }, clear=True):
            extractor = create_extractor(
                bedrock_model="anthropic.claude-3-sonnet-20240229-v1:0"
            )
            
            assert isinstance(extractor, BedrockExtractor)
            assert extractor.model_name == "anthropic.claude-3-sonnet-20240229-v1:0"
    
    def test_create_bedrock_with_custom_region(self):
        """Test creating Bedrock extractor with custom region."""
        with patch.dict(os.environ, {
            "AWS_ACCESS_KEY_ID": "test-key",
            "AWS_SECRET_ACCESS_KEY": "test-secret"
        }, clear=True):
            extractor = create_extractor(
                bedrock_region="us-west-2"
            )
            
            assert isinstance(extractor, BedrockExtractor)
            assert extractor.region == "us-west-2"
    
    def test_create_bedrock_region_from_env(self):
        """Test Bedrock region from environment variable."""
        with patch.dict(os.environ, {
            "AWS_ACCESS_KEY_ID": "test-key",
            "AWS_SECRET_ACCESS_KEY": "test-secret",
            "AWS_DEFAULT_REGION": "eu-west-1"
        }, clear=True):
            extractor = create_extractor()
            
            assert isinstance(extractor, BedrockExtractor)
            assert extractor.region == "eu-west-1"
    
    def test_openrouter_priority_over_bedrock(self):
        """Test that OpenRouter takes priority over Bedrock when both available."""
        with patch.dict(os.environ, {
            "OPENROUTER_API_KEY": "sk-or-test-key",
            "AWS_ACCESS_KEY_ID": "test-key",
            "AWS_SECRET_ACCESS_KEY": "test-secret"
        }):
            extractor = create_extractor()
            
            # OpenRouter should be selected
            assert isinstance(extractor, OpenRouterExtractor)
    
    def test_no_provider_configured_raises_error(self):
        """Test that ConfigurationError is raised when no provider is configured."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ConfigurationError) as exc_info:
                create_extractor()
            
            assert "No LLM provider configured" in str(exc_info.value)
            assert "OPENROUTER_API_KEY" in str(exc_info.value)
            assert "AWS_ACCESS_KEY_ID" in str(exc_info.value)


class TestFactoryErrorMessages:
    """Test factory error messages for better user experience."""
    
    def test_error_message_is_helpful(self):
        """Test that error message provides clear guidance."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ConfigurationError) as exc_info:
                create_extractor()
            
            error_msg = str(exc_info.value)
            
            # Should mention both providers
            assert "OPENROUTER_API_KEY" in error_msg
            assert "AWS_ACCESS_KEY_ID" in error_msg
            
            # Should reference .env.example
            assert ".env.example" in error_msg
