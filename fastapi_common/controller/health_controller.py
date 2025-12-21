import http
from typing import Any

from fastapi import APIRouter

from fastapi_common.config.app_config import get_application_config

config = get_application_config()
router = APIRouter(prefix=f"{config.get('info.app.context-path')}")


@router.get("/health", status_code=http.HTTPStatus.OK)
async def get_health_check() -> Any:
    """Health Check Endpoint"""
    return "hello"
