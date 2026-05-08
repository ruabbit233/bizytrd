"""Result processing for bizytrd — download outputs, matching bizyengine."""

from __future__ import annotations

import io
import json
from typing import Any

from bizytrd_sdk import AsyncBizyTRD


def _audio_bytes_to_comfy(audio_bytes: bytes) -> dict[str, Any]:
    """Convert raw audio bytes to ComfyUI AUDIO dict {"waveform": Tensor, "sample_rate": int}.

    Uses PyAV for decoding.  Fallback when comfy_api_nodes.util.conversions
    is not available.
    """
    import torch

    try:
        import av
    except ImportError as exc:
        raise RuntimeError(
            "Audio output requires the 'av' package for decoding. "
            "Install it with: pip install av"
        ) from exc

    from_bytesio = io.BytesIO(audio_bytes)
    with av.open(from_bytesio) as container:
        if not container.streams.audio:
            raise ValueError("No audio stream found in downloaded audio.")
        stream = container.streams.audio[0]
        sample_rate = int(stream.codec_context.sample_rate)
        n_channels = stream.channels or 1

        frames: list = []
        for frame in container.decode(streams=stream.index):
            arr = frame.to_ndarray()
            buf = torch.from_numpy(arr)
            if buf.ndim == 1:
                buf = buf.unsqueeze(0)
            elif buf.shape[0] != n_channels and buf.shape[-1] == n_channels:
                buf = buf.transpose(0, 1).contiguous()
            elif buf.shape[0] != n_channels:
                buf = buf.reshape(-1, n_channels).t().contiguous()
            frames.append(buf)

    if not frames:
        raise ValueError("Decoded zero audio frames.")

    wav = torch.cat(frames, dim=1)  # [C, T]
    if wav.dtype == torch.int16:
        wav = wav.float() / (2**15)
    elif wav.dtype == torch.int32:
        wav = wav.float() / (2**31)
    elif not wav.dtype.is_floating_point:
        wav = wav.float()

    return {"waveform": wav.unsqueeze(0).contiguous(), "sample_rate": sample_rate}


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

    for audio_content in downloaded.audios:
        try:
            from comfy_api_nodes.util.conversions import audio_bytes_to_audio_input

            audios.append(audio_bytes_to_audio_input(audio_content))
        except ImportError:
            audios.append(_audio_bytes_to_comfy(audio_content))
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
