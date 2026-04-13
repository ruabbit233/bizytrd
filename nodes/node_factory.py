"""Registry-driven node factory for bizytrd."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..core.base import BizyTRDBaseNode
from ..core.exceptions import RegistryError

REQUIRED_MODEL_FIELDS = {
    "internal_name",
    "class_name",
    "display_name",
    "category",
    "model_key",
    "output_type",
    "params",
}
REQUIRED_PARAM_FIELDS = {"name", "type"}
VALID_PARAM_TYPES = {
    "STRING",
    "INT",
    "FLOAT",
    "BOOLEAN",
    "LIST",
    "IMAGE",
    "VIDEO",
    "AUDIO",
}
VALID_OUTPUT_TYPES = {"image", "video", "audio", "string"}


def _registry_path() -> Path:
    return Path(__file__).resolve().parent.parent / "models_registry.json"


def _load_registry() -> list[dict[str, Any]]:
    path = _registry_path()
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise RegistryError(f"Models registry not found at {path}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RegistryError(f"Models registry contains invalid JSON: {exc}") from exc
    if not isinstance(data, list):
        raise RegistryError("Models registry root must be a JSON array")
    return data


def _validate_registry(data: list[dict[str, Any]]) -> None:
    seen_names: set[str] = set()

    for index, model_def in enumerate(data):
        prefix = f"Registry entry [{index}]"

        if not isinstance(model_def, dict):
            raise RegistryError(
                f"{prefix} must be a JSON object, got {type(model_def).__name__}"
            )

        missing = REQUIRED_MODEL_FIELDS - model_def.keys()
        if missing:
            raise RegistryError(f"{prefix} missing required fields: {sorted(missing)}")

        name = model_def["internal_name"]
        if name in seen_names:
            raise RegistryError(
                f"Duplicate internal_name '{name}' in models_registry.json"
            )
        seen_names.add(name)

        output_type = model_def.get("output_type", "")
        if output_type not in VALID_OUTPUT_TYPES:
            raise RegistryError(
                f"{prefix} ('{name}'): invalid output_type '{output_type}', "
                f"must be one of {sorted(VALID_OUTPUT_TYPES)}"
            )

        params = model_def.get("params", [])
        if not isinstance(params, list):
            raise RegistryError(f"{prefix} ('{name}'): 'params' must be a list")

        for param_index, param in enumerate(params):
            param_prefix = f"{prefix} ('{name}'), param [{param_index}]"
            if not isinstance(param, dict):
                raise RegistryError(f"{param_prefix} must be a JSON object")
            param_missing = REQUIRED_PARAM_FIELDS - param.keys()
            if param_missing:
                raise RegistryError(
                    f"{param_prefix} missing required fields: {sorted(param_missing)}"
                )
            if param["type"] not in VALID_PARAM_TYPES:
                raise RegistryError(
                    f"{param_prefix}: invalid type '{param['type']}', "
                    f"must be one of {sorted(VALID_PARAM_TYPES)}"
                )

        adapter = model_def.get("adapter")
        if adapter and isinstance(adapter, dict):
            if "kind" not in adapter:
                raise RegistryError(
                    f"{prefix} ('{name}'): adapter dict must contain 'kind'"
                )


def _return_signature(output_type: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    mapping = {
        "image": (("IMAGE", "STRING", "STRING"), ("image", "urls", "response")),
        "video": (("VIDEO", "STRING", "STRING"), ("video", "urls", "response")),
        "audio": (("AUDIO", "STRING", "STRING"), ("audio", "urls", "response")),
        "string": (("STRING", "STRING", "STRING"), ("result", "urls", "response")),
    }
    return mapping.get(output_type, mapping["string"])


def _param_tooltip(param: dict[str, Any]) -> str:
    for key in (
        "tooltip_zh",
        "description_zh",
        "tooltip",
        "description",
        "help",
        "notes",
    ):
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


def _iter_param_inputs(
    param: dict[str, Any],
) -> list[tuple[str, tuple[Any, ...], bool]]:
    input_name = param["name"]
    input_def = _build_input_def(param)
    entries = [(input_name, input_def, bool(param.get("required", False)))]

    if param.get("type") not in {"IMAGE", "VIDEO", "AUDIO"}:
        return entries
    if not param.get("multiple_inputs"):
        return entries

    max_inputs = int(param.get("max_inputs", 1))
    if max_inputs <= 1:
        return entries

    for index in range(2, max_inputs + 1):
        entries.append(
            (_extra_input_name(param, index), _clone_input_def(input_def), False)
        )
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

    return_types, return_names = _return_signature(
        model_def.get("output_type", "string")
    )
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

    registry = _load_registry()
    _validate_registry(registry)

    for model_def in registry:
        internal_name = model_def["internal_name"]
        node_class = create_node_class(model_def)
        class_mappings[internal_name] = node_class
        display_mappings[internal_name] = model_def["display_name"]

    return class_mappings, display_mappings
