from __future__ import annotations

import json
from typing import Any

from .base import HookContext


def size_mapping(
    value: Any,
    context: HookContext,
) -> Any:
    width = int(context.get("width") or 0)
    height = int(context.get("height") or 0)

    if width < 256 or width > 2048:
        raise ValueError("Width must be between 256 and 2048")
    if height < 256 or height > 2048:
        raise ValueError("Height must be between 256 and 2048")
    
    return f"{width}*{height}"