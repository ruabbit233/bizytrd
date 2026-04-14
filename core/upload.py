"""Upload and media normalization helpers for bizytrd."""

from __future__ import annotations

import io
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ..bizytrd_sdk import BizyTRD


def _is_remote_reference(text: str) -> bool:
    return text.startswith(("http://", "https://", "data:"))


def _normalize_local_path(text: str) -> Path | None:
    if text.startswith("file://"):
        return Path(urlparse(text).path)

    candidate = Path(text).expanduser()
    if candidate.exists():
        return candidate
    return None


def request_upload_token(
    file_name: str,
    config: dict[str, Any],
    *,
    file_type: str = "inputs",
) -> dict[str, Any]:
    client = BizyTRD(
        api_key=config.get("api_key"),
        base_url=config.get("base_url"),
        upload_base_url=config.get("upload_base_url"),
        timeout=config.get("timeout"),
        polling_interval=config.get("polling_interval"),
        max_polling_time=config.get("max_polling_time"),
    )
    return client.request_upload_token(file_name, file_type=file_type)


def upload_bytes(
    file_content: io.BytesIO,
    file_name: str,
    config: dict[str, Any],
    *,
    file_type: str = "inputs",
) -> str:
    client = BizyTRD(
        api_key=config.get("api_key"),
        base_url=config.get("base_url"),
        upload_base_url=config.get("upload_base_url"),
        timeout=config.get("timeout"),
        polling_interval=config.get("polling_interval"),
        max_polling_time=config.get("max_polling_time"),
    )
    return client.upload_bytes(file_content, file_name, file_type=file_type)


def image_to_bytesio(
    image: Any,
    *,
    total_pixels: int = 10000 * 10000,
    mime_type: str = "image/webp",
    max_size: int = 20 * 1024 * 1024,
) -> io.BytesIO:
    try:
        from comfy_api_nodes.util.conversions import tensor_to_bytesio
    except Exception as exc:
        raise RuntimeError(
            "Image upload requires ComfyUI's comfy_api_nodes conversion helpers."
        ) from exc

    image_bytes = tensor_to_bytesio(
        image=image,
        total_pixels=total_pixels,
        mime_type=mime_type,
    )
    image_bytes.seek(0)
    if image_bytes.getbuffer().nbytes > max_size:
        raise ValueError(
            f"Image size is too large, must be less than {max_size / 1024 / 1024:.1f}MB"
        )
    return image_bytes


def video_to_bytesio(
    video: Any,
    *,
    max_size: int = 100 * 1024 * 1024,
    enforce_duration_range: tuple[float, float] | None = None,
) -> tuple[io.BytesIO, str]:
    if not hasattr(video, "save_to"):
        raise TypeError("Video upload expects a ComfyUI VIDEO input or a pre-uploaded URL.")

    if enforce_duration_range is not None and hasattr(video, "get_duration"):
        duration = float(video.get_duration())
        minimum, maximum = enforce_duration_range
        if duration < minimum or duration > maximum:
            raise ValueError(
                f"Input video duration must be between {minimum:g} and {maximum:g} seconds"
            )

    video_bytes = io.BytesIO()
    video.save_to(video_bytes, format="mp4", codec="h264")
    video_bytes.seek(0)

    if video_bytes.getbuffer().nbytes > max_size:
        raise ValueError(
            f"Input video size is too large, must be less than {max_size / 1024 / 1024:.1f}MB"
        )

    return video_bytes, "mp4"


def audio_to_bytesio(
    audio: Any,
    *,
    format: str = "mp3",
    quality: str = "128k",
    max_size: int = 50 * 1024 * 1024,
) -> tuple[io.BytesIO, str]:
    try:
        import av
        import torchaudio
    except Exception as exc:
        raise RuntimeError(
            "Audio upload requires av and torchaudio to be installed in ComfyUI."
        ) from exc

    if not isinstance(audio, dict) or "waveform" not in audio or "sample_rate" not in audio:
        raise TypeError("Audio upload expects a ComfyUI AUDIO input or a pre-uploaded URL.")

    waveform = audio["waveform"]
    sample_rate = int(audio["sample_rate"])

    if hasattr(waveform, "cpu"):
        waveform = waveform.cpu()

    if getattr(waveform, "dim", lambda: 0)() == 3:
        waveform = waveform[0]
    if getattr(waveform, "dim", lambda: 0)() != 2:
        raise TypeError("Audio waveform must have shape [channels, samples] or [batch, channels, samples].")

    opus_rates = [8000, 12000, 16000, 24000, 48000]
    output_rate = sample_rate
    if format == "opus":
        if output_rate > 48000:
            output_rate = 48000
        elif output_rate not in opus_rates:
            for candidate in opus_rates:
                if candidate > output_rate:
                    output_rate = candidate
                    break
            if output_rate not in opus_rates:
                output_rate = 48000
        if output_rate != sample_rate:
            waveform = torchaudio.functional.resample(waveform, sample_rate, output_rate)

    output = io.BytesIO()
    container = av.open(output, mode="w", format=format)

    if format == "opus":
        stream = container.add_stream("libopus", rate=output_rate)
        quality_map = {
            "64k": 64000,
            "96k": 96000,
            "128k": 128000,
            "192k": 192000,
            "320k": 320000,
        }
        stream.bit_rate = quality_map.get(quality, 128000)
    elif format == "mp3":
        stream = container.add_stream("libmp3lame", rate=output_rate)
        if quality == "V0":
            stream.codec_context.qscale = 1
        elif quality == "320k":
            stream.bit_rate = 320000
        else:
            stream.bit_rate = 128000
    else:
        stream = container.add_stream("flac", rate=output_rate)

    frame = av.AudioFrame.from_ndarray(
        waveform.movedim(0, 1).reshape(1, -1).float().numpy(),
        format="flt",
        layout="mono" if waveform.shape[0] == 1 else "stereo",
    )
    frame.sample_rate = output_rate
    frame.pts = 0
    container.mux(stream.encode(frame))
    container.mux(stream.encode(None))
    container.close()

    output.seek(0)
    if output.getbuffer().nbytes > max_size:
        raise ValueError(
            f"Audio size is too large, must be less than {max_size / 1024 / 1024:.1f}MB"
        )
    return output, format


def upload_local_file(
    path: Path,
    config: dict[str, Any],
    *,
    file_name: str | None = None,
) -> str:
    with path.open("rb") as handle:
        file_bytes = io.BytesIO(handle.read())
    return upload_bytes(file_bytes, file_name or path.name, config)


def upload_image_input(
    value: Any,
    config: dict[str, Any],
    *,
    file_name_prefix: str,
    total_pixels: int = 10000 * 10000,
    max_size: int = 20 * 1024 * 1024,
) -> str:
    if isinstance(value, str):
        text = value.strip()
        if _is_remote_reference(text):
            return text
        local_path = _normalize_local_path(text)
        if local_path is not None:
            return upload_local_file(
                local_path,
                config,
                file_name=f"{file_name_prefix}{local_path.suffix or '.webp'}",
            )

    file_name = f"{file_name_prefix}_{uuid.uuid4().hex}.webp"
    image_bytes = image_to_bytesio(
        value,
        total_pixels=total_pixels,
        mime_type="image/webp",
        max_size=max_size,
    )
    return upload_bytes(image_bytes, file_name, config)


def upload_video_input(
    value: Any,
    config: dict[str, Any],
    *,
    file_name_prefix: str,
    max_size: int = 100 * 1024 * 1024,
    enforce_duration_range: tuple[float, float] | None = None,
) -> str:
    if isinstance(value, str):
        text = value.strip()
        if _is_remote_reference(text):
            return text
        local_path = _normalize_local_path(text)
        if local_path is not None:
            return upload_local_file(
                local_path,
                config,
                file_name=f"{file_name_prefix}{local_path.suffix or '.mp4'}",
            )

    video_bytes, extension = video_to_bytesio(
        value,
        max_size=max_size,
        enforce_duration_range=enforce_duration_range,
    )
    return upload_bytes(
        video_bytes,
        f"{file_name_prefix}_{uuid.uuid4().hex}.{extension}",
        config,
    )


def upload_audio_input(
    value: Any,
    config: dict[str, Any],
    *,
    file_name_prefix: str,
    format: str = "mp3",
    max_size: int = 50 * 1024 * 1024,
) -> str:
    if isinstance(value, str):
        text = value.strip()
        if _is_remote_reference(text):
            return text
        local_path = _normalize_local_path(text)
        if local_path is not None:
            return upload_local_file(
                local_path,
                config,
                file_name=f"{file_name_prefix}{local_path.suffix or '.mp3'}",
            )

    audio_bytes, extension = audio_to_bytesio(value, format=format, max_size=max_size)
    return upload_bytes(
        audio_bytes,
        f"{file_name_prefix}_{uuid.uuid4().hex}.{extension}",
        config,
    )


def normalize_media_input(
    value: Any,
    media_type: str,
    input_name: str,
    config: dict[str, Any],
) -> str:
    if value is None:
        return ""

    if isinstance(value, str):
        text = value.strip()
        if _is_remote_reference(text):
            return text
        local_path = _normalize_local_path(text)
        if local_path is not None:
            return upload_local_file(local_path, config, file_name=local_path.name)

    if media_type == "IMAGE":
        return upload_image_input(value, config, file_name_prefix=input_name)
    if media_type == "VIDEO":
        return upload_video_input(value, config, file_name_prefix=input_name)
    if media_type == "AUDIO":
        return upload_audio_input(value, config, file_name_prefix=input_name)

    raise TypeError(f"Unsupported media type '{media_type}' for input '{input_name}'")
