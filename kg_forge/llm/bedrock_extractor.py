"""
AWS Bedrock LLM implementation using LlamaIndex.
"""

from .client import BaseLLMExtractor
from .exceptions import LLMError


class BedrockLLMExtractor(BaseLLMExtractor):
    """LLM extractor using AWS Bedrock via LlamaIndex."""
    
    def __init__(self, model_name: str, region: str, access_key_id: str = None, 
                 secret_access_key: str = None, session_token: str = None,
                 profile_name: str = None, max_tokens: int = 4000, temperature: float = 0.1):
        """
        Initialize Bedrock LLM extractor.
        
        Args:
            model_name: Bedrock model identifier (e.g., anthropic.claude-3-haiku-20240307-v1:0)
            region: AWS region
            access_key_id: AWS access key (optional, can use env/profile/SSO)
            secret_access_key: AWS secret key (optional, can use env/profile/SSO)
            session_token: AWS session token (optional, for temporary credentials)
            profile_name: AWS profile name (optional, alternative to explicit credentials)
            max_tokens: Maximum tokens for response
            temperature: Temperature for response generation
        """
        super().__init__()
        self.model_name = model_name
        self.region = region
        self.max_tokens = max_tokens
        self.temperature = temperature
        
        # Initialize Bedrock LLM client
        try:
            from llama_index.llms.bedrock import Bedrock
            
            # Configure credentials - support multiple authentication methods:
            # 1. Explicit credentials (highest priority if provided)
            # 2. AWS profile 
            # 3. Environment variables / IAM roles / SSO (handled automatically by boto3)
            credentials = {}
            
            if access_key_id and secret_access_key:
                # Method 1: Explicit credentials
                credentials = {
                    'aws_access_key_id': access_key_id,
                    'aws_secret_access_key': secret_access_key
                }
                # Add session token if provided (for temporary credentials)
                if session_token:
                    credentials['aws_session_token'] = session_token
            elif profile_name:
                # Method 2: AWS profile
                credentials['profile_name'] = profile_name
            # Method 3: Environment/IAM/SSO - no explicit credentials needed
            
            self.llm = Bedrock(
                model=model_name,
                region_name=region,
                max_tokens=max_tokens,
                temperature=temperature,
                **credentials
            )
            
        except ImportError as e:
            raise LLMError("LlamaIndex Bedrock package not installed. Please install: pip install llama-index-llms-bedrock") from e
        except Exception as e:
            raise LLMError(f"Failed to initialize Bedrock LLM: {e}") from e
    
    def _call_llm(self, prompt: str) -> str:
        """
        Make LLM call to Bedrock.
        
        Args:
            prompt: Input prompt for entity extraction
            
        Returns:
            Raw response text from LLM
            
        Raises:
            LLMError: If LLM call fails
        """
        try:
            response = self.llm.complete(prompt)
            
            # Extract text from response
            if hasattr(response, 'text'):
                response_text = response.text
            else:
                response_text = str(response)
            
            # Check for empty response
            if not response_text or not response_text.strip():
                raise LLMError(f"Bedrock returned empty response. Model: {self.model_name}")
            
            return response_text
                
        except Exception as e:
            if isinstance(e, LLMError):
                raise
            raise LLMError(f"Bedrock LLM call failed: {e}") from e