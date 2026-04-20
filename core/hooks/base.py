"""Shared hook protocol definitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class HookContext:
    """Named context passed to value hooks."""

    param: dict[str, Any]
    inputs: dict[str, Any]
    media: dict[str, dict[str, Any]]
    resolved_model: Any = None

    def get(self, name: str, default: Any = None) -> Any:
        return self.inputs.get(name, default)

    def get_media(
        self,
        name: str,
        default: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        return self.media.get(name, default)


HookFunc = Callable[[Any, HookContext], Any]
