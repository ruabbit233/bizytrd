"""Add channel param to registry entries whose model_name lacks 'base' or 'official'.

Reads models_registry.json, and for every entry whose model_name does not
contain "base" or "official" (case-insensitive), prepends the channel param
to its params list — unless the entry already has one.

Usage:
    python scripts/add_channel_param.py            # dry-run (default)
    python scripts/add_channel_param.py --write     # write changes
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REGISTRY_PATH = Path(__file__).resolve().parent.parent / "models_registry.json"

CHANNEL_PARAM = {
    "name": "channel",
    "type": "LIST",
    "required": True,
    "options": ["base", "official"],
    "description": "模型供应渠道。base表示第三方渠道，official表示官方渠道。",
    "fieldKey": "channel",
    "default": "official",
}


def _needs_channel(model_name: str) -> bool:
    lower = model_name.lower()
    return "base" not in lower and "official" not in lower


def _has_channel(params: list[dict]) -> bool:
    return any(p.get("name") == "channel" for p in params)


def run(write: bool = False) -> None:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))

    added = 0
    skipped_already = 0
    skipped_exempt = 0

    for entry in registry:
        model_name = entry.get("model_name", "")
        params = entry.setdefault("params", [])

        if not _needs_channel(model_name):
            skipped_exempt += 1
            continue

        if _has_channel(params):
            skipped_already += 1
            continue

        params.insert(0, dict(CHANNEL_PARAM))
        added += 1

    mode = "WRITE" if write else "DRY-RUN"
    print(f"[{mode}] Added channel param to {added} entries")
    print(f"  Skipped (already have channel): {skipped_already}")
    print(f"  Skipped (model_name has base/official): {skipped_exempt}")
    print(f"  Total entries: {len(registry)}")

    if write:
        REGISTRY_PATH.write_text(
            json.dumps(registry, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"  Written to {REGISTRY_PATH}")
    else:
        print("  (no changes written — use --write to apply)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add channel param to registry entries that need it"
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Actually write changes (default is dry-run)",
    )
    args = parser.parse_args()
    run(write=args.write)


if __name__ == "__main__":
    main()
