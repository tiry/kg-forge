"""Test configuration settings."""

import os
import tempfile
from pathlib import Path
import pytest
import yaml
from unittest.mock import patch

from kg_forge.config.settings import Settings, get_settings


def test_default_settings():
    """Test default settings initialization."""
    settings = Settings()
    
    assert settings.neo4j.uri == "bolt://localhost:7687"
    assert settings.neo4j.username == "neo4j"
    assert settings.neo4j.password == "password"
    
    assert settings.aws.default_region == "us-east-1"
    assert settings.aws.bedrock_model_name == "anthropic.claude-3-haiku-20240307-v1:0"
    
    assert settings.app.log_level == "INFO"
    assert settings.app.default_namespace == "default"


def test_env_settings():
    """Test settings from environment variables (when no YAML config exists)."""
    # Save original values
    original_neo4j_uri = os.environ.get("NEO4J_URI")
    original_log_level = os.environ.get("LOG_LEVEL")
    
    try:
        os.environ["NEO4J_URI"] = "bolt://testhost:7687"
        os.environ["LOG_LEVEL"] = "DEBUG"
        
        # Mock the YAML loading to return None so env vars take precedence
        with patch.object(Settings, '_load_yaml_config', return_value=None):
            settings = Settings.load_config()
            
            assert settings.neo4j.uri == "bolt://testhost:7687"
            assert settings.app.log_level == "DEBUG"
        
    finally:
        # Clean up - restore original values or delete if they didn't exist
        if original_neo4j_uri is not None:
            os.environ["NEO4J_URI"] = original_neo4j_uri
        elif "NEO4J_URI" in os.environ:
            del os.environ["NEO4J_URI"]
            
        if original_log_level is not None:
            os.environ["LOG_LEVEL"] = original_log_level
        elif "LOG_LEVEL" in os.environ:
            del os.environ["LOG_LEVEL"]


def test_yaml_settings():
    """Test settings from YAML file."""
    with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w") as temp_file:
        yaml_content = """
        neo4j:
          uri: bolt://yamlhost:7687
        app:
          log_level: WARNING
        """
        temp_file.write(yaml_content)
        temp_file.flush()
        
        # Save original path to restore later
        original_path = Path.cwd()
        try:
            # Change to temp directory
            os.chdir(Path(temp_file.name).parent)
            
            # Rename file to match what settings.py looks for
            yaml_path = Path(temp_file.name).parent / "kg_forge.yaml"
            with open(yaml_path, "w") as f:
                f.write(yaml_content)
            
            settings = Settings.load_config()
            
            assert settings.neo4j.uri == "bolt://yamlhost:7687"
            assert settings.app.log_level == "WARNING"
            
            # Clean up
            yaml_path.unlink()
        finally:
            # Restore original working directory
            os.chdir(original_path)


def test_override_settings():
    """Test settings with overrides."""
    overrides = {
        "neo4j": {"uri": "bolt://override:7687"},
        "app": {"log_level": "ERROR"}
    }
    
    settings = Settings.load_config(overrides)
    
    assert settings.neo4j.uri == "bolt://override:7687"
    assert settings.app.log_level == "ERROR"


def test_validate_namespace_valid():
    """Test namespace validation with valid names."""
    settings = Settings()
    
    # These should all be valid
    assert settings.validate_namespace("default") == "default"
    assert settings.validate_namespace("test123") == "test123"
    assert settings.validate_namespace("UPPERCASE") == "UPPERCASE"
    assert settings.validate_namespace("mixedCase123") == "mixedCase123"


def test_validate_namespace_invalid():
    """Test namespace validation with invalid names."""
    settings = Settings()
    
    # These should all be invalid
    with pytest.raises(ValueError):
        settings.validate_namespace("space name")
    
    with pytest.raises(ValueError):
        settings.validate_namespace("special-char")
    
    with pytest.raises(ValueError):
        settings.validate_namespace("under_score")
    
    with pytest.raises(ValueError):
        settings.validate_namespace("dot.name")


def test_log_level_validation():
    """Test log level validation."""
    # Valid log levels
    settings = Settings(app={"log_level": "DEBUG"})
    assert settings.app.log_level == "DEBUG"
    
    settings = Settings(app={"log_level": "info"})
    assert settings.app.log_level == "INFO"  # Should be uppercase
    
    # Invalid log level
    with pytest.raises(ValueError):
        Settings(app={"log_level": "INVALID"})
