"""Shared hook protocol definitions."""

from __future__ import annotations

from typing import Any, Callable

HookFunc = Callable[
    [dict[str, Any], Any, dict[str, Any], dict[str, dict[str, Any]]],
    Any,
]
