from __future__ import annotations

import math
from typing import Any

from .base import HookContext


def size_mapping(value: Any, context: HookContext) -> dict[str, int]:
    aspect_ratio = str(context.get("aspect_ratio", "1:1"))
    resolution = str(context.get("resolution", "1k"))

    try:
        aspect_width, aspect_height = (int(part) for part in aspect_ratio.split(":"))
    except ValueError as exc:
        raise ValueError(f"Invalid aspect ratio: {aspect_ratio}") from exc

    resolution_mapping = {
        "1k": 1080,
        "2k": 2160,
        "4k": 3840,
    }
    if resolution not in resolution_mapping:
        raise ValueError(f"Unsupported resolution: {resolution}")

    base_size = resolution_mapping[resolution]
    if aspect_width >= aspect_height:
        width = base_size
        height = int(base_size * aspect_height / aspect_width)
    else:
        height = base_size
        width = int(base_size * aspect_width / aspect_height)

    def align16(size: int, mode: str = "round") -> int:
        if mode == "floor":
            return max(16, (size // 16) * 16)
        if mode == "ceil":
            return max(16, math.ceil(size / 16) * 16)
        return max(16, round(size / 16) * 16)

    width = align16(width)
    height = align16(height)

    max_pixels = 8_294_400
    min_pixels = 655_360
    max_edge = 3840

    if width * height > max_pixels or max(width, height) > max_edge:
        scale = min(
            math.sqrt(max_pixels / (width * height)),
            max_edge / max(width, height),
        )
        width = align16(int(width * scale), mode="floor")
        height = align16(int(height * scale), mode="floor")

    if width * height < min_pixels:
        scale = math.sqrt(min_pixels / (width * height))
        width = align16(int(width * scale), mode="ceil")
        height = align16(int(height * scale), mode="ceil")

    return {"width": width, "height": height}
