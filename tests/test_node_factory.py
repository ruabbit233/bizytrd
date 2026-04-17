import json
from pathlib import Path

from bizytrd.nodes.node_factory import create_node_class


def test_input_types_adds_channel_and_auto_media_inputcount():
    model_def = {
        "internal_name": "BizyTRD_TestNode",
        "class_name": "BizyTRDTestNode",
        "display_name": "BizyTRD Test Node",
        "category": "BizyTRD/Test",
        "model_name": "nano-banana-pro",
        "endpoint_category": "Image To Image",
        "params": [
            {
                "name": "channel",
                "fieldKey": "channel",
                "type": "LIST",
                "required": False,
                "defaultValue": "",
                "options": ["", "official", "base"],
            },
            {
                "name": "images",
                "fieldKey": "images",
                "type": "IMAGE",
                "required": False,
                "multipleInputs": True,
                "maxInputNum": 4,
            },
        ],
    }

    node_cls = create_node_class(model_def)
    input_types = node_cls.INPUT_TYPES()

    assert "channel" in input_types["optional"]
    assert "image_inputcount" in input_types["optional"]
    assert "image_2" in input_types["optional"]
    assert "image_3" in input_types["optional"]
    assert "image_4" in input_types["optional"]


def test_resolve_endpoint_appends_normalized_channel_and_normalizes_category():
    model_def = {
        "internal_name": "BizyTRD_TestNode",
        "class_name": "BizyTRDTestNode",
        "display_name": "BizyTRD Test Node",
        "category": "BizyTRD/Test",
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

    node_cls = create_node_class(model_def)
    node = node_cls()

    assert node.resolve_endpoint(channel="Official API") == (
        "nano-banana-pro-official-api/image-to-image"
    )
    assert node.resolve_endpoint(channel="base_v2") == (
        "nano-banana-pro-base-v2/image-to-image"
    )
    assert node.resolve_endpoint(channel="") == "nano-banana-pro/image-to-image"


def test_input_types_adds_auto_inputcount_for_singular_video_name():
    model_def = {
        "internal_name": "BizyTRD_TestVideoNode",
        "class_name": "BizyTRDTestVideoNode",
        "display_name": "BizyTRD Test Video Node",
        "category": "BizyTRD/Test",
        "model_name": "seedance-2-0-std",
        "endpoint_category": "Multimodal To Video",
        "params": [
            {
                "name": "video",
                "fieldKey": "videoUrls",
                "type": "VIDEO",
                "required": False,
                "multipleInputs": True,
                "maxInputNum": 3,
            }
        ],
    }

    node_cls = create_node_class(model_def)
    input_types = node_cls.INPUT_TYPES()

    assert "video_inputcount" in input_types["optional"]
    assert "video_2" in input_types["optional"]
    assert "video_3" in input_types["optional"]


def test_resolve_endpoint_falls_back_to_legacy_api_node_without_endpoint_category():
    model_def = {
        "internal_name": "BizyTRD_LegacyNode",
        "class_name": "BizyTRDLegacyNode",
        "display_name": "BizyTRD Legacy Node",
        "category": "BizyTRD/Test",
        "model_name": "legacy-endpoint",
        "params": [],
    }

    node_cls = create_node_class(model_def)
    node = node_cls()

    assert node.resolve_endpoint() == "legacy-endpoint"


def test_registry_removes_runtime_logic_fields():
    registry = json.loads(Path("models_registry.json").read_text(encoding="utf-8"))

    forbidden_fields = {
        "api_node",
        "request_model",
        "request_model_from",
        "require_any_of",
        "require_any_message",
    }

    for model_def in registry:
        assert forbidden_fields.isdisjoint(model_def), model_def["internal_name"]


def test_registry_removes_channel_metadata_aliases():
    registry = json.loads(Path("models_registry.json").read_text(encoding="utf-8"))

    forbidden_fields = {
        "channelParam",
        "channel_param",
        "channelSuffixMap",
        "channel_suffix_map",
    }

    for model_def in registry:
        assert forbidden_fields.isdisjoint(model_def), model_def["internal_name"]


def test_registry_uses_camel_case_param_metadata_keys():
    registry = json.loads(Path("models_registry.json").read_text(encoding="utf-8"))

    forbidden_param_fields = {
        "api_field",
        "default",
        "flatten_batches",
        "hook_height_param",
        "hook_media_param",
        "hook_sequential_param",
        "hook_width_param",
        "maxInputCount",
        "media_item_type",
        "multiple_inputs",
        "only_if_false_param",
        "only_if_media_absent",
        "send_if",
        "value_hook",
    }

    for model_def in registry:
        for param in model_def.get("params", []):
            assert forbidden_param_fields.isdisjoint(param), (
                model_def["internal_name"],
                param["name"],
            )
