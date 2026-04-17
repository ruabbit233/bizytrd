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
                "valueHook": "json_loads",
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
