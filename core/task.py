"""Task submission and polling for bizytrd — async, aligned with bizyengine."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from ..bizytrd_sdk import AsyncBizyTRD, BizyTRD

from .config import CLIENT_VERSION, get_config

SUCCESS_CODE = 20000
ACCEPTED_CODE = 20002
RUNNING_STATUSES = {"running", "queuing"}
SAVING_STATUS = "saving"
SUCCESS_STATUSES = {"success"}
FAILED_STATUSES = {"failed"}


def _build_headers(config: dict[str, Any], *, prompt_id: str | None = None) -> dict[str, str]:
    """Build request headers matching bizyengine's client.headers() + extras."""
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "User-Agent": "BizyAir Client",
        "x-bizyair-client-version": CLIENT_VERSION,
    }
    api_key = config.get("api_key")
    if api_key:
        headers["authorization"] = f"Bearer {api_key}"
    if prompt_id:
        headers["X-BIZYAIR-PROMPT-ID"] = prompt_id
    return headers


def process_response_data(response_data: dict) -> dict:
    """Unwrap cloud response format, matching bizyengine's process_response_data."""
    if "result" in response_data:
        try:
            msg = json.loads(response_data["result"])
            if "request_id" in response_data and "request_id" not in msg:
                msg["request_id"] = response_data["request_id"]
        except json.JSONDecodeError:
            raise ValueError(f"Failed to decode JSON from response. {response_data=}")
    else:
        msg = response_data
    return msg


async def async_send_request(
    method: str = "POST",
    url: str | None = None,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    callback: callable = process_response_data,
) -> dict:
    """Async compatibility wrapper that now delegates transport to the SDK."""
    config = get_config()
    async with AsyncBizyTRD(
        api_key=config.get("api_key"),
        base_url=config.get("base_url"),
        upload_base_url=config.get("upload_base_url"),
        timeout=600,
        polling_interval=config.get("polling_interval"),
        max_polling_time=config.get("max_polling_time"),
    ) as client:
        return await client._request(
            method=method,
            url=str(url),
            data=data,
            headers=headers or _build_headers(config),
            callback=callback,
        )


def _extract_request_id(data: dict[str, Any]) -> str:
    request_id = (
        (data.get("data") or {}).get("request_id")
        or (data.get("data") or {}).get("requestId")
        or data.get("request_id")
        or data.get("requestId")
    )
    if not request_id:
        raise RuntimeError(f"No request_id in submit response: {data}")
    return str(request_id)


async def submit_task(
    api_node: str,
    payload: dict[str, Any],
    config: dict[str, Any],
    *,
    prompt_id: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """Submit a task asynchronously, matching bizyengine's create_task flow."""
    async with AsyncBizyTRD(
        api_key=config.get("api_key"),
        base_url=config.get("base_url"),
        upload_base_url=config.get("upload_base_url"),
        timeout=config.get("timeout"),
        polling_interval=config.get("polling_interval"),
        max_polling_time=config.get("max_polling_time"),
    ) as client:
        task = await client.create_task(api_node, payload, prompt_id=prompt_id)
        return task.request_id, task.raw_payload


async def poll_task(
    request_id: str,
    config: dict[str, Any],
    *,
    prompt_id: str | None = None,
    original_urls: set[str] | None = None,
) -> dict[str, Any]:
    """Poll task status asynchronously, matching bizyengine's polling loop.

    Args:
        request_id: The task request ID to poll.
        config: Configuration dict with base_url, api_key, polling_interval, max_polling_time.
        prompt_id: Optional prompt ID for header tracking.
        original_urls: A set to accumulate original URLs from "saving" status.
    """
    async with AsyncBizyTRD(
        api_key=config.get("api_key"),
        base_url=config.get("base_url"),
        upload_base_url=config.get("upload_base_url"),
        timeout=config.get("timeout"),
        polling_interval=config.get("polling_interval"),
        max_polling_time=config.get("max_polling_time"),
    ) as client:
        result = await client.wait_for_task(
            request_id,
            prompt_id=prompt_id,
            original_urls=original_urls,
        )
        return result.raw_payload


def send_request(
    method: str = "POST",
    url: str | None = None,
    data: bytes | None = None,
    config: dict[str, Any] | None = None,
    callback: callable = process_response_data,
) -> dict | Any:
    """Synchronous compatibility wrapper that now delegates transport to the SDK."""
    if config is None:
        config = get_config()

    client = BizyTRD(
        api_key=config.get("api_key"),
        base_url=config.get("base_url"),
        upload_base_url=config.get("upload_base_url"),
        timeout=config.get("timeout"),
        polling_interval=config.get("polling_interval"),
        max_polling_time=config.get("max_polling_time"),
    )
    return client._request(
        method=method,
        url=str(url),
        data=data,
        headers=headers or _build_headers(config),
        callback=callback,
    )
