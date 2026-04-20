"""Compatibility shim for bizytrd node configuration.

Network configuration is resolved by bizytrd_sdk.config. The node layer keeps this
module only so existing call sites can read a dict-shaped configuration.
"""

from __future__ import annotations

from typing import Any

from bizytrd_sdk.config import get_config as get_sdk_config


def get_config() -> dict[str, Any]:
    config = get_sdk_config()
    return {
        "base_url": config.base_url,
        "api_key": config.api_key,
        "upload_base_url": config.upload_base_url,
        "timeout": config.timeout,
        "polling_interval": config.polling_interval,
        "max_polling_time": config.max_polling_time,
    }
