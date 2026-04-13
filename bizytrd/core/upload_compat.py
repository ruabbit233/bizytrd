"""ComfyUI-specific media conversion and handler registration for bizytrd."""

from __future__ import annotations

import io
import uuid
from typing import Any

from bizytrd_sdk import BizyTRDClient


def image_to_bytesio(
    image: Any,
    *,
    total_pixels: int = 10000 * 10000,
    mime_type: str = "image/webp",
    max_size: int = 20 * 1024 * 1024,
) -> io.BytesIO:
    try:
        from comfy_api_nodes.util.conversions import tensor_to_bytesio
    except ImportError as exc:
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
        raise TypeError(
            "Video upload expects a ComfyUI VIDEO input or a pre-uploaded URL."
        )

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
    except ImportError as exc:
        raise RuntimeError(
            "Audio upload requires av and torchaudio to be installed in ComfyUI."
        ) from exc

    if (
        not isinstance(audio, dict)
        or "waveform" not in audio
        or "sample_rate" not in audio
    ):
        raise TypeError(
            "Audio upload expects a ComfyUI AUDIO input or a pre-uploaded URL."
        )

    waveform = audio["waveform"]
    sample_rate = int(audio["sample_rate"])

    if hasattr(waveform, "cpu"):
        waveform = waveform.cpu()

    if getattr(waveform, "dim", lambda: 0)() == 3:
        waveform = waveform[0]
    if getattr(waveform, "dim", lambda: 0)() != 2:
        raise TypeError(
            "Audio waveform must have shape [channels, samples] or [batch, channels, samples]."
        )

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
            waveform = torchaudio.functional.resample(
                waveform, sample_rate, output_rate
            )

    output = io.BytesIO()

    class _NoCloseBytesIO(io.BytesIO):
        def close(self):
            self.flush()

    safe_output = _NoCloseBytesIO()
    container = av.open(safe_output, mode="w", format=format)

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

    num_channels = int(waveform.shape[0])
    layout = "mono" if num_channels == 1 else "stereo"
    if num_channels > 2:
        raise ValueError(
            f"Audio upload only supports mono or stereo input, got {num_channels} channels"
        )

    frame = av.AudioFrame.from_ndarray(
        waveform.movedim(0, 1).reshape(1, -1).float().numpy(),
        format="flt",
        layout=layout,
    )
    frame.sample_rate = output_rate
    frame.pts = 0
    container.mux(stream.encode(frame))
    container.mux(stream.encode(None))
    container.close()

    safe_output.seek(0)
    if safe_output.getbuffer().nbytes > max_size:
        raise ValueError(
            f"Audio size is too large, must be less than {max_size / 1024 / 1024:.1f}MB"
        )
    return safe_output, format


def _handle_image(
    value: Any,
    *,
    input_name: str,
    file_name_prefix: str,
    client: BizyTRDClient,
    **kwargs: Any,
) -> str:
    file_name = f"{file_name_prefix}_{uuid.uuid4().hex}.webp"
    image_bytes = image_to_bytesio(
        value,
        total_pixels=int(kwargs.get("total_pixels", 10000 * 10000)),
        mime_type="image/webp",
        max_size=int(kwargs.get("max_size", 20 * 1024 * 1024)),
    )
    return client.upload_bytes(image_bytes, file_name)


def _handle_video(
    value: Any,
    *,
    input_name: str,
    file_name_prefix: str,
    client: BizyTRDClient,
    **kwargs: Any,
) -> str:
    enforce_duration_range = kwargs.get("enforce_duration_range")
    if isinstance(enforce_duration_range, list):
        enforce_duration_range = tuple(enforce_duration_range)
    video_bytes, extension = video_to_bytesio(
        value,
        max_size=int(kwargs.get("max_size", 100 * 1024 * 1024)),
        enforce_duration_range=enforce_duration_range,
    )
    return client.upload_bytes(
        video_bytes, f"{file_name_prefix}_{uuid.uuid4().hex}.{extension}"
    )


def _handle_audio(
    value: Any,
    *,
    input_name: str,
    file_name_prefix: str,
    client: BizyTRDClient,
    **kwargs: Any,
) -> str:
    audio_format = str(kwargs.get("format", "mp3"))
    audio_bytes, extension = audio_to_bytesio(
        value,
        format=audio_format,
        max_size=int(kwargs.get("max_size", 50 * 1024 * 1024)),
    )
    return client.upload_bytes(
        audio_bytes, f"{file_name_prefix}_{uuid.uuid4().hex}.{extension}"
    )


def register_comfyui_media_handlers(client: BizyTRDClient) -> None:
    client.register_media_handler("IMAGE", _handle_image)
    client.register_media_handler("VIDEO", _handle_video)
    client.register_media_handler("AUDIO", _handle_audio)
