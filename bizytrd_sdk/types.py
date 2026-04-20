"""Dataclasses used by the async BizyTRD SDK."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .client import AsyncBizyTRD


@dataclass(slots=True)
class DownloadedOutputs:
    videos: list[bytes] = field(default_factory=list)
    images: list[bytes] = field(default_factory=list)
    audios: list[bytes] = field(default_factory=list)
    texts: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TaskResult:
    request_id: str
    status: str
    outputs: dict[str, Any]
    raw_payload: dict[str, Any]
    original_urls: list[str] = field(default_factory=list)

    @property
    def output_urls(self) -> list[str]:
        urls: list[str] = []
        videos = self.outputs.get("videos") or []
        images = self.outputs.get("images") or []
        audios = self.outputs.get("audios") or []
        urls.extend(str(item) for item in videos)
        urls.extend(str(item) for item in images)
        urls.extend(str(item) for item in audios)
        return urls

    @property
    def output_texts(self) -> list[str]:
        return [str(item) for item in (self.outputs.get("texts") or [])]


@dataclass(slots=True)
class TaskHandle:
    client: "AsyncBizyTRD"
    request_id: str
    model: str
    raw_payload: dict[str, Any]

    async def retrieve(self, *, prompt_id: str | None = None) -> dict[str, Any]:
        return await self.client.retrieve_task(self.request_id, prompt_id=prompt_id)

    async def wait(
        self,
        *,
        prompt_id: str | None = None,
        polling_interval: float | None = None,
        max_polling_time: int | None = None,
    ) -> TaskResult:
        return await self.client.wait_for_task(
            self.request_id,
            prompt_id=prompt_id,
            polling_interval=polling_interval,
            max_polling_time=max_polling_time,
        )

    async def download_outputs(self) -> DownloadedOutputs:
        result = await self.wait()
        return await self.client.download_outputs(result.outputs)
