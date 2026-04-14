"""Configuration helpers for the BizyTRD SDK."""

from __future__ import annotations

import configparser
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_API_BASE_URL = "https://uat-api.bizyair.cn/x/v1"
DEFAULT_UPLOAD_BASE_URL = "https://uat-api.bizyair.cn/x/v1"
DEFAULT_TIMEOUT = 60
DEFAULT_POLLING_INTERVAL = 10.0
DEFAULT_MAX_POLLING_TIME = 3600

version_path = Path(__file__).resolve().parent.parent / "version.txt"
try:
    CLIENT_VERSION = version_path.read_text(encoding="utf-8").strip()
except FileNotFoundError:
    CLIENT_VERSION = "0.1.0"


@dataclass(slots=True)
class SDKConfig:
    base_url: str
    api_key: str = ""
    upload_base_url: str = DEFAULT_UPLOAD_BASE_URL
    timeout: int = DEFAULT_TIMEOUT
    polling_interval: float = DEFAULT_POLLING_INTERVAL
    max_polling_time: int = DEFAULT_MAX_POLLING_TIME


def _candidate_api_key_paths() -> list[Path]:
    candidates = [
        (
            Path(os.getenv("BIZYTRD_API_KEY_PATH")).expanduser()
            if os.getenv("BIZYTRD_API_KEY_PATH")
            else None
        ),
        Path.cwd() / "api_key.ini",
        Path.home() / ".config" / "bizytrd" / "api_key.ini",
        Path.home() / ".bizytrd" / "api_key.ini",
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
        parser = configparser.ConfigParser()
        parser.read(path, encoding="utf-8")
        api_key = parser.get("auth", "api_key", fallback="").strip().strip("'\"")
        if api_key:
            return api_key
    return ""


def _legacy_bizyair_base_url() -> str:
    direct_base_url = os.getenv("BIZYAIR_API_BASE_URL") or os.getenv("BIZYAIR_X_SERVER")
    if direct_base_url:
        return str(direct_base_url).strip().rstrip("/")

    domain = os.getenv("BIZYAIR_DOMAIN")
    if domain:
        return f"{str(domain).strip().rstrip('/')}/x/v1"
    return ""


def _normalize_upload_base_url(upload_base_url: str, api_base_url: str) -> str:
    text = str(upload_base_url or api_base_url).rstrip("/")
    if text.endswith("/x/v1"):
        return text

    parsed = urlparse(text)
    if parsed.scheme and parsed.netloc and parsed.path in {"", "/"}:
        return f"{text}/x/v1"
    return text


def get_config() -> SDKConfig:
    """Resolve SDK config from environment variables and optional local api_key.ini.

    Priority:
    1. `BIZYTRD_*`
    2. legacy `BIZYAIR_*` compatibility fallbacks
    3. local `api_key.ini`
    4. built-in defaults
    """

    legacy_bizyair_base_url = _legacy_bizyair_base_url()

    api_base_url = (
        os.getenv("BIZYTRD_BASE_URL")
        or os.getenv("BIZYTRD_API_BASE_URL")
        or os.getenv("BIZYTRD_SERVER_URL")
        or os.getenv("BIZYAIR_TEST_TRD_BASE_URL")
        or legacy_bizyair_base_url
        or DEFAULT_API_BASE_URL
    )
    api_key = (
        os.getenv("BIZYTRD_API_KEY")
        or os.getenv("BIZYAIR_API_KEY")
        or _load_api_key_file()
        or ""
    )
    upload_base_url = (
        os.getenv("BIZYTRD_UPLOAD_BASE_URL")
        or os.getenv("BIZYTRD_UPLOAD_URL")
        or api_base_url
    )

    return SDKConfig(
        base_url=str(api_base_url).rstrip("/"),
        api_key=str(api_key).strip(),
        upload_base_url=_normalize_upload_base_url(upload_base_url, api_base_url),
        timeout=int(os.getenv("BIZYTRD_TIMEOUT") or DEFAULT_TIMEOUT),
        polling_interval=float(
            os.getenv("BIZYTRD_POLLING_INTERVAL") or DEFAULT_POLLING_INTERVAL
        ),
        max_polling_time=int(
            os.getenv("BIZYTRD_MAX_POLLING_TIME") or DEFAULT_MAX_POLLING_TIME
        ),
    )
