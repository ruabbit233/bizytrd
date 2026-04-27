import json
from pathlib import Path

from bizytrd.core.adapters import build_payload_for_model


REGISTRY_PATH = Path(__file__).resolve().parents[1] / "models_registry_gpt.json"


def _load_registry():
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _entry_by_name(name):
    for entry in _load_registry():
        if entry["internal_name"] == name:
            return entry
    raise KeyError(name)


def test_gpt_registry_defines_gpt_image_2_nodes():
    entries = {entry["internal_name"]: entry for entry in _load_registry()}

    expected_names = {
        "GPT_IMAGE_2_T2I_API",
        "GPT_IMAGE_2_I2I_API",
        "GPT_IMAGE_2_Official_T2I_API",
        "GPT_IMAGE_2_Official_I2I_API",
    }

    assert expected_names <= set(entries)
    assert entries["GPT_IMAGE_2_T2I_API"]["model_name"] == "gpt-image-2"
    assert entries["GPT_IMAGE_2_I2I_API"]["params"][0]["maxInputNum"] == 10
    assert (
        entries["GPT_IMAGE_2_Official_T2I_API"]["model_name"]
        == "gpt-image-2-official"
    )
    assert entries["GPT_IMAGE_2_Official_I2I_API"]["params"][0]["maxInputNum"] == 16


def test_official_gpt_image_2_payload_maps_aspect_ratio_to_size():
    entry = _entry_by_name("GPT_IMAGE_2_Official_T2I_API")

    payload = build_payload_for_model(
        entry,
        {},
        {
            "prompt": "wide city skyline",
            "aspect_ratio": "21:9",
            "resolution": "4k",
            "quality": "high",
        },
    )

    assert payload == {
        "model": "gpt-image-2-official",
        "prompt": "wide city skyline",
        "size": {"width": 3840, "height": 1648},
        "resolution": "4k",
        "quality": "high",
    }
