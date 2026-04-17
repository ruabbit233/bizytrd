from bizytrd.core.adapters import build_payload_for_model


def test_build_payload_uses_value_hook_instead_of_transform():
    model_def = {
        "model_name": "wan2.7-image",
        "endpoint_category": "Text To Image",
        "params": [
            {
                "name": "payload_json",
                "fieldKey": "payload_json",
                "type": "STRING",
                "valueHook": "common.json_loads",
                "required": False,
            }
        ],
    }

    payload = build_payload_for_model(
        model_def,
        {},
        {"payload_json": '{"a": 1}'},
    )

    assert payload["model"] == "wan2.7-image"
    assert payload["payload_json"] == {"a": 1}


def test_build_payload_appends_normalized_channel_to_model_name():
    model_def = {
        "model_name": "nano-banana-pro",
        "endpoint_category": "Image To Image",
        "params": [
            {
                "name": "channel",
                "fieldKey": "channel",
                "type": "LIST",
                "required": False,
                "defaultValue": "",
                "options": ["", "Official API", "base_v2"],
            }
        ],
    }

    payload = build_payload_for_model(model_def, {}, {"channel": "Official API"})

    assert payload["model"] == "nano-banana-pro-official-api"


def test_build_payload_uses_model_name_without_request_model_overrides():
    model_def = {
        "model_name": "seedance-2-0-std",
        "endpoint_category": "Multimodal To Video",
        "params": [
            {
                "name": "prompt",
                "fieldKey": "prompt",
                "type": "STRING",
                "required": False,
            }
        ],
    }

    payload = build_payload_for_model(model_def, {}, {"prompt": "test"})

    assert payload["model"] == "seedance-2-0-std"


def test_registry_uses_script_path_value_hooks():
    import json
    from pathlib import Path

    registry = json.loads(Path("models_registry.json").read_text(encoding="utf-8"))

    hook_values = []
    for model_def in registry:
        for param in model_def.get("params", []):
            hook_name = param.get("valueHook")
            if hook_name:
                hook_values.append(hook_name)

    assert hook_values
    assert all("." in hook_name for hook_name in hook_values)


def test_registry_removes_hook_param_metadata():
    import json
    from pathlib import Path

    registry = json.loads(Path("models_registry.json").read_text(encoding="utf-8"))
    forbidden_fields = {
        "hookModelParam",
        "hookWidthParam",
        "hookHeightParam",
        "hookMediaParam",
        "hookSequentialParam",
        "hook_model_param",
        "hook_width_param",
        "hook_height_param",
        "hook_media_param",
        "hook_sequential_param",
    }

    for model_def in registry:
        for param in model_def.get("params", []):
            assert forbidden_fields.isdisjoint(param), (
                model_def["internal_name"],
                param["name"],
            )
