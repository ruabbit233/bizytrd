"""Result normalization for bizytrd."""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from io import BytesIO
from typing import Any


def _download_bytes(url: str, timeout: int = 180) -> bytes:
    import requests

    response = requests.get(url, stream=True, timeout=timeout)
    response.raise_for_status()
    return response.content


def _output_dir() -> str:
    try:
        import folder_paths

        return folder_paths.get_output_directory()
    except Exception:
        return tempfile.gettempdir()


def _download_video(url: str) -> Any:
    suffix = os.path.splitext(url.split("?", 1)[0])[1] or ".mp4"
    path = os.path.join(_output_dir(), f"bizytrd_{uuid.uuid4().hex}{suffix}")
    with open(path, "wb") as handle:
        handle.write(_download_bytes(url))

    try:
        from comfy_api.input_impl import VideoFromFile

        return VideoFromFile(path)
    except Exception:
        import logging

        logging.getLogger(__name__).warning(
            "VideoFromFile not available; returning path string for VIDEO output"
        )
        return path


def _download_image_tensor(urls: list[str]) -> Any:
    try:
        import numpy as np
        import torch
        from PIL import Image
    except Exception as exc:
        raise RuntimeError(
            "Image result support requires numpy, torch, and PIL"
        ) from exc

    tensors = []
    for url in urls:
        image = Image.open(BytesIO(_download_bytes(url, timeout=120))).convert("RGB")
        arr = np.array(image).astype("float32") / 255.0
        tensors.append(torch.from_numpy(arr))
    return torch.stack(tensors)


def _download_audio(url: str) -> Any:
    try:
        import torch
        import torchaudio
    except Exception as exc:
        raise RuntimeError(
            "Audio result support requires torch and torchaudio"
        ) from exc

    path = os.path.join(_output_dir(), f"bizytrd_{uuid.uuid4().hex}.wav")
    try:
        with open(path, "wb") as handle:
            handle.write(_download_bytes(url, timeout=120))

        waveform, sample_rate = torchaudio.load(path)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass

    if waveform.dim() == 2:
        waveform = waveform.unsqueeze(0)
    return {"waveform": waveform, "sample_rate": sample_rate}


def normalize_result(
    output_type: str, poll_payload: dict[str, Any]
) -> tuple[Any, str, str]:
    data = poll_payload.get("data") or {}
    outputs = data.get("outputs") or {}
    texts = list(outputs.get("texts") or [])
    images = list(outputs.get("images") or [])
    videos = list(outputs.get("videos") or [])
    audios = list(outputs.get("audios") or [])
    urls = images + videos + audios

    if output_type == "video":
        if not videos:
            raise RuntimeError(f"No video outputs found: {poll_payload}")
        primary = _download_video(videos[0])
    elif output_type == "image":
        if not images:
            raise RuntimeError(f"No image outputs found: {poll_payload}")
        primary = _download_image_tensor(images)
    elif output_type == "audio":
        if not audios:
            raise RuntimeError(f"No audio outputs found: {poll_payload}")
        primary = _download_audio(audios[0])
    else:
        primary = texts[0] if texts else ""

    return (
        primary,
        "\n".join(urls),
        json.dumps(poll_payload, ensure_ascii=False, indent=2),
    )
