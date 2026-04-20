"""Configuration helpers for the BizyTRD SDK."""

from __future__ import annotations

import configparser
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from ._version import __version__

DEFAULT_API_BASE_URL = "https://uat-api.bizyair.cn/x/v1"
DEFAULT_UPLOAD_BASE_URL = "https://uat-api.bizyair.cn/x/v1"
DEFAULT_TIMEOUT = 60
DEFAULT_POLLING_INTERVAL = 10.0
DEFAULT_MAX_POLLING_TIME = 3600
CLIENT_VERSION = __version__


@dataclass(slots=True)
class SDKConfig:
    base_url: str
    api_key: str = ""
    upload_base_url: str = DEFAULT_UPLOAD_BASE_URL
    timeout: int = DEFAULT_TIMEOUT
    polling_interval: float = DEFAULT_POLLING_INTERVAL
    max_polling_time: int = DEFAULT_MAX_POLLING_TIME


def _package_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _bizyair_comfyui_path() -> Path | None:
    env_path = os.getenv("BIZYAIR_COMFYUI_PATH")
    if env_path:
        return Path(env_path).expanduser()
    return None


def _candidate_api_key_paths() -> list[Path]:
    package_root = _package_root()
    bizyair_comfyui_path = _bizyair_comfyui_path()
    candidates = [
        (
            Path(os.getenv("BIZYTRD_API_KEY_PATH")).expanduser()
            if os.getenv("BIZYTRD_API_KEY_PATH")
            else None
        ),
        bizyair_comfyui_path / "api_key.ini" if bizyair_comfyui_path else None,
        package_root.parent / "ComfyUI" / "custom_nodes" / "BizyAir" / "api_key.ini",
        package_root / "api_key.ini",
        package_root.parent / "api_key.ini",
        package_root.parent.parent / "api_key.ini",
        Path.cwd() / "api_key.ini",
        Path.cwd() / "ComfyUI" / "custom_nodes" / "BizyAir" / "api_key.ini",
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


def _load_dotenv() -> dict[str, str]:
    env_path = _package_root() / "config" / ".env"
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


def _env(name: str, env_values: dict[str, str]) -> str | None:
    return os.getenv(name) or env_values.get(name)


def _legacy_bizyair_base_url(env_values: dict[str, str]) -> str:
    direct_base_url = (
        _env("BIZYAIR_API_BASE_URL", env_values)
        or _env("BIZYAIR_X_SERVER", env_values)
    )
    if direct_base_url:
        return str(direct_base_url).strip().rstrip("/")

    domain = _env("BIZYAIR_DOMAIN", env_values)
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

    env_values = _load_dotenv()
    legacy_bizyair_base_url = _legacy_bizyair_base_url(env_values)

    api_base_url = (
        _env("BIZYTRD_BASE_URL", env_values)
        or _env("BIZYTRD_API_BASE_URL", env_values)
        or _env("BIZYTRD_SERVER_URL", env_values)
        or _env("BIZYAIR_TEST_TRD_BASE_URL", env_values)
        or legacy_bizyair_base_url
        or DEFAULT_API_BASE_URL
    )
    api_key = (
        _env("BIZYTRD_API_KEY", env_values)
        or _env("BIZYAIR_API_KEY", env_values)
        or _load_api_key_file()
        or ""
    )
    upload_base_url = (
        _env("BIZYTRD_UPLOAD_BASE_URL", env_values)
        or _env("BIZYTRD_UPLOAD_URL", env_values)
        or api_base_url
    )

    return SDKConfig(
        base_url=str(api_base_url).rstrip("/"),
        api_key=str(api_key).strip(),
        upload_base_url=_normalize_upload_base_url(upload_base_url, api_base_url),
        timeout=int(_env("BIZYTRD_TIMEOUT", env_values) or DEFAULT_TIMEOUT),
        polling_interval=float(
            _env("BIZYTRD_POLLING_INTERVAL", env_values) or DEFAULT_POLLING_INTERVAL
        ),
        max_polling_time=int(
            _env("BIZYTRD_MAX_POLLING_TIME", env_values) or DEFAULT_MAX_POLLING_TIME
        ),
    )
