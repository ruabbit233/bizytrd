import json
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = (
    PROJECT_ROOT.parent / "bizyengine" / "bizyengine" / "bizyair_extras" / "third_party_api"
)
MIGRATED_REGISTRY_PATH = PROJECT_ROOT / "models_registry_migrated.json"


def _source_class_names() -> set[str]:
    pattern = re.compile(r"^class\s+(\w+)\(BizyAirTrdApiBaseNode\):", re.MULTILINE)
    names: set[str] = set()
    for path in SOURCE_ROOT.glob("*.py"):
        names.update(pattern.findall(path.read_text(encoding="utf-8")))
    return names


def test_migrated_registry_exists_and_covers_all_source_nodes():
    assert MIGRATED_REGISTRY_PATH.exists()

    registry = json.loads(MIGRATED_REGISTRY_PATH.read_text(encoding="utf-8"))
    assert isinstance(registry, list)
    assert registry

    migrated_classes = {
        (entry.get("migration_source") or {}).get("class")
        for entry in registry
    }

    assert _source_class_names().issubset(migrated_classes)


def test_migrated_registry_contains_representative_entries():
    registry = json.loads(MIGRATED_REGISTRY_PATH.read_text(encoding="utf-8"))
    migrated_classes = {
        (entry.get("migration_source") or {}).get("class")
        for entry in registry
    }

    expected = {
        "Wan_V2_5_I2V_API",
        "Seedance_2_0_Multimodal_API",
        "TRD_LLM_API",
        "TRD_VLM_API",
        "Kling_O3_VIDEO_EDIT_API",
        "Grok_Imagine_Video_Edit_Official_API",
    }

    assert expected.issubset(migrated_classes)
