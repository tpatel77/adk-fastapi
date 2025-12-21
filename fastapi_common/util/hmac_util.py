import hmac
import hashlib
import base64
import time
from typing import Optional

class HmacUtil:
    def __init__(self, app_secret: Optional[str] = None):
        """
        :param app_secret: Optional app secret. If not provided, will look for 'app.client.hmac.key' in config.
        :param config: Optional config dictionary.
        """
        self.app_secret = app_secret
        # In-memory cache for HMAC tokens
        self._hmac_cache = {}

    def generate_hmac(self, app_secret: Optional[str] = None) -> dict:
        """
        Generate HMAC using current timestamp and app secret.
        :param app_secret: Optional app secret to override instance secret.
        :return: dict with appToken and appTokenTs
        """
        timestamp = str(int(time.time() * 1000))
        hmac_key = (
            app_secret or self.app_secret
        )
        if not hmac_key:
            raise ValueError("HMAC key is required")
        hmac_obj = hmac.new(
            hmac_key.encode("utf-8"), timestamp.encode("utf-8"), hashlib.sha256
        )
        encrypted_text = base64.b64encode(hmac_obj.digest()).decode("utf-8")
        return {"appToken": encrypted_text, "appTokenTs": timestamp}

    def get_cached_hmac(self, cache_key, ttl_seconds):
        """
        Retrieve a cached HMAC if valid, otherwise generate and cache a new one.
        """
        now = time.time()
        # Check if we have a valid cached value
        if cache_key in self._hmac_cache:
            value, expires_at = self._hmac_cache[cache_key]
            if now < expires_at:
                return value
        # Generate new HMAC and cache it
        value = self.generate_hmac()
        self._hmac_cache[cache_key] = (value, now + ttl_seconds)
        return value