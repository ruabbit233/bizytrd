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
