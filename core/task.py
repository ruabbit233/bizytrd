"""Task submission and polling for bizytrd."""

from __future__ import annotations

import time
from typing import Any


SUCCESS_CODE = 20000
ACCEPTED_CODE = 20002
RUNNING_STATUSES = {"running", "saving"}
SUCCESS_STATUSES = {"success"}
FAILED_STATUSES = {"failed"}


def _json_or_raise(response: Any) -> dict[str, Any]:
    try:
        return response.json() if response.text else {}
    except ValueError as exc:
        raise RuntimeError(
            f"Invalid JSON response: HTTP {response.status_code}, body={response.text[:500]}"
        ) from exc


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


def submit_task(model_key: str, payload: dict[str, Any], config: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    import requests

    url = f"{config['base_url'].rstrip('/')}/trd_api/{model_key}"
    headers = {"Content-Type": "application/json"}
    if config.get("api_key"):
        headers["Authorization"] = f"Bearer {config['api_key']}"

    response = requests.post(url, json=payload, headers=headers, timeout=config["timeout"])
    data = _json_or_raise(response)

    if response.status_code >= 400:
        raise RuntimeError(f"Submit failed: HTTP {response.status_code}, body={data}")
    if data.get("status") is False:
        raise RuntimeError(f"Submit failed: {data.get('message') or data}")
    if data.get("code") not in (SUCCESS_CODE, ACCEPTED_CODE, None):
        raise RuntimeError(f"Submit failed: code={data.get('code')} body={data}")

    return _extract_request_id(data), data


def poll_task(request_id: str, config: dict[str, Any]) -> dict[str, Any]:
    import requests

    url = f"{config['base_url'].rstrip('/')}/trd_api/{request_id}"
    headers: dict[str, str] = {}
    if config.get("api_key"):
        headers["Authorization"] = f"Bearer {config['api_key']}"

    started_at = time.time()
    interval = float(config["polling_interval"])
    timeout_seconds = int(config["max_polling_time"])
    last_payload: dict[str, Any] | None = None

    while True:
        if time.time() - started_at > timeout_seconds:
            raise RuntimeError(
                f"Task polling timed out after {timeout_seconds}s for request_id={request_id}. "
                f"Last payload={last_payload}"
            )

        response = requests.get(url, headers=headers, timeout=min(config["timeout"], 30))
        payload = _json_or_raise(response)
        last_payload = payload

        if response.status_code >= 400:
            raise RuntimeError(f"Poll failed: HTTP {response.status_code}, body={payload}")
        if payload.get("status") is False:
            raise RuntimeError(f"Poll failed: {payload.get('message') or payload}")

        data = payload.get("data") or {}
        status = str(data.get("status") or "").strip().lower()

        if status in SUCCESS_STATUSES:
            return payload
        if status in FAILED_STATUSES:
            raise RuntimeError(data.get("message") or payload.get("message") or f"Task failed: {payload}")
        if not status or status in RUNNING_STATUSES:
            time.sleep(interval)
            continue

        time.sleep(interval)
