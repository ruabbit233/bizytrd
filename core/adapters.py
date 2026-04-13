"""Generic payload builder for registry-driven bizytrd nodes.

The goal is to keep models_registry.json as the primary source of truth.
Most models should work by declaring params plus a small amount of metadata,
without needing a bespoke Python adapter function.
"""

from __future__ import annotations

import json
from typing import Any

from .upload import (
    normalize_media_input,
    upload_audio_input,
    upload_image_input,
    upload_video_input,
)


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) == 0
    return False


def _coerce_int(value: Any, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, (list, tuple)):
        if not value:
            return default
        value = value[0]
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _image_batches(images: Any) -> list[Any]:
    if images is None:
        return []
    if hasattr(images, "shape"):
        if len(images.shape) > 3:
            return [images[i] for i in range(images.shape[0])]
        return [images]
    if isinstance(images, (list, tuple)):
        batches: list[Any] = []
        for item in images:
            if item is None:
                continue
            if hasattr(item, "shape") and len(item.shape) > 3:
                batches.extend(item[i] for i in range(item.shape[0]))
            else:
                batches.append(item)
        return batches
    return [images]


def _resolve_custom_size(
    size: str,
    model: str,
    custom_width: int,
    custom_height: int,
    has_input_images: bool,
    enable_sequential: bool,
) -> str:
    if size != "Custom":
        if size == "4K":
            if model != "wan2.7-image-pro":
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
    if model == "wan2.7-image-pro" and not has_input_images and not enable_sequential:
        max_pixels = 4096 * 4096
    if total_pixels > max_pixels:
        raise ValueError(f"Custom size total pixels exceed the current scene limit: {max_pixels}")
    return f"{custom_width}*{custom_height}"


def _parse_bbox_list(bbox_list_str: str, image_count: int) -> list[Any] | None:
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


def _parse_color_palette(color_palette_str: str, enable_sequential: bool) -> list[Any] | None:
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


def _collect_media_values(param: dict[str, Any], kwargs: dict[str, Any]) -> list[Any]:
    input_name = param["name"]
    values: list[Any] = []

    def _append(value: Any) -> None:
        if _is_blank(value):
            return
        if param.get("flatten_batches"):
            values.extend(_image_batches(value))
        else:
            values.append(value)

    _append(kwargs.get(input_name))

    if not (param.get("multiple_inputs") or param.get("multiple")):
        return values

    max_inputs = int(param.get("max_inputs", 1))
    count_param = param.get("inputcount_param")
    if count_param:
        input_count = max(1, min(_coerce_int(kwargs.get(count_param), 1), max_inputs))
    else:
        input_count = max_inputs

    pattern = str(param.get("extra_input_pattern", f"{input_name}_{{index}}"))
    for index in range(2, input_count + 1):
        _append(kwargs.get(pattern.format(index=index, name=input_name)))
    return values


def _upload_media_values(
    param: dict[str, Any],
    values: list[Any],
    config: dict[str, Any],
) -> list[str]:
    media_type = param.get("type")
    if media_type not in {"IMAGE", "VIDEO", "AUDIO"}:
        return []

    urls: list[str] = []
    for index, value in enumerate(values, start=1):
        prefix_template = str(param.get("upload_file_name_prefix", param["name"]))
        file_name_prefix = prefix_template.format(index=index, name=param["name"])

        if media_type == "IMAGE":
            urls.append(
                upload_image_input(
                    value,
                    config,
                    file_name_prefix=file_name_prefix,
                    total_pixels=int(param.get("upload_total_pixels", 10000 * 10000)),
                    max_size=int(param.get("upload_max_size", 20 * 1024 * 1024)),
                )
            )
        elif media_type == "VIDEO":
            duration_range = None
            if "upload_duration_range" in param:
                duration_range = tuple(param["upload_duration_range"])
            urls.append(
                upload_video_input(
                    value,
                    config,
                    file_name_prefix=file_name_prefix,
                    max_size=int(param.get("upload_max_size", 100 * 1024 * 1024)),
                    enforce_duration_range=duration_range,
                )
            )
        else:
            urls.append(
                upload_audio_input(
                    value,
                    config,
                    file_name_prefix=file_name_prefix,
                    format=str(param.get("upload_format", "mp3")),
                    max_size=int(param.get("upload_max_size", 50 * 1024 * 1024)),
                )
            )
    return urls


def _build_media_context(
    model_def: dict[str, Any],
    config: dict[str, Any],
    kwargs: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    context: dict[str, dict[str, Any]] = {}
    for param in model_def.get("params", []):
        if param.get("type") not in {"IMAGE", "VIDEO", "AUDIO"}:
            continue
        values = _collect_media_values(param, kwargs)
        urls = _upload_media_values(param, values, config)
        context[param["name"]] = {
            "values": values,
            "urls": urls,
            "count": len(values),
        }
    return context


def _apply_transform(
    param: dict[str, Any],
    value: Any,
    kwargs: dict[str, Any],
    media_context: dict[str, dict[str, Any]],
) -> Any:
    transform = param.get("transform")
    if not transform:
        return value

    if transform == "custom_size":
        model_param = param.get("transform_model_param", "model")
        width_param = param.get("transform_width_param", "custom_width")
        height_param = param.get("transform_height_param", "custom_height")
        media_param = param.get("transform_media_param", "images")
        sequential_param = param.get("transform_sequential_param", "enable_sequential")
        return _resolve_custom_size(
            str(value),
            str(kwargs.get(model_param) or ""),
            int(kwargs.get(width_param) or 0),
            int(kwargs.get(height_param) or 0),
            bool(media_context.get(media_param, {}).get("count", 0)),
            bool(kwargs.get(sequential_param, False)),
        )

    if transform == "bbox_list":
        media_param = param.get("transform_media_param", "images")
        return _parse_bbox_list(str(value or ""), int(media_context.get(media_param, {}).get("count", 0)))

    if transform == "color_palette":
        sequential_param = param.get("transform_sequential_param", "enable_sequential")
        return _parse_color_palette(str(value or ""), bool(kwargs.get(sequential_param, False)))

    if transform == "json":
        if _is_blank(value):
            return None
        return json.loads(str(value))

    raise ValueError(f"Unsupported transform '{transform}' for param '{param['name']}'")


def _should_include_param(
    param: dict[str, Any],
    value: Any,
    kwargs: dict[str, Any],
    media_context: dict[str, dict[str, Any]],
) -> bool:
    if value is None:
        return False

    only_if_true_param = param.get("only_if_true_param")
    if only_if_true_param and not bool(kwargs.get(only_if_true_param)):
        return False

    only_if_false_param = param.get("only_if_false_param")
    if only_if_false_param and bool(kwargs.get(only_if_false_param)):
        return False

    only_if_media_absent = param.get("only_if_media_absent")
    if only_if_media_absent and media_context.get(only_if_media_absent, {}).get("count", 0) > 0:
        return False

    only_if_media_present = param.get("only_if_media_present")
    if only_if_media_present and media_context.get(only_if_media_present, {}).get("count", 0) <= 0:
        return False

    send_if = param.get("send_if")
    if send_if == "non_empty":
        return not _is_blank(value)
    if send_if == "true":
        return bool(value)
    if send_if == "gte_zero":
        return int(value) >= 0
    if send_if == "nonzero":
        return value not in (0, "0")
    if send_if == "not_default":
        return value != param.get("default")
    if send_if == "always":
        return True

    skip_values = param.get("skip_values")
    if isinstance(skip_values, list) and value in skip_values:
        return False

    if _is_blank(value) and param.get("type") == "STRING":
        return False
    return True


def _resolve_model_value(model_def: dict[str, Any], kwargs: dict[str, Any]) -> Any:
    model_param = model_def.get("request_model_from")
    if model_param:
        value = kwargs.get(model_param)
        if value is not None:
            return value
    if "request_model" in model_def:
        return model_def["request_model"]
    return model_def["model_key"]


def _validate_required_any_of(
    model_def: dict[str, Any],
    kwargs: dict[str, Any],
    media_context: dict[str, dict[str, Any]],
) -> None:
    require_any = model_def.get("require_any_of") or []
    if not require_any:
        return

    for name in require_any:
        if name in media_context and media_context[name]["count"] > 0:
            return
        if not _is_blank(kwargs.get(name)):
            return

    message = model_def.get("require_any_message") or "At least one value is required"
    raise ValueError(message)


def build_payload_for_model(
    model_def: dict[str, Any],
    config: dict[str, Any],
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    media_context = _build_media_context(model_def, config, kwargs)
    _validate_required_any_of(model_def, kwargs, media_context)

    payload: dict[str, Any] = {"model": _resolve_model_value(model_def, kwargs)}
    grouped_media: dict[str, list[Any]] = {}

    for param in model_def.get("params", []):
        param_type = param.get("type")
        if param_type in {"IMAGE", "VIDEO", "AUDIO"}:
            if param.get("internal"):
                continue

            urls = media_context.get(param["name"], {}).get("urls", [])
            if not urls:
                continue

            api_field = param.get("api_field", param["name"])
            media_item_type = param.get("media_item_type")
            if media_item_type:
                grouped_media.setdefault(api_field, []).extend(
                    {"type": media_item_type, "url": url} for url in urls
                )
            elif param.get("multiple_inputs") or param.get("multiple") or param.get("force_list"):
                payload[api_field] = urls
            else:
                payload[api_field] = urls[0]
            continue

        if param.get("internal"):
            continue

        raw_value = kwargs.get(param["name"])
        value = _apply_transform(param, raw_value, kwargs, media_context)
        if not _should_include_param(param, value, kwargs, media_context):
            continue
        payload[param.get("api_field", param["name"])] = value

    for field_name, items in grouped_media.items():
        if items:
            payload[field_name] = items

    return payload
