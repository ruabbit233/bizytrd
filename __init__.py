"""bizytrd reusable package exports for BizyAir integration."""

from __future__ import annotations

import logging
import shutil
import sys
from pathlib import Path

__version__ = "0.1.0"
_PACKAGE_ROOT = Path(__file__).resolve().parent

# In ComfyUI/custom_nodes source layouts, only the parent of this package may be
# on sys.path. Keep the local top-level bizytrd_sdk importable until it is
# installed as an external package.
_package_root_text = str(_PACKAGE_ROOT)
if _package_root_text not in sys.path:
    sys.path.insert(0, _package_root_text)

from .nodes.node_factory import create_all_nodes


def get_node_mappings() -> tuple[dict[str, type], dict[str, str]]:
    return create_all_nodes()


def get_web_directory() -> Path:
    return _PACKAGE_ROOT / "web"


def sync_web_assets(target_dir: str | Path, *, subdir: str = "bizytrd") -> Path:
    source_root = get_web_directory() / "js"
    destination_root = Path(target_dir).expanduser().resolve() / subdir
    try:
        destination_root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logging.warning(
            "bizytrd web asset sync skipped because '%s' is not writable: %s",
            destination_root,
            exc,
        )
        return destination_root

    if not source_root.is_dir():
        return destination_root

    for source_path in source_root.rglob("*"):
        if not source_path.is_file():
            continue
        relative_path = source_path.relative_to(source_root)
        destination_path = destination_root / relative_path
        try:
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            if (
                destination_path.exists()
                and destination_path.read_bytes() == source_path.read_bytes()
            ):
                continue
            shutil.copy2(source_path, destination_path)
        except OSError as exc:
            logging.warning(
                "bizytrd web asset sync skipped for '%s': %s",
                destination_path,
                exc,
            )
    return destination_root

__all__ = [
    "__version__",
    "get_node_mappings",
    "get_web_directory",
    "sync_web_assets",
]
