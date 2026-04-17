"""General-purpose hooks."""

from __future__ import annotations

import json
from typing import Any


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) == 0
    return False


def json_loads(
    param: dict[str, Any],
    value: Any,
    kwargs: dict[str, Any],
    media_context: dict[str, dict[str, Any]],
) -> Any:
    if _is_blank(value):
        return None
    return json.loads(str(value))
