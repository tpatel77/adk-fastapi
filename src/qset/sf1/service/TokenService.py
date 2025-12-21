"""Token Service - Manages OAuth2 token generation and refresh for CVS API."""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import httpx
from fastapi import HTTPException
from src.common.config.AppConfig import get_application_config
from src.common.util.LoggerUtil import LoggerUtil
from src.common.models.CvsEventEnum import CvsEventEnum

logger = logging.getLogger(__name__)
class TokenService:
    """Service class for managing OAuth2 tokens with automatic refresh."""
    
    DEFAULT_REFRESH_INTERVAL_SECONDS = 720
    
    
    _instance: Optional['TokenService'] = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        """Singleton pattern to ensure only one instance exists."""
        if cls._instance is None:
            cls._instance = super(TokenService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize token service."""
        LoggerUtil.logMessage(CvsEventEnum.ENTRY, "TokenService.__init__")
        if self._initialized:
            LoggerUtil.logMessage(CvsEventEnum.EXIT, "TokenService.__init__ (already initialized)")
            return
            
        self._token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
        self._token_acquired_at: Optional[datetime] = None
        self._load_configuration()
        self._initialized = True
        LoggerUtil.logMessage(CvsEventEnum.INFO, "TokenService initialized")
        LoggerUtil.logMessage(CvsEventEnum.EXIT, "TokenService.__init__ completed")

    def _load_configuration(self) -> None:
        """Load TokenService configuration from application settings."""

        self._token_url = get_application_config().get("sf1.token_service.token_url")
        self._api_key = get_application_config().get("sf1.token_service.api_key")
        self._client_id = get_application_config().get("sf1.token_service.client_id")
        self._client_secret = get_application_config().get("sf1.token_service.client_secret")

        refresh_interval_raw = get_application_config().get("sf1.token_service.token_refresh_interval_seconds")
        try:
            self._token_ttl_seconds = int(refresh_interval_raw)
        except (TypeError, ValueError):
            logger.warning(
                "Invalid refresh_interval_seconds '%s'. Falling back to default %s seconds.",
                refresh_interval_raw,
                self.DEFAULT_REFRESH_INTERVAL_SECONDS,
            )
            self._token_ttl_seconds = self.DEFAULT_REFRESH_INTERVAL_SECONDS

        missing_fields = [
            field_name
            for field_name, value in {
                "token_url": self._token_url,
                "api_key": self._api_key,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            }.items()
            if not value
        ]

        if missing_fields:
            LoggerUtil.logMessage(
                CvsEventEnum.ERROR,
                f"TokenService configuration missing fields: {', '.join(missing_fields)}"
            )
            raise ValueError(
                f"TokenService configuration missing required fields: {', '.join(missing_fields)}"
            )
        LoggerUtil.logMessage(CvsEventEnum.EXIT, "TokenService._load_configuration completed")
    
    async def get_token(self) -> str:
        """
        Get valid OAuth2 token. Fetches new token if not available or expired.
        
        Returns:
            str: Valid OAuth2 bearer token
            
        Raises:
            HTTPException: If token generation fails
        """
        LoggerUtil.logMessage(CvsEventEnum.ENTRY, "TokenService.get_token")
        async with self._lock:
            if self._is_token_valid():
                LoggerUtil.logMessage(CvsEventEnum.INFO, "TokenService returning cached token")
                LoggerUtil.logMessage(CvsEventEnum.EXIT, "TokenService.get_token (cache hit)")
                return self._token
            
            LoggerUtil.logMessage(
                CvsEventEnum.INFO, "TokenService token not available or expired; fetching new token"
            )
            await self._fetch_new_token()
            LoggerUtil.logMessage(CvsEventEnum.EXIT, "TokenService.get_token (fetched new token)")
            return self._token
    
    def _is_token_valid(self) -> bool:
        """
        Check if current token is valid and not expired.
        
        Returns:
            bool: True if token is valid, False otherwise
        """
        if self._token is None or self._token_expiry is None:
            LoggerUtil.logMessage(CvsEventEnum.INFO, "TokenService token not available in memory")
            return False
        
        if datetime.now() >= self._token_expiry:
            LoggerUtil.logMessage(CvsEventEnum.INFO, "TokenService cached token has expired")
            return False
        
        return True
    
    async def _fetch_new_token(self) -> None:
        """
        Fetch new OAuth2 token from CVS API.
        
        Raises:
            HTTPException: If token generation fails
        """
        LoggerUtil.logMessage(CvsEventEnum.ENTRY, "TokenService._fetch_new_token")
        LoggerUtil.logMessage(CvsEventEnum.INFO, "TokenService fetching new OAuth2 token from CVS API")
        
        headers = {
            "x-api-key": self._api_key,
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self._token_url,
                    headers=headers,
                    data=data
                )
                
                if response.status_code != 200:
                    error_msg = f"Token generation failed with status {response.status_code}: {response.text}"
                    logger.error(error_msg)
                    raise HTTPException(status_code=502, detail=error_msg)
                
                token_data = response.json()
                self._token = token_data.get("access_token")
                
                if not self._token:
                    error_msg = "Access token not found in response"
                    logger.error(f"{error_msg}. Response: {token_data}")
                    raise HTTPException(status_code=502, detail=error_msg)
                
                self._token_acquired_at = datetime.now()
                self._token_expiry = self._token_acquired_at + timedelta(
                    seconds=self._token_ttl_seconds
                )
                
                LoggerUtil.logMessage(
                    CvsEventEnum.INFO,
                    f"Successfully fetched new token. Cached for {self._token_ttl_seconds} seconds. "
                    f"Will refresh at {self._token_expiry.isoformat()}",
                )
                LoggerUtil.logMessage(
                    CvsEventEnum.INFO,
                    f"TokenService fetched token expiring at {self._token_expiry.isoformat()}"
                )
                
        except httpx.TimeoutException as e:
            error_msg = f"Token API request timed out: {str(e)}"
            logger.error(error_msg, exc_info=True)
            LoggerUtil.logMessage(CvsEventEnum.ERROR, error_msg)
            raise HTTPException(status_code=504, detail=error_msg)
        
        except httpx.RequestError as e:
            error_msg = f"Failed to connect to token API: {str(e)}"
            logger.error(error_msg, exc_info=True)
            LoggerUtil.logMessage(CvsEventEnum.ERROR, error_msg)
            raise HTTPException(status_code=502, detail=error_msg)
        
        except HTTPException:
            LoggerUtil.logMessage(CvsEventEnum.ERROR, "HTTPException raised in _fetch_new_token")
            raise
        
        except Exception as e:
            error_msg = f"Unexpected error fetching token: {str(e)}"
            logger.error(error_msg, exc_info=True)
            LoggerUtil.logMessage(CvsEventEnum.ERROR, error_msg)
            raise HTTPException(status_code=500, detail=error_msg)
        finally:
            LoggerUtil.logMessage(CvsEventEnum.EXIT, "TokenService._fetch_new_token completed")
    
    def get_token_info(self) -> Dict[str, Any]:
        """
        Get current token information for debugging/monitoring.
        
        Returns:
            Dict containing token status information
        """
        LoggerUtil.logMessage(CvsEventEnum.ENTRY, "TokenService.get_token_info")
        info = {
            "has_token": self._token is not None,
            "is_valid": self._is_token_valid(),
            "expiry": self._token_expiry.isoformat() if self._token_expiry else None,
            "cache_ttl_seconds": self._token_ttl_seconds,
        }
        LoggerUtil.logMessage(CvsEventEnum.EXIT, "TokenService.get_token_info")
        return info
    
    async def force_refresh(self) -> str:
        """
        Force immediate token refresh regardless of expiry.
        
        Returns:
            str: New OAuth2 bearer token
            
        Raises:
            HTTPException: If token generation fails
        """
        LoggerUtil.logMessage(CvsEventEnum.ENTRY, "TokenService.force_refresh")
        async with self._lock:
            await self._fetch_new_token()
        LoggerUtil.logMessage(CvsEventEnum.EXIT, "TokenService.force_refresh completed")
        return self._token
    
    def clear_token(self) -> None:
        """Clear token from memory (for testing or security purposes)."""
        LoggerUtil.logMessage(CvsEventEnum.ENTRY, "TokenService.clear_token")
        logger.info("Clearing token from memory")
        self._token = None
        self._token_expiry = None
        LoggerUtil.logMessage(CvsEventEnum.EXIT, "TokenService.clear_token completed")


def get_token_service() -> TokenService:
    """
    Get singleton instance of TokenService.
    
    Returns:
        TokenService: Singleton token service instance
    """
    return TokenService()
