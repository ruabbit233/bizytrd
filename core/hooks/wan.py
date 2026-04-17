"""Wan-specific hooks.

These hooks read the current Wan node contract directly instead of relying on
registry-level hook parameter indirection.
"""

from __future__ import annotations

import json
from typing import Any


def custom_size(
    param: dict[str, Any],
    value: Any,
    kwargs: dict[str, Any],
    media_context: dict[str, dict[str, Any]],
) -> Any:
    size = str(value)
    resolved_model = kwargs.get("__resolved_model__") or ""
    custom_width = int(kwargs.get("custom_width") or 0)
    custom_height = int(kwargs.get("custom_height") or 0)
    has_input_images = bool(media_context.get("images", {}).get("count", 0))
    enable_sequential = bool(kwargs.get("enable_sequential", False))

    if size != "Custom":
        if size == "4K":
            if resolved_model != "wan2.7-image-pro":
                raise ValueError("wan2.7-image does not support 4K output")
            if has_input_images or enable_sequential:
                raise ValueError(
                    "4K is only supported for text-to-image when there are no input images and enable_sequential is false"
                )
        return size

    total_pixels = custom_width * custom_height
    ratio = custom_width / custom_height
    if ratio < 1 / 8 or ratio > 8:
        raise ValueError("Custom size aspect ratio must be between 1:8 and 8:1")
    if total_pixels < 768 * 768:
        raise ValueError("Custom size total pixels must be at least 768*768")

    max_pixels = 2048 * 2048
    if resolved_model == "wan2.7-image-pro" and not has_input_images and not enable_sequential:
        max_pixels = 4096 * 4096
    if total_pixels > max_pixels:
        raise ValueError(f"Custom size total pixels exceed the current scene limit: {max_pixels}")
    return f"{custom_width}*{custom_height}"


def bbox_list(
    param: dict[str, Any],
    value: Any,
    kwargs: dict[str, Any],
    media_context: dict[str, dict[str, Any]],
) -> Any:
    bbox_list_str = str(value or "")
    image_count = int(media_context.get("images", {}).get("count", 0))

    if not bbox_list_str or not bbox_list_str.strip():
        return None
    try:
        bbox_list = json.loads(bbox_list_str)
    except json.JSONDecodeError as exc:
        raise ValueError(f"bbox_list must be valid JSON: {exc}") from exc
    if not isinstance(bbox_list, list):
        raise ValueError("bbox_list must be a JSON array")
    if len(bbox_list) != image_count:
        raise ValueError("bbox_list length must exactly match the number of input images")
    for image_boxes in bbox_list:
        if not isinstance(image_boxes, list):
            raise ValueError("Each bbox_list item must be an array")
        if len(image_boxes) > 2:
            raise ValueError("Each input image supports at most 2 bounding boxes")
        for box in image_boxes:
            if (
                not isinstance(box, list)
                or len(box) != 4
                or not all(isinstance(v, int) for v in box)
            ):
                raise ValueError(
                    "Each bounding box must be a list of 4 integers: [x1, y1, x2, y2]"
                )
    return bbox_list


def color_palette(
    param: dict[str, Any],
    value: Any,
    kwargs: dict[str, Any],
    media_context: dict[str, dict[str, Any]],
) -> Any:
    color_palette_str = str(value or "")
    enable_sequential = bool(kwargs.get("enable_sequential", False))

    if not color_palette_str or not color_palette_str.strip():
        return None
    if enable_sequential:
        raise ValueError("color_palette is only supported when enable_sequential is false")
    try:
        color_palette = json.loads(color_palette_str)
    except json.JSONDecodeError as exc:
        raise ValueError(f"color_palette must be valid JSON: {exc}") from exc
    if not isinstance(color_palette, list):
        raise ValueError("color_palette must be a JSON array")
    if len(color_palette) < 3 or len(color_palette) > 10:
        raise ValueError("color_palette must contain between 3 and 10 colors")

    ratio_sum = 0.0
    for color in color_palette:
        if not isinstance(color, dict):
            raise ValueError("Each color_palette item must be an object")
        hex_value = color.get("hex", "")
        ratio_value = color.get("ratio", "")
        if (
            not isinstance(hex_value, str)
            or len(hex_value) != 7
            or not hex_value.startswith("#")
        ):
            raise ValueError("Each color_palette item must contain a hex value like #C2D1E6")
        if not isinstance(ratio_value, str) or not ratio_value.endswith("%"):
            raise ValueError('Each color_palette item must contain a ratio string like "23.51%"')
        try:
            ratio_sum += float(ratio_value[:-1])
        except ValueError as exc:
            raise ValueError(
                f"Invalid color ratio value in color_palette: {ratio_value}"
            ) from exc
    if abs(ratio_sum - 100.0) > 0.05:
        raise ValueError("color_palette ratios must sum to 100.00%")
    return color_palette
