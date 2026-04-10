"""Task submission and polling for bizytrd — async, aligned with bizyengine."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

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
    """Async HTTP request using aiohttp, matching bizyengine's async_send_request."""
    import aiohttp

    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=600)
    ) as session:
        async with session.request(
            method, url, data=data, headers=headers
        ) as response:
            response_text = await response.text()
            logging.debug(f"Response Data: {response_text}")
            if response.status != 200:
                error_message = (
                    f"HTTP Status {response.status}, response body: {response_text}"
                )
                logging.error(f"Error encountered: {error_message}")
                if response.status == 401:
                    raise PermissionError(
                        "Key is invalid, please refer to https://cloud.siliconflow.cn to get the API key.\n"
                        "If you have the key, please click the 'BizyAir Key' button at the bottom right to set the key."
                    )
                else:
                    raise ConnectionError(
                        f"Failed to connect to the server: {error_message}.\n"
                        + "Please check your API key and ensure the server is reachable.\n"
                        + "Also, verify your network settings and disable any proxies if necessary.\n"
                        + "After checking, please restart the ComfyUI service."
                    )
            parsed = json.loads(response_text)
            if callback:
                return callback(parsed)
            return parsed


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
    model_key: str,
    payload: dict[str, Any],
    config: dict[str, Any],
    *,
    prompt_id: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """Submit a task asynchronously, matching bizyengine's create_task flow."""
    url = f"{config['base_url'].rstrip('/')}/trd_api/{model_key}"
    headers = _build_headers(config, prompt_id=prompt_id)
    json_payload = json.dumps(payload).encode("utf-8")

    logging.debug(f"Submitting task to {url}")
    print(url, json_payload, headers, sep='\n')
    create_api_resp = await async_send_request(
        url=url,
        data=json_payload,
        headers=headers,
    )
    logging.debug(f"Create task api resp: {create_api_resp}")

    if "data" not in create_api_resp or "request_id" not in create_api_resp["data"]:
        logging.error(f"Task creation failed: {create_api_resp}")
        raise ValueError(f"Invalid response: {create_api_resp}")

    request_id = _extract_request_id(create_api_resp)
    logging.info(f"Task created, request_id: {request_id}")
    return request_id, create_api_resp


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
    if original_urls is None:
        original_urls = set()

    url = f"{config['base_url'].rstrip('/')}/trd_api/{request_id}"
    headers = _build_headers(config, prompt_id=prompt_id)

    polling_interval = float(config["polling_interval"])
    max_polling_time = int(config["max_polling_time"])
    start_time = time.time()

    while time.time() - start_time < max_polling_time:
        await asyncio.sleep(polling_interval)

        try:
            status_api_resp = await async_send_request(
                method="GET",
                url=url,
                headers=headers,
            )
        except Exception as e:
            logging.error(f"Task {request_id} status api error: {e}")
            continue

        if "data" not in status_api_resp:
            logging.error(f"Task {request_id} status api resp no data: {status_api_resp}")
            continue
        if "status" not in status_api_resp["data"]:
            logging.error(f"Task {request_id} status api resp no status: {status_api_resp}")
            continue

        status = status_api_resp["data"]["status"]
        logging.debug(f"Task {request_id} status: {status}")

        if status in FAILED_STATUSES:
            logging.error(f"Task {request_id} failed: {status_api_resp}")
            raise ValueError(f"Task {request_id} failed: {status_api_resp}")

        if status in RUNNING_STATUSES:
            continue

        # "saving" status: record original URLs then keep polling
        if status == SAVING_STATUS:
            if "outputs" in status_api_resp["data"]:
                outputs = status_api_resp["data"]["outputs"]
                if "videos" in outputs:
                    for video_url in outputs["videos"]:
                        original_urls.add(video_url)
                if "images" in outputs:
                    for image_url in outputs["images"]:
                        original_urls.add(image_url)
                logging.debug(
                    f"Task {request_id} saving, original URLs: {original_urls}"
                )
            continue

        # Success: expect outputs
        if "outputs" not in status_api_resp["data"]:
            logging.error(f"Task {request_id} no outputs: {status_api_resp}")
            raise ValueError(f"Task {request_id} no outputs: {status_api_resp}")

        logging.info(f"Task {request_id} success: {status_api_resp}")
        return status_api_resp

    logging.error(f"Task {request_id} timed out after {max_polling_time}s")
    raise ValueError(f"Task timed out, request ID: {request_id}")


def send_request(
    method: str = "POST",
    url: str | None = None,
    data: bytes | None = None,
    config: dict[str, Any] | None = None,
    callback: callable = process_response_data,
) -> dict | Any:
    """Synchronous HTTP request using urllib, matching bizyengine's send_request.

    Used for file upload token requests and other sync operations.
    """
    import urllib.error
    import urllib.request

    if config is None:
        config = get_config()

    headers = _build_headers(config)
    timeout = int(config.get("timeout", 60))

    try:
        req = urllib.request.Request(
            url, data=data, headers=headers, method=method
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            response_data = response.read().decode("utf-8")
    except urllib.error.URLError as e:
        error_message = str(e)
        response_body = e.read().decode("utf-8") if hasattr(e, "read") else "N/A"
        logging.error(f"URLError encountered: {error_message}")
        logging.debug(f"Response Body: {response_body}")
        code, message = "N/A", "N/A"
        try:
            response_dict = json.loads(response_body)
            if isinstance(response_dict, dict):
                code = response_dict.get("code", "N/A")
                message = response_dict.get("message", "N/A")
        except json.JSONDecodeError:
            error_info = f"Failed to decode response body as JSON: {str(e)}. Response: {response_body[:200]}"
            raise ConnectionError(f"Invalid server response: {error_info}") from e

        if "Unauthorized" in error_message:
            raise PermissionError(
                "Key is invalid, please refer to https://cloud.siliconflow.cn to get the API key.\n"
                "If you have the key, please click the 'API Key' button at the bottom right to set the key."
            )
        elif code != "N/A" and message != "N/A":
            if code in [20049, 20050]:
                raise ConnectionError(f"Failed to handle your request:\n\n    {message}")
            else:
                raise ConnectionError(
                    f"""Failed to handle your request: {error_message}

    Error code: {code}
    Error message: {message}

    The cause of this issue may be incorrect parameter status or ongoing background tasks.
    If retrying after waiting for a while still does not resolve the issue,
    please report it to Bizyair's official support."""
                )
        else:
            raise ConnectionError(
                f"Failed to connect to the server: {url}.\n"
                "Please check the network connection."
            )

    response_parsed = json.loads(response_data)
    if callback:
        return callback(response_parsed)
    return response_parsed
