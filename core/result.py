"""Result processing for bizytrd — download outputs, matching bizyengine."""

from __future__ import annotations

import io
import json
import logging
from typing import Any


async def download_outputs(
    outputs: dict[str, Any],
) -> tuple[list, list, list[str], str]:
    """Download videos, images, and texts from task outputs.

    Matches bizyengine's create_task_and_wait_for_completion output download loop:
    - Videos: download and wrap in VideoFromFile
    - Images: download and convert to tensor via bytesio_to_image_tensor
    - Texts: extract as-is
    - URLs: collected as a JSON string array
    """
    import aiohttp

    videos: list[Any] = []
    images: list[Any] = []
    texts: list[str] = []
    urls: list[str] = []

    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=3600)
    ) as session:
        if "videos" in outputs:
            for video_url in outputs["videos"]:
                async with session.get(video_url) as video_resp:
                    video_resp.raise_for_status()
                    video_content = await video_resp.read()
                    try:
                        from comfy_api.latest._input_impl import VideoFromFile
                        videos.append(VideoFromFile(io.BytesIO(video_content)))
                    except ImportError:
                        videos.append(io.BytesIO(video_content))
                    urls.append(video_url)

        if "images" in outputs:
            for image_url in outputs["images"]:
                async with session.get(image_url) as image_resp:
                    image_resp.raise_for_status()
                    image_content = await image_resp.read()
                    try:
                        from bizyairsdk import bytesio_to_image_tensor
                        images.append(bytesio_to_image_tensor(io.BytesIO(image_content)))
                    except ImportError:
                        images.append(io.BytesIO(image_content))
                    urls.append(image_url)

    if "texts" in outputs:
        for text in outputs["texts"]:
            texts.append(text)

    urls_str = json.dumps(urls)
    return videos, images, texts, urls_str


def normalize_result(
    output_type: str,
    poll_payload: dict[str, Any],
) -> tuple[Any, str, str]:
    """Normalize poll result into (primary_output, urls_str, response_str).

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
        urls_str = json.dumps(urls)
        texts = outputs.get("texts", [])
        response_str = json.dumps(poll_payload, ensure_ascii=False)
        primary = urls[0] if urls else ""
        return primary, urls_str, response_str

    # string / text output
    texts = outputs.get("texts", [])
    urls = []
    if "videos" in outputs:
        urls.extend(outputs["videos"])
    if "images" in outputs:
        urls.extend(outputs["images"])
    urls_str = json.dumps(urls)
    primary = "\n".join(texts) if texts else ""
    response_str = json.dumps(poll_payload, ensure_ascii=False)
    return primary, urls_str, response_str
