"""Explicit registrations for hand-written bizytrd nodes."""

from __future__ import annotations

from .config import DoubaoToolConfig, LLMToolConfig, MultiPromptConfig


NODE_CLASS_MAPPINGS = {
    "BizyTRD_DoubaoToolConfig": DoubaoToolConfig,
    "BizyTRD_MultiPromptConfig": MultiPromptConfig,
    "BizyTRD_LLMToolConfig": LLMToolConfig,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "BizyTRD_DoubaoToolConfig": "Doubao Tool Config",
    "BizyTRD_MultiPromptConfig": "Kling O3 MultiPrompt Config",
    "BizyTRD_LLMToolConfig": "LLM Tool Config",
}


def get_manual_node_mappings() -> tuple[dict[str, type], dict[str, str]]:
    return dict(NODE_CLASS_MAPPINGS), dict(NODE_DISPLAY_NAME_MAPPINGS)

