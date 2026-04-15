# Registry Endpoint Assembly Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update the registry-driven ComfyUI node pipeline so endpoints are assembled from `model_name` and `endpoint_category`, media input count widgets are inferred automatically for `images`/`videos`/`audios`, and registry-side transform logic is replaced by a small predefined hook system.

**Architecture:** Keep ComfyUI menu `category` as a presentation-only field and add backend routing metadata at the model level. Build node UI from registry metadata plus deterministic media conventions, then have the base node resolve endpoint strings just before task submission. Simplify payload building so registry stays declarative, with only a bounded set of named hooks for exceptional cases.

**Tech Stack:** Python 3.10, pytest, registry JSON, ComfyUI node metadata, frontend dynamic input JavaScript

---

### Task 1: Lock Endpoint And Inputcount Behavior With Tests

**Files:**
- Create: `tests/test_node_factory.py`
- Test: `tests/test_node_factory.py`

- [ ] **Step 1: Write the failing tests**

```python
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
                "api_field": "channel",
                "type": "LIST",
                "required": False,
                "default": "",
                "options": ["", "official", "base"],
            },
            {
                "name": "images",
                "api_field": "images",
                "type": "IMAGE",
                "required": False,
                "multiple_inputs": True,
                "maxInputCount": 4,
            },
        ],
    }

    node_cls = create_node_class(model_def)
    input_types = node_cls.INPUT_TYPES()

    assert "channel" in input_types["optional"]
    assert "image_inputcount" in input_types["optional"]
    assert "image_2" in input_types["optional"]


def test_resolve_endpoint_appends_channel_suffix_and_normalizes_category():
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
                "api_field": "channel",
                "type": "LIST",
                "required": False,
                "default": "",
                "options": ["", "official", "base"],
            }
        ],
    }

    node_cls = create_node_class(model_def)
    node = node_cls()

    assert node.resolve_endpoint(channel="official") == "nano-banana-pro-official/image-to-image"
    assert node.resolve_endpoint(channel="") == "nano-banana-pro/image-to-image"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_node_factory.py -v`
Expected: FAIL because auto-generated inputcount widgets and `resolve_endpoint()` do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
# node_factory.py
# add automatic count widget injection for plural media names and maxInputCount

# core/base.py
# add resolve_endpoint(**kwargs) and use it when creating tasks
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_node_factory.py -v`
Expected: PASS

### Task 2: Lock Hook-Based Payload Builder Behavior

**Files:**
- Create: `tests/test_adapters.py`
- Modify: `core/adapters.py`
- Test: `tests/test_adapters.py`

- [ ] **Step 1: Write the failing tests**

```python
from bizytrd.core.adapters import build_payload_for_model


def test_build_payload_uses_value_hook_instead_of_transform():
    model_def = {
        "model_name": "wan2.7-image",
        "endpoint_category": "Text To Image",
        "params": [
            {
                "name": "payload_json",
                "api_field": "payload_json",
                "type": "STRING",
                "value_hook": "json_loads",
                "required": False,
            }
        ],
    }

    payload = build_payload_for_model(model_def, {}, {"payload_json": "{\"a\":1}"})

    assert payload["model"] == "wan2.7-image"
    assert payload["payload_json"] == {"a": 1}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_adapters.py -v`
Expected: FAIL because `value_hook` is not implemented yet.

- [ ] **Step 3: Write minimal implementation**

```python
# adapters.py
# replace transform dispatch with a bounded HOOKS map
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_adapters.py -v`
Expected: PASS

### Task 3: Migrate Registry And JS Dynamic Input Assumptions

**Files:**
- Modify: `models_registry.json`
- Modify: `web/js/dynamic_inputs.js`
- Modify: `docs/MODELS_REGISTRY_GUIDE.md`
- Modify: `docs/ADAPTERS.md`

- [ ] **Step 1: Update registry schema usage**

```json
{
  "model_name": "nano-banana-pro",
  "endpoint_category": "Image To Image",
  "params": [
    {
      "name": "channel",
      "type": "LIST",
      "options": ["", "official", "base"]
    },
    {
      "name": "images",
      "type": "IMAGE",
      "multiple_inputs": true,
      "maxInputCount": 4
    }
  ]
}
```

- [ ] **Step 2: Align frontend dynamic input logic**

Run: update `web/js/dynamic_inputs.js` so group discovery accepts auto-generated `image_inputcount` / `video_inputcount` / `audio_inputcount` widgets and uses `maxInputCount` from node metadata-derived extra slots.
Expected: dynamic connectors remain stable after node creation and configure.

- [ ] **Step 3: Update docs**

Run: document `model_name`, `endpoint_category`, optional `channel`, automatic inputcount generation, and `value_hook` / model hook semantics while removing `transform` guidance.
Expected: docs match runtime behavior.

### Task 4: Verify End-To-End Regression Surface

**Files:**
- Test: `tests/test_node_factory.py`
- Test: `tests/test_adapters.py`

- [ ] **Step 1: Run focused test suite**

Run: `pytest tests/test_node_factory.py tests/test_adapters.py -v`
Expected: PASS

- [ ] **Step 2: Run full project tests**

Run: `pytest -v`
Expected: PASS

- [ ] **Step 3: Review diff for accidental registry logic regressions**

Run: `git diff -- core/adapters.py core/base.py nodes/node_factory.py models_registry.json web/js/dynamic_inputs.js docs/MODELS_REGISTRY_GUIDE.md docs/ADAPTERS.md tests/test_node_factory.py tests/test_adapters.py`
Expected: only the intended endpoint assembly, auto inputcount, hook-system, and docs changes appear.
