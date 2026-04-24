"""Base node scaffolding for bizytrd — async, aligned with bizyengine."""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
from abc import ABC
from fractions import Fraction
from typing import Any
import torch
import numpy as np

from bizytrd_sdk import AsyncBizyTRD

from .adapters import build_payload_for_model
from .config import get_config
from .result import download_outputs


class _AsyncAtomicCounter:
    """Async atomic counter, matching bizyengine.misc.utils.AsyncAtomicCounter."""

    def __init__(self, initial: int = 0):
        self._value = initial
        self._lock = asyncio.Lock()

    async def increment(self, num: int = 1) -> int:
        async with self._lock:
            self._value += num
            return self._value

    async def value(self) -> int:
        async with self._lock:
            return self._value


_trd_api_counter = _AsyncAtomicCounter(0)
_placeholder_img = None
_placeholder_video = None


def _load_placeholder_image():
    global _placeholder_img
    if _placeholder_img is not None:
        return _placeholder_img
    placeholder_path = os.path.join(os.path.dirname(__file__), "..", "placeholder.png")
    if not os.path.exists(placeholder_path):
        placeholder_path = os.path.join(
            os.path.dirname(__file__), "placeholder.png"
        )
    if os.path.exists(placeholder_path):
        with open(placeholder_path, "rb") as f:
            try:
                from bizyairsdk import bytesio_to_image_tensor
                _placeholder_img = bytesio_to_image_tensor(io.BytesIO(f.read()))
            except ImportError:
                _placeholder_img = None
    return _placeholder_img

def _make_placeholder_image(error_msg: str) -> torch.Tensor:
    """Generate a 512x512 red-tinted image with error text burned in.
    Returns a ComfyUI IMAGE tensor (1, H, W, 3) float32 in [0,1].
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = _render_placeholder_canvas(error_msg, Image, ImageDraw, ImageFont)
        arr = np.array(img).astype(np.float32) / 255.0
        return torch.from_numpy(arr).unsqueeze(0)
    except Exception:
        arr = np.zeros((512, 512, 3), dtype=np.float32)
        arr[:, :, 0] = 0.3
        return torch.from_numpy(arr).unsqueeze(0)


def _render_placeholder_canvas(error_msg: str, Image, ImageDraw, ImageFont):
    width, height = 512, 512
    img = Image.new("RGB", (width, height), (80, 10, 10))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 18)
        title_font = ImageFont.truetype("arial.ttf", 28)
    except Exception:
        font = ImageFont.load_default()
        title_font = font

    draw.rectangle((0, 0, width - 1, height - 1), outline=(210, 60, 60), width=6)
    draw.text((20, 18), "BizyTRD Error", fill=(255, 220, 220), font=title_font)

    margin = 20
    content_top = 70
    max_width = width - 2 * margin
    lines = []
    normalized_msg = str(error_msg).strip() or "Unknown BizyTRD error"
    for paragraph in normalized_msg.split("\n"):
        words = paragraph.split() or [""]
        cur = ""
        for word in words:
            test = f"{cur} {word}".strip()
            bbox = draw.textbbox((0, 0), test, font=font)
            if bbox[2] - bbox[0] > max_width and cur:
                lines.append(cur)
                cur = word
            else:
                cur = test
        if cur:
            lines.append(cur)

    y = content_top
    for line in lines:
        draw.text((margin, y), line, fill=(255, 200, 200), font=font)
        y += 22
        if y > height - 24:
            break

    return img


def _make_placeholder_video(error_msg: str):
    """Generate a short placeholder video that Save Video can round-trip."""
    try:
        from comfy_api.latest import InputImpl, Types

        # Prefer ComfyUI's native video type so Save Video can re-encode it
        # through the same H264/MP4 path used by built-in nodes.
        placeholder_frame = _make_placeholder_image(error_msg)
        placeholder_frames = placeholder_frame.repeat(24, 1, 1, 1)
        return InputImpl.VideoFromComponents(
            Types.VideoComponents(
                images=placeholder_frames,
                frame_rate=Fraction(12, 1),
            )
        )
    except Exception as exc:
        logging.warning(
            "Failed to build dynamic placeholder video from components: %s",
            exc,
        )
        fallback = _load_placeholder_video()
        if fallback is not None:
            return fallback
        return None

def _load_placeholder_video():
    global _placeholder_video
    if _placeholder_video is not None:
        return _placeholder_video
    placeholder_path = os.path.join(os.path.dirname(__file__), "..", "placeholder.mp4")
    if not os.path.exists(placeholder_path):
        placeholder_path = os.path.join(
            os.path.dirname(__file__), "placeholder.mp4"
        )
    if os.path.exists(placeholder_path):
        with open(placeholder_path, "rb") as f:
            try:
                from comfy_api.latest._input_impl import VideoFromFile
                _placeholder_video = VideoFromFile(io.BytesIO(f.read()))
            except ImportError:
                _placeholder_video = None
    return _placeholder_video


def _get_prompt_id() -> str | None:
    """Get the current prompt ID, matching bizyengine's pop_api_key_and_prompt_id logic."""
    try:
        from server import PromptServer
        if (
            PromptServer.instance is not None
            and PromptServer.instance.last_prompt_id is not None
        ):
            return PromptServer.instance.last_prompt_id
    except (ImportError, AttributeError):
        pass
    return None


class BizyTRDBaseNode(ABC):
    """Shared base class for registry-generated bizytrd nodes."""

    MODEL_NAME = ""
    ENDPOINT_CATEGORY = ""
    NORMALIZED_ENDPOINT_CATEGORY = ""
    MODEL_DEF: dict[str, Any] = {}
    PARAMS: list[dict[str, Any]] = []
    OUTPUT_TYPE = "string"
    FUNCTION = "execute"
    OUTPUT_NODE = True

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.original_urls: set[str] = set()

    def build_payload(self, config: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        model_def = self.MODEL_DEF or {
            "model_name": self.MODEL_NAME,
            "endpoint_category": self.ENDPOINT_CATEGORY,
            "params": self.PARAMS,
        }
        return build_payload_for_model(model_def, config, kwargs)

    def resolve_endpoint(self, **kwargs: Any) -> str:
        model_name = str(self.MODEL_NAME or "").strip()
        endpoint_category = str(
            self.NORMALIZED_ENDPOINT_CATEGORY or self.ENDPOINT_CATEGORY or ""
        ).strip("/")

        channel_value = kwargs.get("channel")
        if channel_value is not None:
            channel_key = str(channel_value).strip()
            if channel_key:
                normalized = channel_key.lower().replace("_", "-")
                normalized = "-".join(normalized.split())
                model_name = f"{model_name}-{normalized}"

        if model_name and endpoint_category:
            return f"{model_name}/{endpoint_category}"
        return model_name

    async def execute(self, **kwargs: Any):
        """Main execution entry, matching bizyengine's BizyAirTrdApiBaseNode.api_call()."""
        self.original_urls.clear()
        config = get_config()
        prompt_id = _get_prompt_id()
        payload = self.build_payload(config, **kwargs)
        endpoint = self.resolve_endpoint(**kwargs)
        print(f"payload preview: {self._payload_preview(payload)}")

        e = None
        outputs = ([], [], [], [], "")

        try:
            await _trd_api_counter.increment(1)
            outputs = await self._create_task_and_wait(
                endpoint, payload, config, prompt_id=prompt_id
            )
        except Exception as api_err:
            e = api_err
        finally:
            await _trd_api_counter.increment(-1)
            skip_error = kwargs.get("skip_error", False)
            if e is not None:
                # If other concurrent tasks are still running, return placeholders silently
                # if await _trd_api_counter.value() > 0:
                # 新版改为只要当前任务的参数里设置了 skip_error 为 true 就返回占位符，不管是否有其他并发任务了
                if skip_error:
                    logging.error(
                        f"BizyTRD task failed (silently because of other tasks executing in parallel), error: {str(e)}"
                    )
                    error_msg = str(e)
                    urls_str = ""
                    if len(self.original_urls) > 0:
                        urls_str = json.dumps(sorted(self.original_urls))
                        logging.error(
                            f"原始输出下载地址: {urls_str}，请手动下载。\n错误信息: {error_msg}"
                        )
                    placeholder_video = []
                    placeholder_image = []
                    if self.OUTPUT_TYPE == "video":
                        video = _make_placeholder_video(error_msg)
                        if video is not None:
                            placeholder_video = [video]
                    elif self.OUTPUT_TYPE == "image":
                        placeholder_image = [_make_placeholder_image(error_msg)]
                    outputs = [
                        placeholder_video,
                        placeholder_image,
                        [],
                        [error_msg],
                        urls_str,
                    ]
                else:
                    # No concurrent tasks, raise normally
                    # 如果 skip_error 没有设置为 true，直接抛出错误，不返回占位符了
                    if len(self.original_urls) > 0:
                        urls_str = json.dumps(sorted(self.original_urls))
                        raise RuntimeError(
                            f"原始输出下载地址: {urls_str}，请手动下载。\n错误信息: {str(e)}"
                        ) from e
                    else:
                        raise e
        return self.handle_outputs(outputs)

    async def _create_task_and_wait(
        self,
        endpoint: str,
        payload: dict[str, Any],
        config: dict[str, Any],
        *,
        prompt_id: str | None = None,
    ) -> tuple[list, list, list, list[str], str]:
        """Create a task and wait for completion, matching bizyengine's flow."""
        async with AsyncBizyTRD(
            api_key=config.get("api_key"),
            base_url=config.get("base_url"),
            upload_base_url=config.get("upload_base_url"),
            timeout=config.get("timeout"),
            polling_interval=config.get("polling_interval"),
            max_polling_time=config.get("max_polling_time"),
        ) as client:
            task = await client.create_task(
                endpoint,
                payload,
                prompt_id=prompt_id,
            )
            result = await client.wait_for_task(
                task.request_id,
                prompt_id=prompt_id,
                original_urls=self.original_urls,
            )

            # Download actual media content, matching bizyengine's download loop.
            videos, images, audios, texts, urls_str = await download_outputs(
                client,
                result.outputs,
            )
            return (videos, images, audios, texts, urls_str)

    def handle_outputs(
        self,
        outputs: tuple[list, list, list, list[str], str],
    ) -> dict[str, Any]:
        """Transform raw outputs into ComfyUI node return format.

        outputs = (videos, images, audios, texts, urls_str)
        """
        videos, images, audios, texts, urls_str = outputs

        if self.OUTPUT_TYPE == "video":
            primary = videos[0] if videos else ""
            return {
                "ui": {"text": [urls_str]},
                "result": (primary, urls_str),
            }
        elif self.OUTPUT_TYPE == "image":
            primary = images[0] if images else ""
            return {
                "ui": {"text": [urls_str]},
                "result": (primary, urls_str),
            }
        elif self.OUTPUT_TYPE == "audio":
            primary = audios[0] if audios else (texts[0] if texts else urls_str)
            return {
                "ui": {"text": [urls_str]},
                "result": (primary, urls_str),
            }
        else:
            # string / text
            primary = "\n".join(texts) if texts else ""
            return {
                "ui": {"text": [primary, urls_str]},
                "result": (primary, urls_str),
            }

    def upload_file(self, file_content: io.BytesIO, file_name: str, config: dict[str, Any]) -> str:
        """Upload a file, matching bizyengine's upload_file logic."""
        from .upload import upload_bytes
        return upload_bytes(file_content, file_name, config)

    @staticmethod
    def _payload_preview(payload: dict[str, Any]) -> str:
        safe: dict[str, Any] = {}
        for key, value in payload.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                safe[key] = value
            elif isinstance(value, list):
                safe[key] = f"<list:{len(value)}>"
            else:
                safe[key] = f"<{type(value).__name__}>"
        return json.dumps(safe, ensure_ascii=False)
