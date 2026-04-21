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
                "default": "",
                "options": ["", "official", "base"],
            },
            {
                "name": "images",
                "fieldKey": "images",
                "type": "IMAGE",
                "required": False,
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


def test_input_types_sorts_optional_inputs_with_media_then_channel_then_widgets():
    model_def = {
        "internal_name": "BizyTRD_TestSortedNode",
        "class_name": "BizyTRDTestSortedNode",
        "display_name": "BizyTRD Test Sorted Node",
        "category": "BizyTRD/Test",
        "model_name": "nano-banana-pro",
        "endpoint_category": "Image To Image",
        "params": [
            {
                "name": "style",
                "fieldKey": "style",
                "type": "LIST",
                "required": False,
                "default": "general",
                "options": ["general", "anime"],
            },
            {
                "name": "audio",
                "fieldKey": "audioUrls",
                "type": "AUDIO",
                "required": False,
                "maxInputNum": 2,
            },
            {
                "name": "negative_prompt",
                "fieldKey": "negative_prompt",
                "type": "STRING",
                "required": False,
            },
            {
                "name": "channel",
                "fieldKey": "channel",
                "type": "LIST",
                "required": False,
                "default": "",
                "options": ["", "official"],
            },
            {
                "name": "video",
                "fieldKey": "videoUrls",
                "type": "VIDEO",
                "required": False,
                "maxInputNum": 2,
            },
            {
                "name": "prompt",
                "fieldKey": "prompt",
                "type": "STRING",
                "required": False,
            },
            {
                "name": "images",
                "fieldKey": "imageUrls",
                "type": "IMAGE",
                "required": False,
                "maxInputNum": 2,
            },
        ],
    }

    node_cls = create_node_class(model_def)
    optional_keys = list(node_cls.INPUT_TYPES()["optional"].keys())

    assert optional_keys == [
        "image_inputcount",
        "images",
        "image_2",
        "video_inputcount",
        "video",
        "video_2",
        "audio_inputcount",
        "audio",
        "audio_2",
        "channel",
        "prompt",
        "negative_prompt",
        "style",
    ]


def test_input_types_keeps_required_media_before_required_channel_and_widgets():
    model_def = {
        "internal_name": "BizyTRD_TestRequiredOrderNode",
        "class_name": "BizyTRDTestRequiredOrderNode",
        "display_name": "BizyTRD Test Required Order Node",
        "category": "BizyTRD/Test",
        "model_name": "seedance-2-0-std",
        "endpoint_category": "Multimodal To Video",
        "params": [
            {
                "name": "prompt",
                "fieldKey": "prompt",
                "type": "STRING",
                "required": True,
            },
            {
                "name": "channel",
                "fieldKey": "channel",
                "type": "LIST",
                "required": True,
                "default": "",
                "options": ["", "fast-lane"],
            },
            {
                "name": "image",
                "fieldKey": "imageUrl",
                "type": "IMAGE",
                "required": True,
            },
            {
                "name": "negative_prompt",
                "fieldKey": "negative_prompt",
                "type": "STRING",
                "required": True,
            },
        ],
    }

    node_cls = create_node_class(model_def)
    required_keys = list(node_cls.INPUT_TYPES()["required"].keys())

    assert required_keys == [
        "image",
        "channel",
        "prompt",
        "negative_prompt",
    ]


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
                "default": "",
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
                "maxInputNum": 3,
            }
        ],
    }

    node_cls = create_node_class(model_def)
    input_types = node_cls.INPUT_TYPES()

    assert "video_inputcount" in input_types["optional"]
    assert "video_2" in input_types["optional"]
    assert "video_3" in input_types["optional"]


def test_string_input_can_be_forced_to_socket_for_config_consumers():
    model_def = {
        "internal_name": "BizyTRD_ConfigConsumer",
        "class_name": "BizyTRDConfigConsumer",
        "display_name": "BizyTRD Config Consumer",
        "category": "BizyTRD/Test",
        "model_name": "config-consumer",
        "endpoint_category": "Chat",
        "params": [
            {
                "name": "tools",
                "fieldKey": "tools",
                "type": "STRING",
                "required": False,
                "default": "[]",
                "forceInput": True,
                "description": "Config JSON from a manual config node.",
            }
        ],
    }

    node_cls = create_node_class(model_def)
    input_def = node_cls.INPUT_TYPES()["optional"]["tools"]

    assert input_def == (
        "STRING",
        {
            "default": "[]",
            "multiline": False,
            "description": "Config JSON from a manual config node.",
            "forceInput": True,
        },
    )


def test_numeric_inputs_preserve_step_metadata():
    model_def = {
        "internal_name": "BizyTRD_StepNode",
        "class_name": "BizyTRDStepNode",
        "display_name": "BizyTRD Step Node",
        "category": "BizyTRD/Test",
        "model_name": "step-model",
        "endpoint_category": "Text To Image",
        "params": [
            {
                "name": "temperature",
                "fieldKey": "temperature",
                "type": "FLOAT",
                "required": False,
                "default": 1.0,
                "min": 0.0,
                "max": 2.0,
                "step": 0.05,
            },
            {
                "name": "steps",
                "fieldKey": "steps",
                "type": "INT",
                "required": False,
                "default": 50,
                "min": 1,
                "max": 100,
                "step": 5,
            },
        ],
    }

    node_cls = create_node_class(model_def)
    input_types = node_cls.INPUT_TYPES()

    assert input_types["optional"]["temperature"][1]["step"] == 0.05
    assert input_types["optional"]["steps"][1]["step"] == 5


def test_hidden_params_are_not_exposed_in_input_types():
    model_def = {
        "internal_name": "BizyTRD_HiddenParamNode",
        "class_name": "BizyTRDHiddenParamNode",
        "display_name": "BizyTRD Hidden Param Node",
        "category": "BizyTRD/Test",
        "model_name": "hidden-param-model",
        "endpoint_category": "Text To Image",
        "params": [
            {
                "name": "prompt",
                "fieldKey": "prompt",
                "type": "STRING",
                "required": True,
            },
            {
                "name": "watermark",
                "fieldKey": "watermark",
                "type": "BOOLEAN",
                "required": False,
                "default": False,
                "hidden": True,
            },
        ],
    }

    node_cls = create_node_class(model_def)
    input_types = node_cls.INPUT_TYPES()

    assert "prompt" in input_types["required"]
    assert "watermark" not in input_types["required"]
    assert "watermark" not in input_types["optional"]


def test_hidden_params_can_omit_widget_type():
    model_def = {
        "internal_name": "BizyTRD_HiddenTypelessParamNode",
        "class_name": "BizyTRDHiddenTypelessParamNode",
        "display_name": "BizyTRD Hidden Typeless Param Node",
        "category": "BizyTRD/Test",
        "model_name": "hidden-typeless-param-model",
        "endpoint_category": "Text To Image",
        "params": [
            {
                "name": "watermark",
                "fieldKey": "watermark",
                "hidden": True,
                "default": False,
            },
        ],
    }

    node_cls = create_node_class(model_def)

    assert node_cls.INPUT_TYPES() == {"required": {}, "optional": {}}


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
        "flatten_batches",
        "hook_height_param",
        "hook_media_param",
        "hook_sequential_param",
        "hook_width_param",
        "inputcountParam",
        "inputcount_param",
        "maxInputCount",
        "max_inputs",
        "media_item_type",
        "only_if_media_present",
        "only_if_true_param",
        "only_if_false_param",
        "only_if_media_absent",
        "send_if",
        "skip_values",
        "value_hook",
        "defaultValue",
    }

    for model_def in registry:
        for param in model_def.get("params", []):
            assert forbidden_param_fields.isdisjoint(param), (
                model_def["internal_name"],
                param["name"],
            )


def test_registry_params_are_flat_objects_with_required_schema():
    registry = json.loads(Path("models_registry.json").read_text(encoding="utf-8"))

    for model_def in registry:
        for index, param in enumerate(model_def.get("params", [])):
            assert isinstance(param, dict), (model_def["internal_name"], index, param)
            assert "name" in param, (model_def["internal_name"], index, param)
            assert "type" in param or param.get("hidden") is True, (
                model_def["internal_name"],
                param["name"],
            )
            assert isinstance(param["name"], str) and param["name"].strip(), (
                model_def["internal_name"],
                index,
                param,
            )


def test_registry_uses_default_field_not_default_value():
    registry = json.loads(Path("models_registry.json").read_text(encoding="utf-8"))

    has_default = False
    for model_def in registry:
        for param in model_def.get("params", []):
            assert "defaultValue" not in param, (model_def["internal_name"], param["name"])
            has_default = has_default or "default" in param

    assert has_default


def test_create_node_class_reports_invalid_param_schema():
    from bizytrd.nodes.node_factory import create_node_class

    model_def = {
        "internal_name": "InvalidNode",
        "class_name": "InvalidNode",
        "display_name": "Invalid Node",
        "category": "BizyTRD/Test",
        "model_name": "invalid-model",
        "endpoint_category": "Text To Image",
        "output_type": "image",
        "params": [{"image": {"name": "image", "type": "IMAGE"}}],
    }

    try:
        create_node_class(model_def)
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("create_node_class should reject invalid param schema")

    assert "InvalidNode" in message
    assert "params[0]" in message
    assert "missing required key 'name'" in message


def test_dynamic_inputs_extension_matches_bizytrd_category_nodes():
    source = Path("web/js/dynamic_inputs.js").read_text(encoding="utf-8")

    assert 'nodeData?.category || ""' in source
    assert 'startsWith("BizyTRD/")' in source
