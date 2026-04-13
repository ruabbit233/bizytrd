"""Base node scaffolding for bizytrd."""

from __future__ import annotations

import json
from abc import ABC
from typing import Any

from bizytrd_sdk import BizyTRDClient

from .adapters import build_payload_for_model
from .config_compat import create_client
from .result import normalize_result
from .upload_compat import register_comfyui_media_handlers

_client: BizyTRDClient | None = None


def _get_comfyui_client() -> BizyTRDClient:
    global _client
    if _client is None:
        _client = create_client()
        register_comfyui_media_handlers(_client)
    return _client


class BizyTRDBaseNode(ABC):
    """Shared base class for registry-generated bizytrd nodes."""

    MODEL_KEY = ""
    MODEL_DEF: dict[str, Any] = {}
    PARAMS: list[dict[str, Any]] = []
    OUTPUT_TYPE = "string"
    FUNCTION = "execute"
    OUTPUT_NODE = True

    def build_payload(self, **kwargs: Any) -> dict[str, Any]:
        client = _get_comfyui_client()
        model_def = self.MODEL_DEF or {
            "model_key": self.MODEL_KEY,
            "params": self.PARAMS,
        }
        return build_payload_for_model(model_def, client.config, kwargs, client=client)

    def execute(self, **kwargs: Any):
        client = _get_comfyui_client()
        model_def = self.MODEL_DEF or {
            "model_key": self.MODEL_KEY,
            "params": self.PARAMS,
        }
        payload = build_payload_for_model(
            model_def, client.config, kwargs, client=client
        )
        request_id, _ = client.submit_task(self.MODEL_KEY, payload)
        poll_payload = client.poll_task(request_id)
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
