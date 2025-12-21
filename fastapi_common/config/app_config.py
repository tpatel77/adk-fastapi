import logging
import os
from functools import lru_cache
from functools import reduce

import yaml
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

yaml_settings: dict = {}

_config_base = os.environ.get("CONFIGBASEPATH")
_candidates: list[str] = []
if _config_base:
    _candidates.append(os.path.join(_config_base, "application.yaml"))
_candidates.append(os.path.join(os.getcwd(), "config", "application.yaml"))
_candidates.append(os.path.join(os.getcwd(), "application.yaml"))

for _path in _candidates:
    try:
        if os.path.exists(_path):
            with open(_path, "r") as stream:
                yaml_settings = dict(yaml.safe_load(stream) or {})
            break
    except OSError as e:
        print(f"Unable to open application yaml file: {e}")
    except Exception as ex:
        print(f"Unknown Exception in loading application yaml file : {ex}")

env_settings = dict(os.environ)
yaml_settings.update(env_settings)


class Settings(BaseSettings):
    """Application Config Settings"""

    APP: dict = yaml_settings

    def get(self, keys: str, default=None):
        value = deep_get(yaml_settings, keys, default)
        # if value contains "${", replace it with environment variable
        if isinstance(value, str) and "${" in value:
            start_idx = value.index("${") + 2
            end_idx = value.index("}", start_idx)
            env_var = value[start_idx:end_idx]
            env_value = os.getenv(env_var, "")
            value = value.replace(f"${{{env_var}}}", env_value)
        return value

    def has_checkpointer(self) -> bool:
        """Return True if checkpointer config is present."""
        return self.APP.get("checkpointer", {}).get("type") is not None

    def get_llm_gateway_config(self) -> dict:
        """Return the llm_gateway config section."""
        return self.APP.get("service", {}).get("llm_gateway", {})

    def get_service(self, service_name: str) -> dict:
        """Return a specific service config by name."""
        return self.APP.get("service", {}).get(service_name, {})

    def is_cache_enabled(self) -> bool:
        """Return True if cache is enabled."""
        return self.get_cache_config().get("enabled", False)


settings = Settings()


@lru_cache()
def get_application_config():
    """Get Application Config"""
    return settings


def deep_get(dictionary, keys, default=None):
    """Deep Get Function to Flatten nested dictionary structure"""
    return reduce(
        lambda d, key: d.get(key, default) if isinstance(d, dict) else default,
        keys.split("."),
        dictionary,
    )


def filter_maker(level):
    """Filter Maker For Application Logging"""
    level = getattr(logging, level)

    def filter(record):
        return record.levelno <= level

    return filter
