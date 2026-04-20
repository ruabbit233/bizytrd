"""Result processing for bizytrd — download outputs, matching bizyengine."""

from __future__ import annotations

import io
import json
from typing import Any

from bizytrd_sdk import AsyncBizyTRD


async def download_outputs(
    client: AsyncBizyTRD,
    outputs: dict[str, Any],
) -> tuple[list, list, list, list[str], str]:
    """Download videos, images, audios, and texts from task outputs.

    Matches bizyengine's create_task_and_wait_for_completion output download loop:
    - Videos: download and wrap in VideoFromFile
    - Images: download and convert to tensor via bytesio_to_image_tensor
    - Texts: extract as-is
    - URLs: collected as a JSON string array
    """
    videos: list[Any] = []
    images: list[Any] = []
    audios: list[Any] = []
    texts: list[str] = []
    downloaded = await client.download_outputs(outputs)

    for video_content in downloaded.videos:
        try:
            from comfy_api.latest._input_impl import VideoFromFile

            videos.append(VideoFromFile(io.BytesIO(video_content)))
        except ImportError:
            videos.append(io.BytesIO(video_content))

    for image_content in downloaded.images:
        try:
            from bizyairsdk import bytesio_to_image_tensor

            images.append(bytesio_to_image_tensor(io.BytesIO(image_content)))
        except ImportError:
            images.append(io.BytesIO(image_content))

    audios.extend(io.BytesIO(audio_content) for audio_content in downloaded.audios)
    texts.extend(downloaded.texts)

    urls_str = json.dumps(downloaded.urls)
    return videos, images, audios, texts, urls_str


def normalize_result(
    output_type: str,
    poll_payload: dict[str, Any],
) -> tuple[Any, str]:
    """Normalize poll result into (primary_output, urls_str).

    This wraps the async download_outputs for use in the base node's execute method.
    For output types that don't need downloading (e.g. string), falls back to
    extracting directly from the response.
    """
    data = poll_payload.get("data") or {}
    outputs = data.get("outputs") or {}

    if output_type in ("image", "video", "audio"):
        # These require async download — handled in base.py directly.
        # This path is a fallback for non-async contexts.
        urls = []
        if "videos" in outputs:
            urls.extend(outputs["videos"])
        if "images" in outputs:
            urls.extend(outputs["images"])
        if "audios" in outputs:
            urls.extend(outputs["audios"])
        urls_str = json.dumps(urls)
        primary = urls[0] if urls else ""
        return primary, urls_str

    # string / text output
    texts = outputs.get("texts", [])
    urls = []
    if "videos" in outputs:
        urls.extend(outputs["videos"])
    if "images" in outputs:
        urls.extend(outputs["images"])
    if "audios" in outputs:
        urls.extend(outputs["audios"])
    urls_str = json.dumps(urls)
    primary = "\n".join(texts) if texts else ""
    return primary, urls_str
