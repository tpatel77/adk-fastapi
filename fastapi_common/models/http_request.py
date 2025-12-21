from typing import Dict, Optional, Any, Union
from pydantic import BaseModel, Field


class TimeoutConfig(BaseModel):
    """
    Granular timeout configuration for HTTP requests.
    
    Timeout Types:
    - connect: Time to establish socket connection (default: 1s)
    - read: Time to receive response data (default: 4s)
    - write: Time to send request data (default: 6s)
    - pool: Time to acquire connection from pool (default: 4s)
    
    All values are in SECONDS, not milliseconds.
    """
    connect: float = Field(default=1.0, ge=0.1, le=300.0)
    read: float = Field(default=4.0, ge=0.1, le=3600.0)
    write: float = Field(default=6.0, ge=0.1, le=3600.0)
    pool: float = Field(default=4.0, ge=0.1, le=60.0)


class LimitsConfig(BaseModel):
    """
    Connection pool limits configuration analogous to httpx.Limits.

    - max_connections: Max concurrent connections across all hosts.
    - max_keepalive_connections: Max idle keep-alive connections to keep pooled.
    - keepalive_expiry: Seconds to keep idle connections alive.
    """
    max_connections: Optional[int] = Field(default=None, ge=1)
    max_keepalive_connections: Optional[int] = Field(default=None, ge=0)
    keepalive_expiry: Optional[float] = Field(default=None, ge=0.0)


class HttpRequest(BaseModel):
    """
    HTTP request configuration with enhanced timeout support.
    
    Supports both legacy timeout (int/float) and granular TimeoutConfig.
    """
    url: str
    headers: Optional[Dict[str, Optional[str]]] = None
    params: Optional[Dict[str, Any]] = None
    data: Optional[Dict[str, Any]] = None
    json_data: Optional[Dict[str, Any]] = None
    timeout: Union[int, float, TimeoutConfig] = Field(default=TimeoutConfig())
    verify: bool = True
    limits: Optional[LimitsConfig] = None
