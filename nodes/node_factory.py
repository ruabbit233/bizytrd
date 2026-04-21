"""Registry-driven node factory for bizytrd."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..core.base import BizyTRDBaseNode
from .manual import get_manual_node_mappings


_MEDIA_UI_ORDER = {
    "IMAGE": 0,
    "VIDEO": 1,
    "AUDIO": 2,
}

_PROMPT_KEYS = {"prompt", "text"}
_NEGATIVE_PROMPT_KEYS = {"negativeprompt", "negative_prompt"}


def _registry_path() -> Path:
    return Path(__file__).resolve().parent.parent / "models_registry.json"


def _load_registry() -> list[dict[str, Any]]:
    return json.loads(_registry_path().read_text(encoding="utf-8"))


def _model_label(model_def: dict[str, Any]) -> str:
    return str(
        model_def.get("internal_name")
        or model_def.get("class_name")
        or model_def.get("model_name")
        or "<unknown model>"
    )


def _validate_param_schema(model_def: dict[str, Any]) -> list[dict[str, Any]]:
    model_label = _model_label(model_def)
    params = model_def.get("params", [])
    if not isinstance(params, list):
        raise ValueError(f"{model_label}: params must be a list")

    for index, param in enumerate(params):
        if not isinstance(param, dict):
            raise ValueError(
                f"{model_label}: params[{index}] must be an object, got {type(param).__name__}"
            )
        for key in ("name", "type"):
            value = param.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"{model_label}: params[{index}] missing required key '{key}': {param}"
                )
    return params


def _return_signature(output_type: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    mapping = {
        "image": (("IMAGE", "STRING"), ("image", "urls")),
        "video": (("VIDEO", "STRING"), ("video", "urls")),
        "audio": (("AUDIO", "STRING"), ("audio", "urls")),
        "string": (("STRING", "STRING"), ("result", "urls")),
    }
    return mapping.get(output_type, mapping["string"])


def _param_description(param: dict[str, Any]) -> str:
    value = param.get("description")
    if isinstance(value, str):
        return value.strip()
    return ""


def _param_value(param: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in param:
            return param[name]
    return default


def _param_truthy(param: dict[str, Any], *names: str) -> bool:
    return bool(_param_value(param, *names, default=False))


def _build_input_def(param: dict[str, Any]):
    param_type = _param_value(param, "type", default="STRING")
    default = _param_value(param, "default")
    description = _param_description(param)

    if param_type == "STRING":
        options = {
            "default": default or "",
            "multiline": bool(_param_value(param, "multiline", default=False)),
            "description": description,
        }
        if _param_truthy(param, "forceInput"):
            options["forceInput"] = True
        return ("STRING", options)
    if param_type == "INT":
        options = {"default": int(default or 0)}
        if "min" in param:
            options["min"] = int(param["min"])
        if "max" in param:
            options["max"] = int(param["max"])
        if description:
            options["description"] = description
        return ("INT", options)
    if param_type == "FLOAT":
        options = {"default": float(default or 0.0)}
        if "min" in param:
            options["min"] = float(param["min"])
        if "max" in param:
            options["max"] = float(param["max"])
        if description:
            options["description"] = description
        return ("FLOAT", options)
    if param_type == "BOOLEAN":
        options = {"default": bool(default)}
        if description:
            options["description"] = description
        return ("BOOLEAN", options)
    if param_type == "LIST":
        options = param.get("options", [])
        if not options:
            fallback = {"default": str(default or "")}
            if description:
                fallback["description"] = description
            return ("STRING", fallback)
        selected = default if default is not None else options[0]
        if selected not in options:
            selected = options[0]
        meta = {"default": selected}
        if description:
            meta["description"] = description
        return (options, meta)
    if param_type in {"IMAGE", "VIDEO", "AUDIO"}:
        if description:
            return (param_type, {"description": description})
        return (param_type,)
    return ("STRING", {"default": str(default or "")})


def _clone_input_def(input_def: tuple[Any, ...]) -> tuple[Any, ...]:
    if len(input_def) == 1:
        return input_def
    first, options = input_def
    if isinstance(options, dict):
        return (first, dict(options))
    return input_def


def _multi_input_base_name(param_name: str) -> str:
    if param_name.endswith("s") and len(param_name) > 1:
        return param_name[:-1]
    return param_name


def _auto_inputcount_name(param: dict[str, Any]) -> str | None:
    if _param_value(param, "type") not in {"IMAGE", "VIDEO", "AUDIO"}:
        return None
    max_inputs = _param_value(param, "maxInputNum")
    if max_inputs is None or int(max_inputs) <= 1:
        return None
    name = str(param.get("name") or "")
    if name not in {"image", "images", "video", "videos", "audio", "audios"}:
        return None
    return f"{_multi_input_base_name(name)}_inputcount"


def _extra_input_name(param: dict[str, Any], index: int) -> str:
    return f"{_multi_input_base_name(param['name'])}_{index}"


def _resolved_max_inputs(
    param: dict[str, Any],
    params_by_name: dict[str, dict[str, Any]],
) -> int:
    max_inputs = _param_value(param, "maxInputNum")
    if max_inputs is not None:
        return int(max_inputs)
    return 1


def _build_auto_inputcount_def(param: dict[str, Any], params_by_name: dict[str, dict[str, Any]]):
    count_name = _auto_inputcount_name(param)
    if not count_name or count_name in params_by_name:
        return None

    max_inputs = _resolved_max_inputs(param, params_by_name)
    if max_inputs <= 1:
        return None

    media_label = _multi_input_base_name(param["name"])
    return (
        count_name,
        (
            "INT",
            {
                "default": 1,
                "min": 1,
                "max": max_inputs,
                "description": f"Controls how many {media_label} inputs are shown and read.",
            },
        ),
        False,
    )


def _iter_param_inputs(
    param: dict[str, Any],
    params_by_name: dict[str, dict[str, Any]],
) -> list[tuple[str, tuple[Any, ...], bool]]:
    if _param_truthy(param, "hidden"):
        return []

    input_name = param["name"]
    input_def = _build_input_def(param)
    entries: list[tuple[str, tuple[Any, ...], bool]] = []

    auto_count_def = _build_auto_inputcount_def(param, params_by_name)
    if auto_count_def is not None:
        entries.append(auto_count_def)

    entries.append((input_name, input_def, bool(_param_value(param, "required", default=False))))

    if _param_value(param, "type") not in {"IMAGE", "VIDEO", "AUDIO"}:
        return entries

    max_inputs = _resolved_max_inputs(param, params_by_name)
    if max_inputs <= 1:
        return entries

    for index in range(2, max_inputs + 1):
        entries.append((_extra_input_name(param, index), _clone_input_def(input_def), False))
    return entries


def _normalize_endpoint_category(value: str) -> str:
    normalized = re.sub(r"\s+", "-", str(value or "").strip().lower())
    normalized = normalized.replace("_", "-")
    return normalized.strip("-")


def _widget_sort_group(param: dict[str, Any]) -> int:
    name = str(param.get("name") or "").strip().lower()
    field_key = str(_param_value(param, "fieldKey", default=name) or "").strip().lower()

    if name == "channel":
        return 0
    if name in _PROMPT_KEYS or field_key in _PROMPT_KEYS:
        return 1
    if name in _NEGATIVE_PROMPT_KEYS or field_key in _NEGATIVE_PROMPT_KEYS:
        return 2
    return 3


def _sorted_params(model_def: dict[str, Any]) -> list[dict[str, Any]]:
    params = list(model_def.get("params", []))
    enumerated = list(enumerate(params))

    media_params = []
    widget_params = []
    for index, param in enumerated:
        if _param_value(param, "type") in {"IMAGE", "VIDEO", "AUDIO"}:
            media_params.append((index, param))
        else:
            widget_params.append((index, param))

    media_params.sort(
        key=lambda item: (
            _MEDIA_UI_ORDER.get(_param_value(item[1], "type"), len(_MEDIA_UI_ORDER)),
            item[0],
        )
    )
    widget_params.sort(
        key=lambda item: (
            _widget_sort_group(item[1]),
            item[0],
        )
    )

    return [param for _, param in media_params] + [param for _, param in widget_params]


def create_node_class(model_def: dict[str, Any]) -> type:
    required: dict[str, Any] = {}
    optional: dict[str, Any] = {}
    params = _validate_param_schema(model_def)
    params_by_name = {param["name"]: param for param in params}
    sorted_params = _sorted_params(model_def)

    for param in sorted_params:
        for input_name, input_def, is_required in _iter_param_inputs(param, params_by_name):
            if is_required:
                required[input_name] = input_def
            else:
                optional[input_name] = input_def

    return_types, return_names = _return_signature(model_def.get("output_type", "string"))
    class_name = model_def["class_name"]
    model_name = model_def["model_name"]
    endpoint_category = model_def.get("endpoint_category", "")
    category = model_def["category"]
    params = list(params)
    output_type = model_def.get("output_type", "string")
    node_definition = dict(model_def)

    class GeneratedBizyTRDNode(BizyTRDBaseNode):
        MODEL_NAME = model_name
        ENDPOINT_CATEGORY = endpoint_category
        MODEL_DEF = node_definition
        PARAMS = params
        OUTPUT_TYPE = output_type
        RETURN_TYPES = return_types
        RETURN_NAMES = return_names
        CATEGORY = category
        NORMALIZED_ENDPOINT_CATEGORY = _normalize_endpoint_category(endpoint_category)

        @classmethod
        def INPUT_TYPES(cls):
            return {"required": required, "optional": optional}

    GeneratedBizyTRDNode.__name__ = class_name
    GeneratedBizyTRDNode.__qualname__ = class_name
    return GeneratedBizyTRDNode


def create_all_nodes():
    class_mappings: dict[str, type] = {}
    display_mappings: dict[str, str] = {}
    registry = _load_registry()

    for model_def in registry:
        node_class = create_node_class(model_def)
        class_mappings[model_def["internal_name"]] = node_class
        display_mappings[model_def["internal_name"]] = model_def["display_name"]

    manual_classes, manual_displays = get_manual_node_mappings()
    duplicate_names = sorted(set(class_mappings) & set(manual_classes))
    if duplicate_names:
        raise ValueError(
            "Manual bizytrd node registration conflicts with registry nodes: "
            + ", ".join(duplicate_names)
        )

    class_mappings.update(manual_classes)
    display_mappings.update(manual_displays)

    return class_mappings, display_mappings
