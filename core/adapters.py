"""Generic payload builder for registry-driven bizytrd nodes.

The goal is to keep models_registry.json as the primary source of truth.
Most models should work by declaring params plus a small amount of metadata,
without needing a bespoke Python adapter function.
"""

from __future__ import annotations

import importlib
import re
from typing import Any

from .upload import (
    upload_audio_input,
    upload_image_input,
    upload_video_input,
)


def _param_value(param: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in param:
            return param[name]
    return default


def _param_truthy(param: dict[str, Any], *names: str) -> bool:
    return bool(_param_value(param, *names, default=False))


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


def _multi_input_base_name(param_name: str) -> str:
    if param_name.endswith("s") and len(param_name) > 1:
        return param_name[:-1]
    return param_name


def _extra_input_name(param_name: str, index: int) -> str:
    return f"{_multi_input_base_name(param_name)}_{index}"


def _resolved_max_inputs(
    param: dict[str, Any],
    params_by_name: dict[str, dict[str, Any]],
) -> int:
    count_param_name = _param_value(param, "inputcountParam", "inputcount_param") or _auto_inputcount_name(param)
    if count_param_name:
        count_param = params_by_name.get(count_param_name, {})
        count_param_max = _param_value(count_param, "max", "maxInputNum", "maxInputCount")
        if count_param_max is not None:
            return int(count_param_max)
    max_inputs = _param_value(param, "maxInputNum", "maxInputCount", "max_inputs")
    if max_inputs is not None:
        return int(max_inputs)
    return 1


def _auto_inputcount_name(param: dict[str, Any]) -> str | None:
    if _param_value(param, "type") not in {"IMAGE", "VIDEO", "AUDIO"}:
        return None
    if not (_param_truthy(param, "multipleInputs", "multiple_inputs", "multiple")):
        return None
    name = str(param.get("name") or "")
    if name not in {"image", "images", "video", "videos", "audio", "audios"}:
        return None
    return f"{_multi_input_base_name(name)}_inputcount"


def _collect_media_values(param: dict[str, Any], kwargs: dict[str, Any]) -> list[Any]:
    input_name = param["name"]
    values: list[Any] = []

    def _append(value: Any) -> None:
        if _is_blank(value):
            return
        if _param_truthy(param, "flattenBatches", "flatten_batches"):
            values.extend(_image_batches(value))
        else:
            values.append(value)

    _append(kwargs.get(input_name))

    if not (_param_truthy(param, "multipleInputs", "multiple_inputs", "multiple")):
        return values

    params_by_name = kwargs.get("__params_by_name__", {})
    max_inputs = _resolved_max_inputs(param, params_by_name)
    count_param = _param_value(param, "inputcountParam", "inputcount_param")
    if count_param:
        input_count = max(1, min(_coerce_int(kwargs.get(count_param), 1), max_inputs))
    else:
        input_count = max_inputs

    for index in range(2, input_count + 1):
        _append(kwargs.get(_extra_input_name(input_name, index)))
    return values


def _upload_media_values(
    param: dict[str, Any],
    values: list[Any],
    config: dict[str, Any],
) -> list[str]:
    media_type = _param_value(param, "type")
    if media_type not in {"IMAGE", "VIDEO", "AUDIO"}:
        return []

    urls: list[str] = []
    for index, value in enumerate(values, start=1):
        file_name_prefix = f"{param['name']}_{index}"

        if media_type == "IMAGE":
            urls.append(
                upload_image_input(
                    value,
                    config,
                    file_name_prefix=file_name_prefix,
                )
            )
        elif media_type == "VIDEO":
            urls.append(
                upload_video_input(
                    value,
                    config,
                    file_name_prefix=file_name_prefix,
                )
            )
        else:
            urls.append(
                upload_audio_input(
                    value,
                    config,
                    file_name_prefix=file_name_prefix,
                )
            )
    return urls


def _build_media_context(
    model_def: dict[str, Any],
    config: dict[str, Any],
    kwargs: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    context: dict[str, dict[str, Any]] = {}
    kwargs = dict(kwargs)
    kwargs["__params_by_name__"] = {
        param["name"]: param for param in model_def.get("params", [])
    }
    for param in model_def.get("params", []):
        if _param_value(param, "type") not in {"IMAGE", "VIDEO", "AUDIO"}:
            continue
        values = _collect_media_values(param, kwargs)
        urls = _upload_media_values(param, values, config)
        context[param["name"]] = {
            "values": values,
            "urls": urls,
            "count": len(values),
        }
    return context


def _resolve_value_hook(hook_name: str):
    parts = str(hook_name).split(".")
    if len(parts) != 2 or not all(parts):
        raise ValueError(
            f"Unsupported value_hook '{hook_name}'. Expected '<module>.<function>'."
        )

    module_name, function_name = parts
    try:
        module = importlib.import_module(f"{__package__}.hooks.{module_name}")
    except ModuleNotFoundError as exc:
        raise ValueError(
            f"Unsupported value_hook '{hook_name}'. Unknown hook module '{module_name}'."
        ) from exc

    hook = getattr(module, function_name, None)
    if hook is None or not callable(hook):
        raise ValueError(
            f"Unsupported value_hook '{hook_name}'. Unknown hook function '{function_name}'."
        )
    return hook


def _apply_value_hook(
    param: dict[str, Any],
    value: Any,
    kwargs: dict[str, Any],
    media_context: dict[str, dict[str, Any]],
) -> Any:
    hook_name = _param_value(param, "valueHook", "value_hook")
    if not hook_name:
        return value

    hook = _resolve_value_hook(str(hook_name))
    return hook(param, value, kwargs, media_context)


def _normalize_channel_suffix(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = re.sub(r"\s+", "-", text)
    text = text.replace("_", "-")
    if not text.startswith("-"):
        text = f"-{text}"
    return text


def _should_include_param(
    param: dict[str, Any],
    value: Any,
    kwargs: dict[str, Any],
    media_context: dict[str, dict[str, Any]],
) -> bool:
    if value is None:
        return False

    only_if_true_param = _param_value(param, "onlyIfTrueParam", "only_if_true_param")
    if only_if_true_param and not bool(kwargs.get(only_if_true_param)):
        return False

    only_if_false_param = _param_value(param, "onlyIfFalseParam", "only_if_false_param")
    if only_if_false_param and bool(kwargs.get(only_if_false_param)):
        return False

    only_if_media_absent = _param_value(param, "onlyIfMediaAbsent", "only_if_media_absent")
    if only_if_media_absent and media_context.get(only_if_media_absent, {}).get("count", 0) > 0:
        return False

    only_if_media_present = _param_value(param, "onlyIfMediaPresent", "only_if_media_present")
    if only_if_media_present and media_context.get(only_if_media_present, {}).get("count", 0) <= 0:
        return False

    send_if = _param_value(param, "sendIf", "send_if")
    if send_if == "non_empty":
        return not _is_blank(value)
    if send_if == "true":
        return bool(value)
    if send_if == "gte_zero":
        return int(value) >= 0
    if send_if == "nonzero":
        return value not in (0, "0")
    if send_if == "not_default":
        return value != _param_value(param, "defaultValue", "default")
    if send_if == "always":
        return True

    skip_values = param.get("skip_values")
    if isinstance(skip_values, list) and value in skip_values:
        return False

    if _is_blank(value) and _param_value(param, "type") == "STRING":
        return False
    return True


def _resolve_model_value(model_def: dict[str, Any], kwargs: dict[str, Any]) -> Any:
    model_name = model_def.get("model_name")
    if model_name is not None:
        channel_value = kwargs.get("channel")
        if channel_value is not None and str(channel_value).strip():
            return f"{model_name}{_normalize_channel_suffix(channel_value)}"
        return model_name
    raise KeyError("model_name")


def build_payload_for_model(
    model_def: dict[str, Any],
    config: dict[str, Any],
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    media_context = _build_media_context(model_def, config, kwargs)
    payload: dict[str, Any] = {"model": _resolve_model_value(model_def, kwargs)}
    hook_kwargs = dict(kwargs)
    hook_kwargs["__resolved_model__"] = payload["model"]
    grouped_media: dict[str, list[Any]] = {}

    for param in model_def.get("params", []):
        param_type = _param_value(param, "type")
        if param_type in {"IMAGE", "VIDEO", "AUDIO"}:
            if param.get("internal"):
                continue

            urls = media_context.get(param["name"], {}).get("urls", [])
            if not urls:
                continue

            api_field = _param_value(param, "fieldKey", "api_field", default=param["name"])
            media_item_type = _param_value(param, "mediaItemType", "media_item_type")
            if media_item_type:
                grouped_media.setdefault(api_field, []).extend(
                    {"type": media_item_type, "url": url} for url in urls
                )
            elif _param_truthy(param, "multipleInputs", "multiple_inputs", "multiple", "forceList", "force_list"):
                payload[api_field] = urls
            else:
                payload[api_field] = urls[0]
            continue

        if param.get("internal"):
            continue

        raw_value = kwargs.get(param["name"])
        value = _apply_value_hook(param, raw_value, hook_kwargs, media_context)
        if not _should_include_param(param, value, hook_kwargs, media_context):
            continue
        payload[_param_value(param, "fieldKey", "api_field", default=param["name"])] = value

    for field_name, items in grouped_media.items():
        if items:
            payload[field_name] = items

    return payload
