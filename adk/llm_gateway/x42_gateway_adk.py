"""
X42 Gateway for Google ADK integration with internal LLM service.
Uses Google ADK's LiteLlm to connect to OpenAI-compatible internal API.
"""
import os
import logging
from typing import Any, AsyncIterator, Dict, List, Optional, Union


import litellm

os.environ.setdefault("LITELLM_DROP_PARAMS", "false")
litellm.drop_params = False



from google.adk.models.base_llm import BaseLlm
from google.adk.models import lite_llm as adk_lite_llm
# Also patch the imported reference in ADK's lite_llm module
# adk_lite_llm.acompletion = _filtered_acompletion

from adk.llm_gateway.x42_litellm_usage_model import X42LiteLLMUsageModel

from google.genai import types

# Try to import fastapi_common, fall back to simple implementations if not available
try:
    from fastapi_common.config.app_config import get_application_config
    from fastapi_common.util.hmac_util import HmacUtil
    from fastapi_common.service.logging import cvs_logger
    from fastapi_common.util.context_util import get_request_execution_ctx
    _HAS_FASTAPI_COMMON = True
except ImportError:
    _HAS_FASTAPI_COMMON = False
    # Simple fallback logger
    cvs_logger = logging.getLogger("x42_gateway")
    cvs_logger.setLevel(logging.INFO)
    if not cvs_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        cvs_logger.addHandler(handler)
    
    # Fallback implementations
    def get_application_config():
        class FallbackConfig:
            def get_service(self, name):
                return {}
            def get(self, key, default=None):
                return default
        return FallbackConfig()
    
    def get_request_execution_ctx():
        class FallbackCtx:
            grid = ""
        return FallbackCtx()
    
    class HmacUtil:
        def __init__(self, secret):
            self.secret = secret
        def get_cached_hmac(self, key, ttl):
            return {"appToken": "", "appTokenTs": ""}

# from fastapi_agent_google_adk.config.x42_workflow_config import get_x42_config

config = get_application_config()
# x42_config = get_x42_config()


class X42GatewayADK:
    """
    Gateway class for connecting to internal X42 LLM API using Google ADK.
    
    This gateway uses Google ADK's LiteLlm to connect to an OpenAI-compatible
    internal API endpoint, enabling seamless integration with ADK agents.
    
    Example:
        ```python
        from fastapi_agent_google_adk.llm_gateway.x42_gateway_adk import X42GatewayADK
        from google.adk.agents import LlmAgent
        
        gateway = X42GatewayADK()
        llm = gateway.get_llm_model({"experience_id": "my-exp"})
        
        agent = LlmAgent(
            model=llm,
            name="my_agent",
            instruction="You are a helpful assistant.",
        )
        ```
    """
    
    def __init__(self):
        """Initialize the X42 Gateway with configuration from environment."""
        # service_cf = config.get_service("chat-completions") or x42_config.get_service("chat-completions")
        # hmac_cf = config.get("hmac", {}) or x42_config.get("hmac", {})
        # self.url = service_cf.get("url")
        # self.method = service_cf.get("method", "POST")
        # self.timeout = int(service_cf.get("timeout", 30000))
        # self.enabled = service_cf.get("enabled", True)
        # self.hmac_enabled = hmac_cf.get("enabled", False)
        # self.app_secret = config.get('app_secret') or hmac_cf.get("appSecret")
        # self.app_code = config.get('app_code') or hmac_cf.get("appCode", "")
        # self.app_client_id = hmac_cf.get("appClientId", "")
        # self.hmac_util = HmacUtil(self.app_secret) if self.hmac_enabled and self.app_secret else None
        # self.service_headers = service_cf.get("headers", {})
        # self.hmac_ttl = int(hmac_cf.get("ttl", 900))  # default 900 seconds (15 min)

        service_cf = config.get_service("chat-completions")
        hmac_cf = config.get("hmac", {})
        self.url = service_cf.get("url")
        self.method = service_cf.get("method", "POST")
        self.timeout = int(service_cf.get("timeout", 30000))
        self.enabled = service_cf.get("enabled", True)
        self.hmac_enabled = hmac_cf.get("enabled", False)
        self.app_secret = config.get('app_secret') or hmac_cf.get("appSecret")
        self.app_code = config.get('app_code') or hmac_cf.get("appCode", "")
        self.app_client_id = hmac_cf.get("appClientId", "")
        self.hmac_util = HmacUtil(self.app_secret) if self.hmac_enabled and self.app_secret else None
        self.service_headers = service_cf.get("headers", {})
        self.hmac_ttl = int(hmac_cf.get("ttl", 900))  # default 900 seconds (15 min)

    def _build_headers(self, params: dict) -> Dict[str, str]:
        """Build headers including HMAC authentication if enabled."""
        hmac_auth_token = ""
        if self.hmac_enabled and self.hmac_util:
            cache_key = f"{self.app_code}:{self.app_client_id}"
            hmac_data = self.hmac_util.get_cached_hmac(cache_key, self.hmac_ttl)
            hmac_auth_token = (
                f"appToken:{hmac_data['appToken']};"
                f"appTokenTs:{hmac_data['appTokenTs']};"
                f"appCode:{self.app_code};"
                f"appClientId:{self.app_client_id}"
            )

        cvs_logger.info(
            f"HMAC Details - app_code: {self.app_code}, "
            f"app_client_id: {self.app_client_id}, "
            f"experience_id: {params.get('experience_id')}"
        )

        ctx = get_request_execution_ctx()
        headers = dict(self.service_headers)
        
        # Add experience ID and grid
        if params.get("experience_id"):
            headers["x-experienceId"] = params.get("experience_id")
        if ctx and ctx.grid:
            headers["x-grid"] = ctx.grid
        
        headers["X-TFY-METADATA"] = '{"tfy_log_request":"true"}'
        
        if hmac_auth_token:
            headers["x-apptoapp-authorization"] = hmac_auth_token
        
        return headers

    def get_llm_model(self, params: Optional[dict] = None) -> BaseLlm:
        """
        Create and return a Google ADK LiteLlm model configured for the internal API.
        
        This model can be used directly with Google ADK agents.
        
        Args:
            params: Optional dictionary containing:
                - experience_id: Experience ID for the request
                - model: Model name (default: uses config or "openai/custom")
                
        Returns:
            LiteLlm: Configured LiteLLM model instance for Google ADK.
            
        Example:
            ```python
            gateway = X42GatewayADK()
            llm = gateway.get_llm_model({"experience_id": "my-exp"})
            
            # Use with ADK agent
            agent = LlmAgent(model=llm, name="agent", instruction="...")
            ```
        """
        params = params or {}
        headers = self._build_headers(params)
        
        # Get model name from params or config
        model_name = params.get("model", "custom")
        
        # LiteLLM requires openai/ prefix for OpenAI-compatible endpoints
        if not model_name.startswith("openai/"):
            model_name = f"openai/{model_name}"
        
        cvs_logger.info(f"Creating LiteLlm model: {model_name} with base URL: {self.url}")
        
        llm = X42LiteLLMUsageModel(
            model=model_name,
            api_base=self.url,
            api_key="not-required",
            extra_headers=headers,
        )
        
        return llm

    def get_generation_config(self, params: Optional[dict] = None) -> types.GenerateContentConfig:
        """
        Create generation configuration for ADK content generation.
        
        Args:
            params: Optional dictionary containing:
                - temperature: Sampling temperature (default: 0.1)
                - max_tokens: Maximum output tokens (default: 4096)
                - top_p: Top-p sampling (default: None)
                - top_k: Top-k sampling (default: None)
                
        Returns:
            GenerateContentConfig: Configuration for content generation.
            
        Example:
            ```python
            gateway = X42GatewayADK()
            config = gateway.get_generation_config({"temperature": 0.7, "max_tokens": 1000})
            ```
        """
        params = params or {}
        return types.GenerateContentConfig(
            temperature=params.get("temperature", 0.1),
            max_output_tokens=params.get("max_tokens", 4096),
            top_p=params.get("top_p"),
            top_k=params.get("top_k"),
        )