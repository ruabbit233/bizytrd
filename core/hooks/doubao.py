from __future__ import annotations

import json
from typing import Any

from .base import HookContext


def custom_size(
    value: Any,
    context: HookContext,
) -> Any:
    size = str(value)
    custom_width = int(context.get("custom_width") or 0)
    custom_height = int(context.get("custom_height") or 0)

    match size:
        case "1K Square (1024x1024)":
            width = 1024
            height = 1024
        case "2K Square (2048x2048)":
            width = 2048
            height = 2048
        case "4K Square (4096x4096)":
            width = 4096
            height = 4096
        case "HD 16:9 (1920x1080)":
            width = 1920
            height = 1080
        case "2K 16:9 (2560x1440)":
            width = 2560
            height = 1440
        case "4K 16:9 (3840x2160)":
            width = 3840
            height = 2160
        case "Portrait 9:16 (1080x1920)":
            width = 1080
            height = 1920
        case "Portrait 3:4 (1536x2048)":
            width = 1536
            height = 2048
        case "Landscape 4:3 (2048x1536)":
            width = 2048
            height = 1536
        case "Ultra-wide 21:9 (3440x1440)":
            width = 3440
            height = 1440
        case "Custom":
            width = custom_width
            height = custom_height

        case _:
            raise ValueError(f"Invalid size: {size}")
        
    return f"{width}*{height}"