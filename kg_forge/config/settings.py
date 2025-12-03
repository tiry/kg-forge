"""Configuration management for kg-forge CLI."""

import os
import re
from pathlib import Path
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator
from dotenv import load_dotenv
import yaml


class Neo4jConfig(BaseModel):
    """Neo4j connection configuration."""
    uri: str = Field(default="bolt://localhost:7687")
    username: str = Field(default="neo4j")
    password: str = Field(default="password")


class AWSConfig(BaseModel):
    """AWS Bedrock configuration."""
    access_key_id: Optional[str] = Field(default=None)
    secret_access_key: Optional[str] = Field(default=None)
    default_region: str = Field(default="us-east-1")
    bedrock_model_name: str = Field(default="anthropic.claude-3-haiku-20240307-v1:0")


class GraphConfig(BaseModel):
    """Graph database configuration."""
    backend: str = Field(default="neo4j")


class AppConfig(BaseModel):
    """Application configuration."""
    log_level: str = Field(default="INFO")
    default_namespace: str = Field(default="default")

    @field_validator('log_level')
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v.upper()

    @field_validator('default_namespace')
    @classmethod
    def validate_namespace(cls, v):
        """Validate namespace format - alphanumeric only, no spaces."""
        if not re.match(r'^[a-zA-Z0-9]+$', v):
            raise ValueError("Namespace must be alphanumeric only (no spaces or special characters)")
        return v


class Settings(BaseModel):
    """Main configuration class."""
    neo4j: Neo4jConfig = Field(default_factory=Neo4jConfig)
    aws: AWSConfig = Field(default_factory=AWSConfig)
    graph: GraphConfig = Field(default_factory=GraphConfig)
    app: AppConfig = Field(default_factory=AppConfig)

    @classmethod
    def load_config(cls, config_overrides: Optional[Dict[str, Any]] = None) -> "Settings":
        """
        Load configuration from multiple sources with proper precedence:
        1. Command-line arguments (highest priority)
        2. YAML configuration file
        3. Environment variables
        4. .env file values
        5. Default values (lowest priority)
        """
        # Load .env file first (lowest priority)
        load_dotenv()

        # Load configuration from YAML file
        yaml_config = cls._load_yaml_config()

        # Merge configurations with proper precedence
        config_data = {}
        
        # Start with defaults (handled by Pydantic)
        
        # Apply .env and environment variables
        env_config = cls._load_env_config()
        config_data = cls._merge_config(config_data, env_config)
        
        # Apply YAML config
        if yaml_config:
            config_data = cls._merge_config(config_data, yaml_config)
        
        # Apply command-line overrides (highest priority)
        if config_overrides:
            config_data = cls._merge_config(config_data, config_overrides)

        return cls(**config_data)

    @classmethod
    def _load_yaml_config(cls) -> Optional[Dict[str, Any]]:
        """Load configuration from YAML file."""
        config_paths = [
            Path("./kg_forge.yaml"),
            Path("./config.yaml"),
            Path.home() / ".kg_forge.yaml"
        ]
        
        for config_path in config_paths:
            if config_path.exists():
                try:
                    with open(config_path, 'r') as f:
                        return yaml.safe_load(f)
                except yaml.YAMLError as e:
                    raise ValueError(f"Error parsing YAML config file {config_path}: {e}")
                except Exception as e:
                    raise ValueError(f"Error reading config file {config_path}: {e}")
        
        return None

    @classmethod
    def _load_env_config(cls) -> Dict[str, Any]:
        """Load configuration from environment variables."""
        config = {}
        
        # Neo4j configuration
        neo4j_config = {}
        if os.getenv("NEO4J_URI"):
            neo4j_config["uri"] = os.getenv("NEO4J_URI")
        if os.getenv("NEO4J_USERNAME"):
            neo4j_config["username"] = os.getenv("NEO4J_USERNAME")
        if os.getenv("NEO4J_PASSWORD"):
            neo4j_config["password"] = os.getenv("NEO4J_PASSWORD")
        if neo4j_config:
            config["neo4j"] = neo4j_config

        # AWS configuration
        aws_config = {}
        if os.getenv("AWS_ACCESS_KEY_ID"):
            aws_config["access_key_id"] = os.getenv("AWS_ACCESS_KEY_ID")
        if os.getenv("AWS_SECRET_ACCESS_KEY"):
            aws_config["secret_access_key"] = os.getenv("AWS_SECRET_ACCESS_KEY")
        if os.getenv("AWS_DEFAULT_REGION"):
            aws_config["default_region"] = os.getenv("AWS_DEFAULT_REGION")
        if os.getenv("BEDROCK_MODEL_NAME"):
            aws_config["bedrock_model_name"] = os.getenv("BEDROCK_MODEL_NAME")
        if aws_config:
            config["aws"] = aws_config

        # App configuration
        app_config = {}
        if os.getenv("LOG_LEVEL"):
            app_config["log_level"] = os.getenv("LOG_LEVEL")
        if os.getenv("DEFAULT_NAMESPACE"):
            app_config["default_namespace"] = os.getenv("DEFAULT_NAMESPACE")
        if app_config:
            config["app"] = app_config

        return config

    @classmethod
    def _merge_config(cls, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Merge configuration dictionaries recursively."""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = cls._merge_config(result[key], value)
            else:
                result[key] = value
        
        return result

    def validate_namespace(self, namespace: str) -> str:
        """Validate namespace format."""
        if not re.match(r'^[a-zA-Z0-9]+$', namespace):
            raise ValueError("Namespace must be alphanumeric only (no spaces or special characters)")
        return namespace


def get_settings(config_overrides: Optional[Dict[str, Any]] = None) -> Settings:
    """Get application settings with optional overrides."""
    return Settings.load_config(config_overrides)
