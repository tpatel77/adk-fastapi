from typing import Any, Dict, Optional
from fastapi_common.util.rest_util import AsyncRestUtil
from fastapi_common.models.http_request import HttpRequest
from fastapi_common.config.app_config import get_application_config

config = get_application_config()
class CacheUtil:
    def __init__(self):
        # Check if config.APP and its nested keys exist
        if not config or not config.APP:
            return

        service_config = config.APP.get("service")
        if not service_config:
            return

        cache_config = service_config.get("cache")
        if not cache_config:
            return

        # Safely access 'get' and 'set' with null checks
        self._get = cache_config.get("get")
        self._set = cache_config.get("set")


    @classmethod
    async def get(
        cls, request_meta_data: Dict[str, Any], context: str, key: str
    ) -> Optional[Any]:
        """
        Retrieve data from the Redis cache using the `getdata` endpoint.
        :param request_meta_data: Metadata for the request (e.g., appName, lineOfBusiness, conversationID).
        :param context: The context for the cache (e.g., "entitlement_service").
        :param key: The key to retrieve.
        :return: The value associated with the key, or None if not found.
        """
        payload = {
            "requestMetaData": request_meta_data,
            "requestPayloadData": {
                "data": {"context": context, "data": [{"key": key}]}
            },
        }

        request = HttpRequest(
            url=cls._get["url"],
            headers={"Content-Type": "application/json"},
            json_data=payload,
            timeout=cls._get["timeout"],
        )

        try:
            response = await AsyncRestUtil.post(request)
            return response.body
        except Exception as exc:
            print(f"Error during GET operation: {exc}")
            return None

    @classmethod
    async def set(
        cls, request_meta_data: Dict[str, Any], context: str, key: str, value: str
    ) -> bool:
        """
        Store data in the Redis cache using the `setdata` endpoint.
        :param request_meta_data: Metadata for the request (e.g., appName, lineOfBusiness, conversationID).
        :param context: The context for the cache (e.g., "entitlement_service").
        :param key: The key to set.
        :param value: The value to associate with the key.
        :return: True if the operation was successful, False otherwise.
        """
        payload = {
            "requestMetaData": request_meta_data,
            "requestPayloadData": {
                "data": {"context": context, "data": [{"key": key, "value": value}]}
            },
        }

        request = HttpRequest(
            url=cls._set["url"],
            headers={"Content-Type": "application/json"},
            json_data=payload,
            timeout=cls._set["timeout"],
        )

        try:
            response = await AsyncRestUtil.post(request)
            return response.body
        except Exception as exc:
            print(f"Error during SET operation: {exc}")
            return False
