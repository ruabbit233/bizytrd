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


def test_config_consumer_can_decode_json_config_value():
    model_def = {
        "model_name": "kling-o3-t2v",
        "endpoint_category": "Text To Video",
        "params": [
            {
                "name": "multi_prompt",
                "fieldKey": "multi_prompt",
                "type": "STRING",
                "valueHook": "common.json_loads",
                "required": False,
            }
        ],
    }

    payload = build_payload_for_model(
        model_def,
        {},
        {"multi_prompt": '[{"prompt": "first", "duration": 3}]'},
    )

    assert payload["multi_prompt"] == [{"prompt": "first", "duration": 3}]


def test_config_json_hook_passes_through_structured_config_values():
    model_def = {
        "model_name": "doubao-seedream-5-0-260128",
        "endpoint_category": "",
        "params": [
            {
                "name": "tools",
                "fieldKey": "tools",
                "type": "STRING",
                "valueHook": "common.json_loads",
                "required": False,
            }
        ],
    }

    payload = build_payload_for_model(
        model_def,
        {},
        {"tools": ["web_search"]},
    )

    assert payload["tools"] == ["web_search"]


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
                "default": "",
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


def test_build_payload_uses_auto_inputcount_to_limit_media_inputs():
    model_def = {
        "model_name": "seedance-2-0-std",
        "endpoint_category": "Multimodal To Video",
        "params": [
            {
                "name": "images",
                "fieldKey": "imageUrls",
                "type": "IMAGE",
                "required": False,
                "maxInputNum": 4,
            }
        ],
    }

    from unittest.mock import patch

    with patch("bizytrd.core.adapters.upload_image_input") as upload_image_input:
        upload_image_input.side_effect = [
            "https://example.com/image-1",
            "https://example.com/image-2",
        ]
        payload = build_payload_for_model(
            model_def,
            {},
            {
                "images": "image-a",
                "image_2": "image-b",
                "image_3": "image-c",
                "image_4": "image-d",
                "image_inputcount": 2,
            },
        )

    assert payload["imageUrls"] == [
        "https://example.com/image-1",
        "https://example.com/image-2",
    ]
    assert upload_image_input.call_count == 2


def test_value_hook_receives_value_and_context():
    model_def = {
        "model_name": "test-model",
        "endpoint_category": "Text To Image",
        "params": [
            {
                "name": "payload_json",
                "fieldKey": "payload_json",
                "type": "STRING",
                "valueHook": "common.inspect_context",
                "required": False,
            }
        ],
    }

    from unittest.mock import patch

    def inspect_context(value, context):
        return {
            "value": value,
            "param_name": context.param["name"],
            "prompt": context.get("prompt"),
            "resolved_model": context.resolved_model,
            "missing_media": context.get_media("images", {}),
        }

    with patch("bizytrd.core.hooks.common.inspect_context", inspect_context, create=True):
        payload = build_payload_for_model(
            model_def,
            {},
            {"payload_json": "raw", "prompt": "hello"},
        )

    assert payload["payload_json"] == {
        "value": "raw",
        "param_name": "payload_json",
        "prompt": "hello",
        "resolved_model": "test-model",
        "missing_media": {},
    }


def test_hook_context_exposes_generic_getters_only():
    from bizytrd.core.hooks.base import HookContext

    context = HookContext(
        param={"name": "size"},
        inputs={"custom_width": 1024},
        media={"images": {"count": 2, "urls": ["a", "b"]}},
        resolved_model="model",
    )

    assert context.get("custom_width") == 1024
    assert context.get("missing", "fallback") == "fallback"
    assert context.get_media("images") == {"count": 2, "urls": ["a", "b"]}
    assert context.get_media("videos", {}) == {}
    assert not hasattr(context, "input")
    assert not hasattr(context, "media_count")


def test_not_default_send_condition_uses_default_field():
    model_def = {
        "model_name": "test-model",
        "endpoint_category": "Text To Image",
        "params": [
            {
                "name": "style",
                "fieldKey": "style",
                "type": "STRING",
                "required": False,
                "default": "default",
                "sendIf": "not_default",
            }
        ],
    }

    assert "style" not in build_payload_for_model(model_def, {}, {"style": "default"})
    assert build_payload_for_model(model_def, {}, {"style": "cinematic"})["style"] == "cinematic"


def test_hidden_param_uses_default_value_in_payload():
    model_def = {
        "model_name": "test-model",
        "endpoint_category": "Text To Image",
        "params": [
            {
                "name": "watermark",
                "fieldKey": "watermark",
                "type": "BOOLEAN",
                "required": False,
                "default": False,
                "hidden": True,
            }
        ],
    }

    payload = build_payload_for_model(model_def, {}, {})

    assert payload["watermark"] is False


def test_hidden_param_can_still_use_value_hook_and_send_condition():
    model_def = {
        "model_name": "test-model",
        "endpoint_category": "Text To Image",
        "params": [
            {
                "name": "metadata",
                "fieldKey": "metadata",
                "type": "STRING",
                "required": False,
                "default": '{"source": "bizytrd"}',
                "hidden": True,
                "valueHook": "common.json_loads",
                "sendIf": "non_empty",
            }
        ],
    }

    payload = build_payload_for_model(model_def, {}, {})

    assert payload["metadata"] == {"source": "bizytrd"}


def test_hidden_duration_param_can_read_video_duration_with_hook():
    class VideoInput:
        def get_duration(self):
            return 12.5

    model_def = {
        "model_name": "dreamactor-2-0",
        "endpoint_category": "Dream Actor",
        "params": [
            {
                "name": "video",
                "fieldKey": "video",
                "type": "VIDEO",
                "required": True,
            },
            {
                "name": "duration",
                "fieldKey": "duration",
                "type": "FLOAT",
                "required": False,
                "hidden": True,
                "valueHook": "doubao.video_duration",
            },
        ],
    }

    from unittest.mock import patch

    video = VideoInput()
    with patch("bizytrd.core.adapters._build_media_context") as build_media_context:
        build_media_context.return_value = {
            "video": {
                "values": [video],
                "urls": ["https://example.com/video.mp4"],
                "count": 1,
            }
        }
        payload = build_payload_for_model(model_def, {}, {"video": video})

    assert payload["video"] == ["https://example.com/video.mp4"]
    assert payload["duration"] == 12.5


def test_internal_param_remains_visible_but_is_not_sent_to_payload():
    model_def = {
        "model_name": "test-model",
        "endpoint_category": "Text To Image",
        "params": [
            {
                "name": "custom_width",
                "fieldKey": "custom_width",
                "type": "INT",
                "required": False,
                "default": 1024,
                "internal": True,
            }
        ],
    }

    payload = build_payload_for_model(model_def, {}, {"custom_width": 2048})

    assert "custom_width" not in payload


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
        "defaultValue",
        "inputcountParam",
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
