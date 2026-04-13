"""ComfyUI-specific configuration loading for bizytrd.

This module contains the ComfyUI-specific logic for discovering API keys
and building a BizyTRDConfig / BizyTRDClient.  The generic config
defaults and helpers live in bizytrd_sdk.config.
"""

from __future__ import annotations

import configparser
import os
from pathlib import Path

from bizytrd_sdk import BizyTRDClient
from bizytrd_sdk.config import (
    DEFAULT_API_BASE_URL,
    DEFAULT_MAX_POLLING_TIME,
    DEFAULT_POLLING_INTERVAL,
    DEFAULT_TIMEOUT,
    BizyTRDConfig,
    _normalize_upload_base_url,
    _safe_float,
    _safe_int,
)


def _plugin_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _bizyair_comfyui_path() -> Path | None:
    env_path = os.getenv("BIZYAIR_COMFYUI_PATH")
    if env_path:
        return Path(env_path).expanduser()
    return None


def _candidate_api_key_paths() -> list[Path]:
    plugin_root = _plugin_root()
    bizyair_comfyui_path = _bizyair_comfyui_path()
    candidates = [
        bizyair_comfyui_path / "api_key.ini" if bizyair_comfyui_path else None,
        plugin_root.parent / "ComfyUI" / "custom_nodes" / "BizyAir" / "api_key.ini",
        plugin_root / "api_key.ini",
        plugin_root.parent / "api_key.ini",
        plugin_root.parent.parent / "api_key.ini",
        Path.cwd() / "api_key.ini",
        Path.cwd() / "ComfyUI" / "custom_nodes" / "BizyAir" / "api_key.ini",
    ]
    ordered: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        if path is None:
            continue
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(path)
    return ordered


def _load_api_key_file() -> str:
    for path in _candidate_api_key_paths():
        if not path.exists() or not path.is_file():
            continue
        config = configparser.ConfigParser()
        config.read(path, encoding="utf-8")
        api_key = config.get("auth", "api_key", fallback="").strip().strip("'\"")
        if api_key:
            return api_key
    return ""


def _load_dotenv() -> dict[str, str]:
    env_path = _plugin_root() / "config" / ".env"
    if not env_path.exists():
        return {}

    values: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _shared_bizyair_base_url(env_values: dict[str, str]) -> str:
    direct_base_url = (
        os.getenv("BIZYAIR_API_BASE_URL")
        or env_values.get("BIZYAIR_API_BASE_URL")
        or os.getenv("BIZYAIR_X_SERVER")
        or env_values.get("BIZYAIR_X_SERVER")
    )
    if direct_base_url:
        return str(direct_base_url).strip().rstrip("/")

    domain = os.getenv("BIZYAIR_DOMAIN") or env_values.get("BIZYAIR_DOMAIN")
    if domain:
        return f"{str(domain).strip().rstrip('/')}/x/v1"
    return ""


def get_config() -> BizyTRDConfig:
    """Build a BizyTRDConfig using ComfyUI-specific discovery logic."""
    env_values = _load_dotenv()
    bizyair_base_url = _shared_bizyair_base_url(env_values)

    api_base_url = (
        os.getenv("BIZYTRD_API_BASE_URL")
        or env_values.get("BIZYTRD_API_BASE_URL")
        or bizyair_base_url
        or DEFAULT_API_BASE_URL
    )
    api_key = (
        os.getenv("BIZYAIR_API_KEY")
        or env_values.get("BIZYAIR_API_KEY")
        or os.getenv("BIZYTRD_API_KEY")
        or env_values.get("BIZYTRD_API_KEY")
        or _load_api_key_file()
        or ""
    )
    upload_base_url = (
        os.getenv("BIZYTRD_UPLOAD_BASE_URL")
        or env_values.get("BIZYTRD_UPLOAD_BASE_URL")
        or api_base_url
    )

    return {
        "base_url": str(api_base_url).rstrip("/"),
        "api_key": str(api_key).strip(),
        "upload_base_url": _normalize_upload_base_url(upload_base_url, api_base_url),
        "timeout": _safe_int(
            os.getenv("BIZYTRD_TIMEOUT")
            or env_values.get("BIZYTRD_TIMEOUT")
            or DEFAULT_TIMEOUT,
            DEFAULT_TIMEOUT,
        ),
        "polling_interval": _safe_float(
            os.getenv("BIZYTRD_POLLING_INTERVAL")
            or env_values.get("BIZYTRD_POLLING_INTERVAL")
            or DEFAULT_POLLING_INTERVAL,
            DEFAULT_POLLING_INTERVAL,
        ),
        "max_polling_time": _safe_int(
            os.getenv("BIZYTRD_MAX_POLLING_TIME")
            or env_values.get("BIZYTRD_MAX_POLLING_TIME")
            or DEFAULT_MAX_POLLING_TIME,
            DEFAULT_MAX_POLLING_TIME,
        ),
    }


def create_client() -> BizyTRDClient:
    """Create a BizyTRDClient from ComfyUI-specific config."""
    config = get_config()
    return BizyTRDClient(
        api_key=config["api_key"],
        base_url=config["base_url"],
        upload_base_url=config["upload_base_url"],
        timeout=config["timeout"],
        polling_interval=config["polling_interval"],
        max_polling_time=config["max_polling_time"],
    )
