from httpx import AsyncClient, ConnectTimeout, ReadTimeout, WriteTimeout, PoolTimeout, HTTPError, Timeout, Limits
from typing import Dict, Optional, Any, Union
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from fastapi_common.models.resource_execution_stats import ResourceExecutionStats
from fastapi_common.util.context_util import get_request_execution_ctx
from contextlib import asynccontextmanager
from fastapi_common.models.http_request import HttpRequest, TimeoutConfig
from fastapi_common.models.http_response import HttpResponse
import uuid

from fastapi_common.config.app_config import get_application_config

config = get_application_config()
rest_config = config.get("service", {}).get("rest", {})
RETRY_ATTEMPTS = rest_config.get("retry_attempts", 0)

# Connection pool defaults
_max_conns = rest_config.get("max_connections", 100)
_max_keepalive = rest_config.get("max_keepalive_connections", 20)
_keepalive_expiry = rest_config.get("keepalive_expiry", 5.0)

try:
    _max_conns = int(_max_conns)
except Exception:
    _max_conns = 100

try:
    _max_keepalive = int(_max_keepalive)
except Exception:
    _max_keepalive = 20
try:
    _keepalive_expiry = float(_keepalive_expiry)
except Exception:
    _keepalive_expiry = 5.0

DEFAULT_LIMITS = Limits(
    max_connections=_max_conns,
    max_keepalive_connections=_max_keepalive,
    keepalive_expiry=_keepalive_expiry,
)


class AsyncRestUtil:
    # Cache of clients keyed by (verify, max_connections, max_keepalive_connections, keepalive_expiry)
    _clients: Dict[tuple, AsyncClient] = {}
    ctx = get_request_execution_ctx()

    @classmethod
    def get_client(cls, verify: bool = True, limits_cfg: Optional[Any] = None) -> AsyncClient:
        """
        Return a shared AsyncClient based on TLS verify and limits configuration.
        Clients are cached and reused per (verify, limits) combination.
        """
        # Build limits: prefer provided limits_cfg, else defaults from config
        limits = Limits(
                max_connections=getattr(limits_cfg, "max_connections", DEFAULT_LIMITS.max_connections),
                max_keepalive_connections=getattr(limits_cfg, "max_keepalive_connections", DEFAULT_LIMITS.max_keepalive_connections),
                keepalive_expiry=getattr(limits_cfg, "keepalive_expiry", DEFAULT_LIMITS.keepalive_expiry),
            )

        key = (
            bool(verify),
            limits.max_connections,
            limits.max_keepalive_connections,
            limits.keepalive_expiry,
        )
        client = cls._clients.get(key)
        if client is None:
            client = AsyncClient(verify=verify, limits=limits)
            cls._clients[key] = client
        return client

    @classmethod
    async def close_client(cls):
        if cls._clients:
            for c in cls._clients.values():
                try:
                    await c.aclose()
                except Exception:
                    pass
            cls._clients.clear()

    @staticmethod
    def retry_policy():
        return retry(
            stop=stop_after_attempt(RETRY_ATTEMPTS), 
            wait=wait_exponential(multiplier=1, min=1, max=3),
            retry=retry_if_exception_type(ConnectTimeout),
        )

    @staticmethod
    @asynccontextmanager
    async def async_client_context():
        client = AsyncClient()
        try:
            yield client
        finally:
            await client.aclose()

    @staticmethod
    def _build_limits(limits_cfg) -> Optional[Limits]:
        """
        Build httpx.Limits from a LimitsConfig-like object.
        Returns None if limits_cfg is falsy.
        """
        if not limits_cfg:
            return None
        return Limits(
            max_connections=limits_cfg.max_connections,
            max_keepalive_connections=limits_cfg.max_keepalive_connections,
            keepalive_expiry=limits_cfg.keepalive_expiry,
        )

    @staticmethod
    def get_request_execution_ctx() -> ResourceExecutionStats:
        return get_request_execution_ctx()

    @staticmethod
    def get_grid() -> str:
        ctx = AsyncRestUtil.get_request_execution_ctx()
        return ctx.requestId if ctx and ctx.requestId else str(uuid.uuid4())

    @staticmethod
    def default_headers() -> dict:
        return {"Content-Type": "application/json", "x-grid": AsyncRestUtil.get_grid()}

    @staticmethod
    def _create_timeout_config(timeout: Union[int, float, TimeoutConfig]) -> Timeout:
        """
        Convert timeout configuration to HTTPX Timeout object.
        
        Args:
            timeout: int/float for uniform timeout or TimeoutConfig for granular control
            
        Returns:
            HTTPX Timeout object
        """
        if isinstance(timeout, (int, float)):
            # Backward compatibility: uniform timeout for all operations
            return Timeout(timeout)
        else:
            # TimeoutConfig - granular timeout configuration
            return Timeout(
                connect=timeout.connect,
                read=timeout.read,
                write=timeout.write,
                pool=timeout.pool
            )

    @staticmethod
    def get_downstream_request_headers(received_headers) -> Dict[str, str]:
        if received_headers is None:
            return AsyncRestUtil.default_headers()
        
        return {**AsyncRestUtil.default_headers(), **received_headers}

    @classmethod
    @retry_policy()
    async def get(cls, request: HttpRequest) -> HttpResponse:
        client = cls.get_client(verify=request.verify, limits_cfg=getattr(request, "limits", None))
        headers = AsyncRestUtil.get_downstream_request_headers(request.headers or {})
        timeout_config = cls._create_timeout_config(request.timeout)
        response = await client.get(
            request.url, headers=headers, params=request.params, timeout=timeout_config
        )
        response.raise_for_status()
        return HttpResponse(
            status_code=response.status_code,
            headers=dict(response.headers),
            body=response.json(),
        )

    @classmethod
    @retry_policy()
    async def post(cls, request: HttpRequest) -> HttpResponse:
        client = cls.get_client(verify=request.verify, limits_cfg=getattr(request, "limits", None))
        headers = AsyncRestUtil.get_downstream_request_headers(request.headers or {})
        timeout_config = cls._create_timeout_config(request.timeout)
        response = await client.post(
            request.url,
            headers=headers,
            data=request.data,
            json=request.json_data,
            timeout=timeout_config,
        )
        response.raise_for_status()
        return HttpResponse(
            status_code=response.status_code,
            headers=dict(response.headers),
            body=response.json(),
        )

    @classmethod
    @retry_policy()
    async def put(cls, request: HttpRequest) -> HttpResponse:
        client = cls.get_client(verify=request.verify, limits_cfg=getattr(request, "limits", None))
        headers = AsyncRestUtil.get_downstream_request_headers(request.headers or {})
        timeout_config = cls._create_timeout_config(request.timeout)
        response = await client.put(
            request.url,
            headers=headers,
            data=request.data,
            json=request.json_data,
            timeout=timeout_config,
        )
        response.raise_for_status()
        return HttpResponse(
            status_code=response.status_code,
            headers=dict(response.headers),
            body=response.json(),
        )

    @classmethod
    @retry_policy()
    async def delete(cls, request: HttpRequest) -> HttpResponse:
        client = cls.get_client(verify=request.verify, limits_cfg=getattr(request, "limits", None))
        headers = AsyncRestUtil.get_downstream_request_headers(request.headers or {})
        timeout_config = cls._create_timeout_config(request.timeout)
        response = await client.delete(
            request.url, headers=headers, timeout=timeout_config
        )
        response.raise_for_status()
        return HttpResponse(
            status_code=response.status_code,
            headers=dict(response.headers),
            body=response.json(),
        )
