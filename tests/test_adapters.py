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


def test_build_payload_always_sends_media_as_lists():
    model_def = {
        "model_name": "seedance-2-0-std",
        "endpoint_category": "Multimodal To Video",
        "params": [
            {
                "name": "image",
                "fieldKey": "imageUrls",
                "type": "IMAGE",
                "required": False,
            },
            {
                "name": "videos",
                "fieldKey": "videoUrls",
                "type": "VIDEO",
                "required": False,
                "maxInputNum": 2,
            },
        ],
    }

    from unittest.mock import patch

    with patch("bizytrd.core.adapters._build_media_context") as build_media_context:
        build_media_context.return_value = {
            "image": {"values": ["image-input"], "urls": ["https://example.com/image"], "count": 1},
            "videos": {
                "values": ["video-a", "video-b"],
                "urls": ["https://example.com/video-a", "https://example.com/video-b"],
                "count": 2,
            },
        }
        payload = build_payload_for_model(model_def, {}, {})

    assert payload["imageUrls"] == ["https://example.com/image"]
    assert payload["videoUrls"] == [
        "https://example.com/video-a",
        "https://example.com/video-b",
    ]


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


def test_registry_removes_legacy_media_payload_metadata():
    import json
    from pathlib import Path

    registry = json.loads(Path("models_registry.json").read_text(encoding="utf-8"))
    forbidden_fields = {
        "flattenBatches",
        "forceList",
        "multipleInputs",
        "mediaItemType",
        "flatten_batches",
        "force_list",
        "multiple_inputs",
        "media_item_type",
    }

    for model_def in registry:
        for param in model_def.get("params", []):
            assert forbidden_fields.isdisjoint(param), (
                model_def["internal_name"],
                param["name"],
            )


def test_registry_removes_legacy_param_compatibility_fields():
    import json
    from pathlib import Path

    registry = json.loads(Path("models_registry.json").read_text(encoding="utf-8"))
    forbidden_fields = {
        "api_field",
        "default",
        "inputcount_param",
        "maxInputCount",
        "max_inputs",
        "only_if_false_param",
        "only_if_media_absent",
        "only_if_media_present",
        "only_if_true_param",
        "send_if",
        "skip_values",
        "value_hook",
    }

    for model_def in registry:
        for param in model_def.get("params", []):
            assert forbidden_fields.isdisjoint(param), (
                model_def["internal_name"],
                param["name"],
            )
