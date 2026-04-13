"""Declarative payload adapters for registry-driven bizytrd nodes."""

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
    if hasattr(value, "numel"):
        try:
            return value.numel() == 0
        except Exception:
            pass
    if hasattr(value, "shape"):
        try:
            return any(dim == 0 for dim in value.shape)
        except Exception:
            pass
    return False


def _default_adapter(
    model_def: dict[str, Any],
    config: dict[str, Any],
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    payload: dict[str, Any] = {"model": model_def["model_key"]}
    for param in model_def.get("params", []):
        input_name = param["name"]
        api_field = param.get("api_field", input_name)
        value = kwargs.get(input_name)
        if value is None:
            continue
        param_type = param.get("type", "STRING")
        if param_type in {"IMAGE", "VIDEO", "AUDIO"}:
            payload[api_field] = normalize_media_input(
                value,
                param_type,
                input_name,
                config,
            )
        else:
            payload[api_field] = value
    return payload


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


def _listify(value: Any) -> list[Any]:
    if _is_blank(value):
        return []
    if isinstance(value, (list, tuple)):
        return [item for item in value if not _is_blank(item)]
    return [value]


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


def _parse_bbox_list(bbox_list_str: str, image_count: int):
    if not bbox_list_str or not bbox_list_str.strip():
        return None
    try:
        bbox_list = json.loads(bbox_list_str)
    except json.JSONDecodeError as exc:
        raise ValueError(f"bbox_list must be valid JSON: {exc}") from exc
    if not isinstance(bbox_list, list):
        raise ValueError("bbox_list must be a JSON array")
    if len(bbox_list) != image_count:
        raise ValueError(
            "bbox_list length must exactly match the number of input images"
        )
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


def _parse_color_palette(color_palette_str: str, enable_sequential: bool):
    if not color_palette_str or not color_palette_str.strip():
        return None
    if enable_sequential:
        raise ValueError(
            "color_palette is only supported when enable_sequential is false"
        )
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
            raise ValueError(
                "Each color_palette item must contain a hex value like #C2D1E6"
            )
        if not isinstance(ratio_value, str) or not ratio_value.endswith("%"):
            raise ValueError(
                'Each color_palette item must contain a ratio string like "23.51%"'
            )
        try:
            ratio_sum += float(ratio_value[:-1])
        except ValueError as exc:
            raise ValueError(
                f"Invalid color ratio value in color_palette: {ratio_value}"
            ) from exc
    if abs(ratio_sum - 100.0) > 0.05:
        raise ValueError("color_palette ratios must sum to 100.00%")
    return color_palette


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
        raise ValueError(
            f"Custom size total pixels exceed the current scene limit: {max_pixels}"
        )
    return f"{custom_width}*{custom_height}"


def _resolve_ref(
    ref: Any,
    kwargs: dict[str, Any],
    context: dict[str, Any],
    model_def: dict[str, Any],
) -> Any:
    if not isinstance(ref, dict):
        return ref
    if "const" in ref:
        return ref["const"]
    if "input" in ref:
        return kwargs.get(ref["input"])
    if "context" in ref:
        return context.get(ref["context"])
    if "model" in ref:
        return model_def.get(ref["model"])
    if "model_key" in ref:
        return model_def.get("model_key")
    recognised = {"const", "input", "context", "model", "model_key"}
    unrecognised = set(ref.keys()) - recognised
    if unrecognised:
        raise ValueError(
            f"Unrecognised ref keys {unrecognised!r} in adapter definition: {ref!r}"
        )
    return None


def _evaluate_condition(
    condition: dict[str, Any] | None,
    kwargs: dict[str, Any],
    context: dict[str, Any],
    model_def: dict[str, Any],
) -> bool:
    if not condition:
        return True
    if "all" in condition:
        return all(
            _evaluate_condition(item, kwargs, context, model_def)
            for item in condition["all"]
        )
    if "any" in condition:
        return any(
            _evaluate_condition(item, kwargs, context, model_def)
            for item in condition["any"]
        )
    if "not" in condition:
        return not _evaluate_condition(condition["not"], kwargs, context, model_def)

    source = condition.get("source", "input")
    key = condition.get("key")
    op = condition.get("op", "exists")
    value = _resolve_ref({source: key}, kwargs, context, model_def)
    target = condition.get("value")

    if op == "exists":
        return value is not None
    if op == "non_empty":
        return not _is_blank(value)
    if op == "empty":
        return _is_blank(value)
    if op == "eq":
        return value == target
    if op == "ne":
        return value != target
    if op == "in":
        return value in (target or [])
    if op == "not_in":
        return value not in (target or [])
    if op == "gt":
        try:
            return value is not None and value > target
        except TypeError:
            return False
    if op == "gte":
        try:
            return value is not None and value >= target
        except TypeError:
            return False
    if op == "lt":
        try:
            return value is not None and value < target
        except TypeError:
            return False
    if op == "lte":
        try:
            return value is not None and value <= target
        except TypeError:
            return False
    if op == "is_true":
        return bool(value) is True
    if op == "is_false":
        return bool(value) is False
    raise ValueError(f"Unsupported adapter condition op '{op}'")


def _upload_media_value(
    value: Any,
    media_type: str,
    config: dict[str, Any],
    input_name: str,
    options: dict[str, Any],
    *,
    index: int | None = None,
) -> str:
    file_name_prefix = str(options.get("file_name_prefix", input_name))
    if index is not None:
        file_name_prefix = file_name_prefix.format(index=index)

    if media_type == "IMAGE":
        return upload_image_input(
            value,
            config,
            file_name_prefix=file_name_prefix,
            total_pixels=int(options.get("total_pixels", 10000 * 10000)),
            max_size=int(options.get("max_size", 20 * 1024 * 1024)),
        )
    if media_type == "VIDEO":
        duration_range = options.get("enforce_duration_range")
        if isinstance(duration_range, list):
            duration_range = tuple(duration_range)
        return upload_video_input(
            value,
            config,
            file_name_prefix=file_name_prefix,
            max_size=int(options.get("max_size", 100 * 1024 * 1024)),
            enforce_duration_range=duration_range,
        )
    if media_type == "AUDIO":
        return upload_audio_input(
            value,
            config,
            file_name_prefix=file_name_prefix,
            format=str(options.get("format", "mp3")),
            max_size=int(options.get("max_size", 50 * 1024 * 1024)),
        )
    return normalize_media_input(value, media_type, input_name, config)


def _apply_transform(
    value: Any,
    transform_spec: str | dict[str, Any],
    kwargs: dict[str, Any],
    context: dict[str, Any],
    model_def: dict[str, Any],
    config: dict[str, Any],
) -> Any:
    if isinstance(transform_spec, str):
        name = transform_spec
        params: dict[str, Any] = {}
    else:
        name = transform_spec["name"]
        params = dict(transform_spec)

    if name == "image_batches":
        return _image_batches(value)

    if name == "count":
        return len(value or [])

    if name == "collect_counted_inputs":
        count_value = _resolve_ref(
            params.get("count", {"const": 1}), kwargs, context, model_def
        )
        max_count = int(params.get("max_count", 1))
        input_count = max(1, min(_coerce_int(count_value, 1), max_count))
        extra_input_pattern = str(params.get("extra_input_pattern", "{index}"))
        item_transform = params.get("item_transform")

        collected: list[Any] = []
        collected.extend(
            _collect_transformed_items(
                value,
                item_transform,
                kwargs,
                context,
                model_def,
                config,
            )
        )
        for index in range(2, input_count + 1):
            extra_value = kwargs.get(extra_input_pattern.format(index=index))
            collected.extend(
                _collect_transformed_items(
                    extra_value,
                    item_transform,
                    kwargs,
                    context,
                    model_def,
                    config,
                )
            )
        return collected

    if name == "upload_media_list":
        items = list(value or [])
        media_type = str(params["media_type"])
        options = {
            "file_name_prefix": params.get("file_name_prefix", "media_{index}"),
            "total_pixels": params.get("total_pixels", 10000 * 10000),
            "max_size": params.get("max_size", 20 * 1024 * 1024),
            "enforce_duration_range": params.get("enforce_duration_range"),
        }
        urls = []
        for index, item in enumerate(items, start=1):
            urls.append(
                _upload_media_value(
                    item,
                    media_type,
                    config,
                    params.get("input_name", "media"),
                    options,
                    index=index,
                )
            )
        return urls

    if name == "resolve_custom_size":
        model = _resolve_ref(params["model"], kwargs, context, model_def)
        custom_width = int(
            _resolve_ref(params["custom_width"], kwargs, context, model_def)
        )
        custom_height = int(
            _resolve_ref(params["custom_height"], kwargs, context, model_def)
        )
        has_input_images = bool(
            _resolve_ref(params["has_input_images"], kwargs, context, model_def)
        )
        enable_sequential = bool(
            _resolve_ref(params["enable_sequential"], kwargs, context, model_def)
        )
        return _resolve_custom_size(
            str(value),
            str(model),
            custom_width,
            custom_height,
            has_input_images,
            enable_sequential,
        )

    if name == "parse_bbox_list":
        image_count = int(
            _resolve_ref(params["image_count"], kwargs, context, model_def) or 0
        )
        return _parse_bbox_list(str(value or ""), image_count)

    if name == "parse_color_palette":
        enable_sequential = bool(
            _resolve_ref(params["enable_sequential"], kwargs, context, model_def)
        )
        return _parse_color_palette(str(value or ""), enable_sequential)

    raise ValueError(f"Unsupported adapter transform '{name}'")


def _collect_transformed_items(
    value: Any,
    item_transform: str | dict[str, Any] | None,
    kwargs: dict[str, Any],
    context: dict[str, Any],
    model_def: dict[str, Any],
    config: dict[str, Any],
) -> list[Any]:
    if _is_blank(value):
        return []
    if item_transform is None:
        return _listify(value)
    transformed = _apply_transform(
        value, item_transform, kwargs, context, model_def, config
    )
    return _listify(transformed)


def _apply_transforms(
    value: Any,
    spec: dict[str, Any],
    kwargs: dict[str, Any],
    context: dict[str, Any],
    model_def: dict[str, Any],
    config: dict[str, Any],
) -> Any:
    transforms: list[Any] = []
    if "transform" in spec:
        transforms.append(spec["transform"])
    transforms.extend(spec.get("transforms", []))
    for transform_spec in transforms:
        value = _apply_transform(
            value, transform_spec, kwargs, context, model_def, config
        )
    return value


def _run_validator(
    validator: dict[str, Any],
    kwargs: dict[str, Any],
    context: dict[str, Any],
    model_def: dict[str, Any],
    current_value: Any = None,
) -> None:
    if not _evaluate_condition(validator.get("when"), kwargs, context, model_def):
        return

    name = validator["name"]
    message = validator.get("message")
    value = (
        _resolve_ref(validator["value"], kwargs, context, model_def)
        if "value" in validator
        else current_value
    )

    if name == "max_count":
        max_count = int(validator["max"])
        count = len(value or [])
        if count > max_count:
            raise ValueError(message or f"Maximum count is {max_count}")
        return

    if name == "int_range":
        if value is None:
            return
        minimum = int(validator["min"])
        maximum = int(validator["max"])
        integer = int(value)
        if integer < minimum or integer > maximum:
            raise ValueError(
                message or f"Value must be between {minimum} and {maximum}"
            )
        return

    if name == "require_any_non_empty":
        refs = validator.get("refs", [])
        if not any(
            not _is_blank(_resolve_ref(ref, kwargs, context, model_def)) for ref in refs
        ):
            raise ValueError(message or "At least one value is required")
        return

    raise ValueError(f"Unsupported adapter validator '{name}'")


def _build_media_array(
    items: list[dict[str, Any]],
    kwargs: dict[str, Any],
    context: dict[str, Any],
    model_def: dict[str, Any],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in items:
        if not _evaluate_condition(item.get("when"), kwargs, context, model_def):
            continue
        value = _resolve_ref(
            item.get("value") or {"input": item["input"]}, kwargs, context, model_def
        )
        if _is_blank(value):
            if item.get("required"):
                raise ValueError(
                    item.get("message") or f"'{item.get('input', 'value')}' is required"
                )
            continue

        media_type = item["media_type"]
        upload_options = {
            "file_name_prefix": item.get(
                "file_name_prefix", item.get("input", "media")
            ),
            "total_pixels": item.get("total_pixels", 10000 * 10000),
            "max_size": item.get("max_size", 20 * 1024 * 1024),
            "enforce_duration_range": item.get("enforce_duration_range"),
        }
        url = _upload_media_value(
            value,
            media_type,
            config,
            item.get("input", "media"),
            upload_options,
        )
        result.append(
            {
                "type": item["item_type"],
                "url": url,
            }
        )
    return result


def _build_context(
    context_specs: list[dict[str, Any]],
    kwargs: dict[str, Any],
    model_def: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    context: dict[str, Any] = {}
    for spec in context_specs:
        if not _evaluate_condition(spec.get("when"), kwargs, context, model_def):
            continue
        value = _resolve_ref(spec, kwargs, context, model_def)
        value = _apply_transforms(value, spec, kwargs, context, model_def, config)
        for validator in spec.get("validators", []):
            _run_validator(validator, kwargs, context, model_def, current_value=value)
        context[spec["name"]] = value
    return context


def _structured_adapter(
    model_def: dict[str, Any],
    config: dict[str, Any],
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    adapter = model_def.get("adapter") or {}
    context = _build_context(adapter.get("context", []), kwargs, model_def, config)

    for validator in adapter.get("validators", []):
        _run_validator(validator, kwargs, context, model_def)

    payload: dict[str, Any] = {}
    for item in adapter.get("payload", []):
        if not _evaluate_condition(item.get("when"), kwargs, context, model_def):
            continue

        if item.get("build") == "media_array":
            value = _build_media_array(
                item.get("items", []), kwargs, context, model_def, config
            )
        else:
            value = _resolve_ref(item, kwargs, context, model_def)
            value = _apply_transforms(value, item, kwargs, context, model_def, config)

        for validator in item.get("validators", []):
            _run_validator(validator, kwargs, context, model_def, current_value=value)

        if item.get("skip_if_blank") and _is_blank(value):
            continue
        if value is None and item.get("skip_if_none", False):
            continue
        payload[item["field"]] = value

    if "model" not in payload:
        payload["model"] = model_def["model_key"]
    return payload


def build_payload_for_model(
    model_def: dict[str, Any],
    config: dict[str, Any],
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    adapter = model_def.get("adapter")
    if not adapter or adapter == "default":
        return _default_adapter(model_def, config, kwargs)
    if isinstance(adapter, dict):
        kind = adapter.get("kind", "structured")
        if kind == "structured":
            return _structured_adapter(model_def, config, kwargs)
        raise ValueError(f"Unsupported adapter kind '{kind}'")
    raise ValueError(f"Unsupported adapter definition '{adapter}'")
