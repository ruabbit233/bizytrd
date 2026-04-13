"""Base node scaffolding for bizytrd."""

from __future__ import annotations

import json
from abc import ABC
from typing import Any

from .adapters import build_payload_for_model
from .config import get_config
from .result import normalize_result
from .task import poll_task, submit_task


class BizyTRDBaseNode(ABC):
    """Shared base class for registry-generated bizytrd nodes."""

    MODEL_KEY = ""
    MODEL_DEF: dict[str, Any] = {}
    PARAMS: list[dict[str, Any]] = []
    OUTPUT_TYPE = "string"
    FUNCTION = "execute"
    OUTPUT_NODE = True

    def build_payload(self, **kwargs: Any) -> dict[str, Any]:
        model_def = self.MODEL_DEF or {
            "model_key": self.MODEL_KEY,
            "params": self.PARAMS,
        }
        config = get_config()
        return build_payload_for_model(model_def, config, kwargs)

    def execute(self, **kwargs: Any):
        config = get_config()
        payload = self.build_payload(**kwargs)
        request_id, _ = submit_task(self.MODEL_KEY, payload, config)
        poll_payload = poll_task(request_id, config)
        primary, urls_str, response_str = normalize_result(
            self.OUTPUT_TYPE, poll_payload
        )
        return {
            "ui": {"text": [urls_str, response_str]},
            "result": (primary, urls_str, response_str),
        }

    @staticmethod
    def _payload_preview(payload: dict[str, Any]) -> str:
        safe: dict[str, Any] = {}
        for key, value in payload.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                safe[key] = value
            elif isinstance(value, list):
                safe[key] = f"<list:{len(value)}>"
            else:
                safe[key] = f"<{type(value).__name__}>"
        return json.dumps(safe, ensure_ascii=False)
