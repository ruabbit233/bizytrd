from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = (
    PROJECT_ROOT.parent / "bizyengine" / "bizyengine" / "bizyair_extras" / "third_party_api"
)
OUTPUT_PATH = PROJECT_ROOT / "models_registry_migrated.json"

MEDIA_TYPES = {"IMAGE", "VIDEO", "AUDIO"}
TYPE_NAMES = MEDIA_TYPES | {"STRING", "INT", "FLOAT", "BOOLEAN", "LIST"}


def _class_name_to_registry_class_name(name: str) -> str:
    parts = re.split(r"[^0-9A-Za-z]+", name)
    normalized = "".join(part[:1].upper() + part[1:] for part in parts if part)
    return f"BizyTRD{normalized or name}"


def _provider_category(raw_category: str | None) -> str:
    tail = str(raw_category or "").split("/")[-1].strip()
    mapping = {
        "WanVideo": "Wan",
        "WanImage": "Wan",
        "OpenAI": "OpenAI",
        "LLm Tools": "LLM",
    }
    return f"BizyTRD/{mapping.get(tail, tail or 'Migrated')}"


def _endpoint_category_from_class_name(class_name: str) -> str:
    upper = class_name.upper()
    if "VIDEO_EDIT" in upper or "VIDEOEDIT" in upper:
        return "Video Edit"
    if "DREAMACTOR" in upper:
        return "Dream Actor"
    if "VI2V_REF" in upper or "I2V_REF" in upper or "REF_API" in upper or "R2V" in upper:
        return "Reference To Video"
    if "T2V" in upper:
        return "Text To Video"
    if "I2V" in upper:
        return "Image To Video"
    if "I2I" in upper:
        return "Image To Image"
    if "T2I" in upper:
        return "Text To Image"
    if "VLM" in upper:
        return "Image To Text"
    if "LLM" in upper:
        return "Chat"
    return ""


def _slugify_name(value: str) -> str:
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", value)
    text = re.sub(r"[^0-9A-Za-z]+", "-", text)
    return text.strip("-").lower()


def _safe_literal(node: ast.AST | None) -> Any:
    if node is None:
        return None
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def _constant_dict(node: ast.AST | None) -> dict[str, Any]:
    value = _safe_literal(node)
    return value if isinstance(value, dict) else {}


def _constant_list(node: ast.AST | None) -> list[Any]:
    value = _safe_literal(node)
    return value if isinstance(value, list) else []


def _extract_class_attrs(class_def: ast.ClassDef) -> dict[str, ast.AST]:
    attrs: dict[str, ast.AST] = {}
    for stmt in class_def.body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    attrs[target.id] = stmt.value
    return attrs


def _extract_input_types_dict(class_def: ast.ClassDef) -> ast.Dict | None:
    for stmt in class_def.body:
        if not isinstance(stmt, ast.FunctionDef) or stmt.name != "INPUT_TYPES":
            continue
        dict_returns = [
            node.value
            for node in ast.walk(stmt)
            if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict)
        ]
        if dict_returns:
            return dict_returns[-1]
    return None


def _dict_items(node: ast.Dict | None) -> list[tuple[Any, ast.AST]]:
    if node is None:
        return []
    items: list[tuple[Any, ast.AST]] = []
    for key_node, value_node in zip(node.keys, node.values):
        key = _safe_literal(key_node)
        items.append((key, value_node))
    return items


def _extract_meta(meta_node: ast.AST | None) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    if not isinstance(meta_node, ast.Dict):
        return meta
    for key_node, value_node in zip(meta_node.keys, meta_node.values):
        key = _safe_literal(key_node)
        if not isinstance(key, str):
            continue
        value = _safe_literal(value_node)
        if value is None and isinstance(value_node, (ast.List, ast.Tuple)):
            value = _safe_literal(value_node)
        meta[key] = value
    return meta


def _param_type_from_node(value_node: ast.AST) -> tuple[str, list[Any] | None]:
    value = _safe_literal(value_node)
    if isinstance(value, str):
        return (value if value in TYPE_NAMES else "STRING"), None
    if isinstance(value, (list, tuple)):
        return "LIST", list(value)
    if isinstance(value_node, ast.Name):
        return "LIST", []
    return "STRING", None


def _build_param(name: str, value_node: ast.AST, required: bool) -> dict[str, Any]:
    tuple_node = value_node if isinstance(value_node, ast.Tuple) else ast.Tuple(elts=[value_node], ctx=ast.Load())
    value_elts = list(tuple_node.elts)
    type_node = value_elts[0] if value_elts else ast.Constant(value="STRING")
    meta_node = value_elts[1] if len(value_elts) > 1 else None

    param_type, options = _param_type_from_node(type_node)
    meta = _extract_meta(meta_node)

    param: dict[str, Any] = {
        "name": name,
        "fieldKey": name,
        "type": param_type,
        "required": required,
    }

    if param_type == "LIST":
        param["options"] = options or []

    default_value = meta.get("default")
    if default_value is not None:
        param["defaultValue"] = default_value

    description = meta.get("tooltip") or meta.get("description")
    if isinstance(description, str) and description.strip():
        param["description"] = description.strip()

    if bool(meta.get("multiline")):
        param["multiline"] = True

    for key in ("min", "max", "step"):
        value = meta.get(key)
        if value is not None:
            param[key] = value

    return param


def _parse_params(class_def: ast.ClassDef) -> tuple[list[dict[str, Any]], list[str]]:
    input_types = _extract_input_types_dict(class_def)
    if input_types is None:
        return [], ["INPUT_TYPES is dynamic or unavailable; params left empty."]

    params: list[dict[str, Any]] = []
    notes: list[str] = []
    top_level = dict(_dict_items(input_types))
    required_node = top_level.get("required")
    optional_node = top_level.get("optional")

    for section_name, section_node in (("required", required_node), ("optional", optional_node)):
        for key, value in _dict_items(section_node if isinstance(section_node, ast.Dict) else None):
            if not isinstance(key, str):
                continue
            params.append(_build_param(key, value, section_name == "required"))

    if not params:
        notes.append("No static params extracted from INPUT_TYPES.")
    return _normalize_media_params(params), notes


def _normalize_media_params(params: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for param in params:
        match = re.fullmatch(r"(image|video|audio)(\d+)?", str(param.get("name") or ""))
        if match and param.get("type") in MEDIA_TYPES:
            grouped.setdefault(match.group(1), []).append(param)

    normalized: list[dict[str, Any]] = []
    consumed: set[int] = set()

    for index, param in enumerate(params):
        if index in consumed:
            continue

        name = str(param.get("name") or "")
        match = re.fullmatch(r"(image|video|audio)(\d+)?", name)
        if not match or param.get("type") not in MEDIA_TYPES:
            normalized.append(param)
            continue

        base = match.group(1)
        group = grouped.get(base, [])
        if len(group) <= 1:
            normalized.append(param)
            continue

        indices = []
        for candidate in group:
            candidate_index = params.index(candidate)
            indices.append(candidate_index)
            consumed.add(candidate_index)

        plural_name = f"{base}s"
        collapsed = dict(param)
        collapsed["name"] = plural_name
        collapsed["fieldKey"] = f"{base}Urls"
        collapsed["multipleInputs"] = True
        collapsed["maxInputNum"] = len(group)
        normalized.append(collapsed)

    if any(param.get("name") == "inputcount" for param in normalized):
        for param in normalized:
            if param.get("name") in {"image", "images", "video", "videos", "audio", "audios"}:
                param["multipleInputs"] = True
                param["inputcountParam"] = "inputcount"
                for count_param in normalized:
                    if count_param.get("name") == "inputcount" and count_param.get("max") is not None:
                        param["maxInputNum"] = count_param["max"]
    return normalized


def _output_type_from_attrs(attrs: dict[str, ast.AST]) -> str:
    return_types = _safe_literal(attrs.get("RETURN_TYPES"))
    if isinstance(return_types, tuple) and return_types:
        first = str(return_types[0]).upper()
        if first in {"IMAGE", "VIDEO", "AUDIO", "STRING"}:
            return first.lower()
    return "string"


def _model_name_from_attrs(attrs: dict[str, ast.AST], params: list[dict[str, Any]], class_name: str) -> str:
    return_types = _safe_literal(attrs.get("RETURN_TYPES"))
    if isinstance(return_types, tuple) and return_types:
        last = return_types[-1]
        if isinstance(last, str):
            try:
                mapping = json.loads(last)
            except Exception:
                mapping = None
            if isinstance(mapping, dict) and mapping:
                first_value = next(iter(mapping.values()))
                if isinstance(first_value, str) and first_value.strip():
                    return first_value.strip()

    for param in params:
        if param.get("name") == "model":
            options = param.get("options") or []
            if options:
                return str(options[0])

    return _slugify_name(class_name)


def _entry_for_class(path: Path, class_def: ast.ClassDef) -> dict[str, Any]:
    attrs = _extract_class_attrs(class_def)
    params, notes = _parse_params(class_def)
    display_name = _safe_literal(attrs.get("NODE_DISPLAY_NAME")) or class_def.name
    function_name = _safe_literal(attrs.get("FUNCTION")) or "api_call"

    if function_name != "api_call":
        notes.append(f"Legacy node uses FUNCTION={function_name}.")

    input_types_node = _extract_input_types_dict(class_def)
    if input_types_node is not None:
        source = ast.get_source_segment(path.read_text(encoding="utf-8"), input_types_node) or ""
        if "models_list" in source:
            notes.append("Contains dynamic model options in INPUT_TYPES.")

    entry = {
        "internal_name": f"BizyTRD_{class_def.name}",
        "class_name": _class_name_to_registry_class_name(class_def.name),
        "display_name": display_name,
        "category": _provider_category(_safe_literal(attrs.get("CATEGORY"))),
        "model_name": _model_name_from_attrs(attrs, params, class_def.name),
        "endpoint_category": _endpoint_category_from_class_name(class_def.name),
        "output_type": _output_type_from_attrs(attrs),
        "params": params,
        "migration_source": {
            "file": f"bizyengine/bizyengine/bizyair_extras/third_party_api/{path.name}",
            "class": class_def.name,
        },
    }

    if notes:
        entry["migration_notes"] = notes

    return entry


def _load_entries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in sorted(SOURCE_ROOT.glob("*.py")):
        if path.name in {"__init__.py", "trd_nodes_base.py"}:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            if not any(
                isinstance(base, ast.Name) and base.id == "BizyAirTrdApiBaseNode"
                for base in node.bases
            ):
                continue
            entries.append(_entry_for_class(path, node))
    return entries


def main() -> None:
    entries = _load_entries()
    OUTPUT_PATH.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(entries)} entries to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
