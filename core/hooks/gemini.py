from __future__ import annotations

from typing import Any

from .base import HookContext


def _has_reference_media(context: HookContext) -> bool:
    for name in ("images", "image"):
        media = context.get_media(name, {}) or {}
        if int(media.get("count") or 0) > 0:
            return True
    return False


def operation_prompt(
    value: Any,
    context: HookContext,
) -> str:
    prompt = str(value or "")
    operation = str(context.get("operation", "generate") or "generate")
    aspect_ratio = str(context.get("aspect_ratio", "auto") or "auto")
    character_consistency = bool(context.get("character_consistency", True))
    quality = str(context.get("quality", "standard") or "standard")
    has_references = _has_reference_media(context)

    auto_aspect = (
        "keep the original image aspect ratio"
        if has_references
        else "use an appropriate aspect ratio"
    )
    aspect_instructions = {
        "1:1": "square format",
        "16:9": "widescreen landscape format",
        "9:16": "portrait format",
        "4:3": "standard landscape format",
        "3:4": "standard portrait format",
        "auto": auto_aspect,
    }
    format_instruction = f"in {aspect_instructions.get(aspect_ratio, auto_aspect)}"
    base_quality = "Generate a high-quality, photorealistic image"

    if operation == "generate":
        if has_references:
            final_prompt = (
                f"{base_quality} inspired by the style and elements of the reference images. "
                f"{prompt}. {format_instruction}."
            )
        else:
            final_prompt = f"{base_quality} of: {prompt}. {format_instruction}."
    elif operation == "edit":
        if not has_references:
            return "Error: Edit operation requires reference images"
        final_prompt = (
            f"Edit the provided reference image(s). {prompt}. "
            "Maintain the original composition and quality while making the requested changes."
        )
    elif operation == "style_transfer":
        if not has_references:
            return "Error: Style transfer requires reference images"
        final_prompt = (
            f"Apply the style from the reference images to create: {prompt}. "
            f"Blend the stylistic elements naturally. {format_instruction}."
        )
    elif operation == "object_insertion":
        if not has_references:
            return "Error: Object insertion requires reference images"
        final_prompt = (
            f"Insert or blend the following into the reference image(s): {prompt}. "
            f"Ensure natural lighting, shadows, and perspective. {format_instruction}."
        )
    else:
        raise ValueError(f"Invalid Gemini operation: {operation}")

    if character_consistency and has_references:
        final_prompt += (
            " Maintain character consistency and visual identity from the reference images."
        )
    if quality == "high":
        final_prompt += " Use the highest quality settings available."
    return final_prompt
