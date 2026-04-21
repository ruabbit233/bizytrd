"""Hand-written local config helper nodes migrated from bizyengine."""

from __future__ import annotations

import json
from typing import Any


class DoubaoToolConfig:
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("tools",)
    FUNCTION = "execute"
    CATEGORY = "BizyTRD/Doubao"
    OUTPUT_NODE = False

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "web_search": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "description": "开启后，模型将根据输入情况按需进行联网搜索",
                    },
                )
            }
        }

    def execute(self, **kwargs: Any):
        web_search = kwargs.pop("web_search", True)
        tools = []
        if web_search:
            tools.append("web_search")
        return (tools,)


class MultiPromptConfig:
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("multi_prompt",)
    FUNCTION = "execute"
    CATEGORY = "BizyTRD/Kling"
    OUTPUT_NODE = False

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {"multiline": True, "default": ""}),
                "duration": ("INT", {"default": 5, "min": 1, "max": 15}),
            },
            "optional": {
                "prev_multi_prompt": ("STRING", {"forceInput": True}),
            },
        }

    def execute(self, **kwargs: Any):
        prompt = kwargs.get("prompt", "")
        duration = kwargs.get("duration", 5)
        prev_multi_prompt = kwargs.get("prev_multi_prompt", "[]")

        try:
            data_list = json.loads(prev_multi_prompt) if prev_multi_prompt else []
        except Exception:
            data_list = []

        data_list.append({"prompt": prompt, "duration": duration})
        return (json.dumps(data_list, ensure_ascii=False),)


class LLMToolConfig:
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("tools",)
    FUNCTION = "execute"
    CATEGORY = "BizyTRD/LLM"
    OUTPUT_NODE = False

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "enable_thinking": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "是否开启思考模式",
                    },
                ),
                "web_search": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "description": "开启后，模型将根据输入情况按需进行联网搜索",
                    },
                ),
            }
        }

    def execute(self, **kwargs: Any):
        web_search = kwargs.pop("web_search", True)
        enable_thinking = kwargs.pop("enable_thinking", False)
        tools = []
        if web_search:
            tools.append("web_search")
        if enable_thinking:
            tools.append("enable_thinking")
        return (json.dumps(tools),)
