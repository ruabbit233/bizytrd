from pathlib import Path
import tomllib


def test_sdk_config_reads_legacy_bizyair_comfyui_api_key(monkeypatch, tmp_path):
    from bizytrd_sdk import config as sdk_config

    api_key_file = tmp_path / "api_key.ini"
    api_key_file.write_text("[auth]\napi_key = legacy-key\n", encoding="utf-8")

    monkeypatch.delenv("BIZYTRD_API_KEY", raising=False)
    monkeypatch.delenv("BIZYAIR_API_KEY", raising=False)
    monkeypatch.delenv("BIZYTRD_API_KEY_PATH", raising=False)
    monkeypatch.setenv("BIZYAIR_COMFYUI_PATH", str(tmp_path))

    assert sdk_config.get_config().api_key == "legacy-key"


def test_core_config_is_sdk_config_shim(monkeypatch):
    from bizytrd_sdk.config import get_config as get_sdk_config
    from bizytrd.core.config import get_config as get_core_config

    monkeypatch.setenv("BIZYTRD_BASE_URL", "https://example.com/x/v1")
    monkeypatch.setenv("BIZYTRD_API_KEY", "sdk-key")
    monkeypatch.setenv("BIZYTRD_UPLOAD_BASE_URL", "https://upload.example.com")
    monkeypatch.setenv("BIZYTRD_TIMEOUT", "123")
    monkeypatch.setenv("BIZYTRD_POLLING_INTERVAL", "2.5")
    monkeypatch.setenv("BIZYTRD_MAX_POLLING_TIME", "456")

    sdk_config = get_sdk_config()
    assert get_core_config() == {
        "base_url": sdk_config.base_url,
        "api_key": sdk_config.api_key,
        "upload_base_url": sdk_config.upload_base_url,
        "timeout": sdk_config.timeout,
        "polling_interval": sdk_config.polling_interval,
        "max_polling_time": sdk_config.max_polling_time,
    }


def test_bizytrd_config_imports_top_level_sdk_package():
    project_root = Path(__file__).resolve().parents[1]
    source = (project_root / "core" / "config.py").read_text(encoding="utf-8")

    assert "..bizytrd_sdk" not in source
    assert "from bizytrd_sdk.config import" in source


def test_distribution_includes_top_level_sdk_until_external_package_exists():
    project_root = Path(__file__).resolve().parents[1]
    pyproject = tomllib.loads((project_root / "pyproject.toml").read_text(encoding="utf-8"))

    packages = pyproject["tool"]["setuptools"]["packages"]
    package_dir = pyproject["tool"]["setuptools"]["package-dir"]

    assert "bizytrd_sdk" in packages
    assert package_dir["bizytrd_sdk"] == "bizytrd_sdk"


def _clear_all_config_env(monkeypatch):
    for key in [
        "BIZYTRD_BASE_URL", "BIZYTRD_API_BASE_URL", "BIZYTRD_SERVER_URL",
        "BIZYAIR_TEST_TRD_BASE_URL", "BIZYAIR_DOMAIN", "BIZYAIR_API_BASE_URL",
        "BIZYAIR_X_SERVER", "BIZYTRD_API_KEY", "BIZYAIR_API_KEY",
        "BIZYTRD_UPLOAD_BASE_URL", "BIZYTRD_UPLOAD_URL",
        "BIZYTRD_TIMEOUT", "BIZYTRD_POLLING_INTERVAL", "BIZYTRD_MAX_POLLING_TIME",
        "BIZYTRD_API_KEY_PATH", "BIZYAIR_COMFYUI_PATH",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_test_mode_routes_uploads_to_bizyair_domain(monkeypatch):
    from bizytrd_sdk import config as sdk_config

    _clear_all_config_env(monkeypatch)
    monkeypatch.setenv("BIZYAIR_TEST_TRD_BASE_URL", "http://127.0.0.1:8888/x/v1")
    monkeypatch.setenv("BIZYAIR_DOMAIN", "https://uat-api.bizyair.cn")
    monkeypatch.setenv("BIZYAIR_API_KEY", "test-key")

    cfg = sdk_config.get_config()
    assert cfg.base_url == "http://127.0.0.1:8888/x/v1"
    assert cfg.upload_base_url == "https://uat-api.bizyair.cn/x/v1"


def test_test_mode_without_bizyair_domain_uses_default_upload(monkeypatch):
    from bizytrd_sdk import config as sdk_config

    _clear_all_config_env(monkeypatch)
    monkeypatch.setenv("BIZYAIR_TEST_TRD_BASE_URL", "http://127.0.0.1:8888/x/v1")
    monkeypatch.setenv("BIZYAIR_API_KEY", "test-key")

    cfg = sdk_config.get_config()
    assert cfg.base_url == "http://127.0.0.1:8888/x/v1"
    assert cfg.upload_base_url == sdk_config.DEFAULT_UPLOAD_BASE_URL


def test_bizytrd_base_url_override_keeps_upload_fallback_to_same_domain(monkeypatch):
    from bizytrd_sdk import config as sdk_config

    _clear_all_config_env(monkeypatch)
    monkeypatch.setenv("BIZYTRD_BASE_URL", "https://custom.example.com/x/v1")
    monkeypatch.setenv("BIZYAIR_TEST_TRD_BASE_URL", "http://127.0.0.1:8888/x/v1")
    monkeypatch.setenv("BIZYAIR_DOMAIN", "https://uat-api.bizyair.cn")
    monkeypatch.setenv("BIZYAIR_API_KEY", "test-key")

    cfg = sdk_config.get_config()
    assert cfg.base_url == "https://custom.example.com/x/v1"
    assert cfg.upload_base_url == "https://custom.example.com/x/v1"


def test_test_mode_explicit_upload_url_overrides_fallback(monkeypatch):
    from bizytrd_sdk import config as sdk_config

    _clear_all_config_env(monkeypatch)
    monkeypatch.setenv("BIZYAIR_TEST_TRD_BASE_URL", "http://127.0.0.1:8888/x/v1")
    monkeypatch.setenv("BIZYAIR_DOMAIN", "https://uat-api.bizyair.cn")
    monkeypatch.setenv("BIZYTRD_UPLOAD_BASE_URL", "https://explicit-upload.example.com/x/v1")
    monkeypatch.setenv("BIZYAIR_API_KEY", "test-key")

    cfg = sdk_config.get_config()
    assert cfg.base_url == "http://127.0.0.1:8888/x/v1"
    assert cfg.upload_base_url == "https://explicit-upload.example.com/x/v1"


def test_no_test_mode_uploads_follow_base_url(monkeypatch):
    from bizytrd_sdk import config as sdk_config

    _clear_all_config_env(monkeypatch)
    monkeypatch.setenv("BIZYAIR_DOMAIN", "https://uat-api.bizyair.cn")
    monkeypatch.setenv("BIZYAIR_API_KEY", "test-key")

    cfg = sdk_config.get_config()
    assert cfg.base_url == "https://uat-api.bizyair.cn/x/v1"
    assert cfg.upload_base_url == "https://uat-api.bizyair.cn/x/v1"
