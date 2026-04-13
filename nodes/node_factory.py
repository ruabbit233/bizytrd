"""Registry-driven node factory for bizytrd."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..core.base import BizyTRDBaseNode


def _registry_path() -> Path:
    return Path(__file__).resolve().parent.parent / "models_registry.json"


def _load_registry() -> list[dict[str, Any]]:
    return json.loads(_registry_path().read_text(encoding="utf-8"))


def _return_signature(output_type: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    mapping = {
        "image": (("IMAGE", "STRING", "STRING"), ("image", "urls", "response")),
        "video": (("VIDEO", "STRING", "STRING"), ("video", "urls", "response")),
        "audio": (("AUDIO", "STRING", "STRING"), ("audio", "urls", "response")),
        "string": (("STRING", "STRING", "STRING"), ("result", "urls", "response")),
    }
    return mapping.get(output_type, mapping["string"])


def _param_tooltip(param: dict[str, Any]) -> str:
    for key in ("tooltip_zh", "description_zh", "tooltip", "description", "help", "notes"):
        value = param.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _build_input_def(param: dict[str, Any]):
    param_type = param["type"]
    default = param.get("default")
    tooltip = _param_tooltip(param)

    if param_type == "STRING":
        return (
            "STRING",
            {
                "default": default or "",
                "multiline": bool(param.get("multiline", False)),
                "tooltip": tooltip,
            },
        )
    if param_type == "INT":
        options = {"default": int(default or 0)}
        if "min" in param:
            options["min"] = int(param["min"])
        if "max" in param:
            options["max"] = int(param["max"])
        if tooltip:
            options["tooltip"] = tooltip
        return ("INT", options)
    if param_type == "FLOAT":
        options = {"default": float(default or 0.0)}
        if "min" in param:
            options["min"] = float(param["min"])
        if "max" in param:
            options["max"] = float(param["max"])
        if tooltip:
            options["tooltip"] = tooltip
        return ("FLOAT", options)
    if param_type == "BOOLEAN":
        options = {"default": bool(default)}
        if tooltip:
            options["tooltip"] = tooltip
        return ("BOOLEAN", options)
    if param_type == "LIST":
        options = param.get("options", [])
        if not options:
            fallback = {"default": str(default or "")}
            if tooltip:
                fallback["tooltip"] = tooltip
            return ("STRING", fallback)
        selected = default if default is not None else options[0]
        if selected not in options:
            selected = options[0]
        meta = {"default": selected}
        if tooltip:
            meta["tooltip"] = tooltip
        return (options, meta)
    if param_type in {"IMAGE", "VIDEO", "AUDIO"}:
        if tooltip:
            return (param_type, {"tooltip": tooltip})
        return (param_type,)
    return ("STRING", {"default": str(default or "")})


def _clone_input_def(input_def: tuple[Any, ...]) -> tuple[Any, ...]:
    if len(input_def) == 1:
        return input_def
    first, options = input_def
    if isinstance(options, dict):
        return (first, dict(options))
    return input_def


def _extra_input_name(param: dict[str, Any], index: int) -> str:
    pattern = str(param.get("extra_input_pattern", "")).strip()
    if pattern:
        return pattern.format(index=index, name=param["name"])
    return f"{param['name']}_{index}"


def _iter_param_inputs(param: dict[str, Any]) -> list[tuple[str, tuple[Any, ...], bool]]:
    input_name = param["name"]
    input_def = _build_input_def(param)
    entries = [(input_name, input_def, bool(param.get("required", False)))]

    if param.get("type") not in {"IMAGE", "VIDEO", "AUDIO"}:
        return entries
    if not (param.get("multiple_inputs") or param.get("multiple")):
        return entries

    max_inputs = int(param.get("max_inputs", 1))
    if max_inputs <= 1:
        return entries

    for index in range(2, max_inputs + 1):
        entries.append((_extra_input_name(param, index), _clone_input_def(input_def), False))
    return entries


def create_node_class(model_def: dict[str, Any]) -> type:
    required: dict[str, Any] = {}
    optional: dict[str, Any] = {}

    for param in model_def.get("params", []):
        for input_name, input_def, is_required in _iter_param_inputs(param):
            if is_required:
                required[input_name] = input_def
            else:
                optional[input_name] = input_def

    return_types, return_names = _return_signature(model_def.get("output_type", "string"))
    class_name = model_def["class_name"]
    model_key = model_def["model_key"]
    category = model_def["category"]
    params = list(model_def.get("params", []))
    output_type = model_def.get("output_type", "string")
    node_definition = dict(model_def)

    class GeneratedBizyTRDNode(BizyTRDBaseNode):
        MODEL_KEY = model_key
        MODEL_DEF = node_definition
        PARAMS = params
        OUTPUT_TYPE = output_type
        RETURN_TYPES = return_types
        RETURN_NAMES = return_names
        CATEGORY = category

        @classmethod
        def INPUT_TYPES(cls):
            return {"required": required, "optional": optional}

    GeneratedBizyTRDNode.__name__ = class_name
    GeneratedBizyTRDNode.__qualname__ = class_name
    return GeneratedBizyTRDNode


def create_all_nodes():
    class_mappings: dict[str, type] = {}
    display_mappings: dict[str, str] = {}

    for model_def in _load_registry():
        node_class = create_node_class(model_def)
        class_mappings[model_def["internal_name"]] = node_class
        display_mappings[model_def["internal_name"]] = model_def["display_name"]

    return class_mappings, display_mappings
