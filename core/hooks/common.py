"""General-purpose hooks."""

from __future__ import annotations

import json
from typing import Any

from .base import HookContext


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) == 0
    return False


def json_loads(
    value: Any,
    context: HookContext,
) -> Any:
    if _is_blank(value):
        return None
    if isinstance(value, (list, dict)):
        return value
    return json.loads(str(value))


def video_duration(
    value: Any,
    context: HookContext,
) -> Any:
    if value is not None:
        return value

    video_context = context.get_media("video", {}) or {}
    values = video_context.get("values") or []
    video = values[0] if values else context.get("video")
    if video is None:
        return None

    get_duration = getattr(video, "get_duration", None)
    if not callable(get_duration):
        raise ValueError("Video input does not expose get_duration().")

    duration = get_duration()
    if duration is None:
        raise ValueError("Cannot get video duration, please check your video input.")
    return duration
