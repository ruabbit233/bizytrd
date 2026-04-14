"""Clients for BizyTRD network requests."""

from __future__ import annotations

import asyncio
import base64
import datetime
import hashlib
import hmac
import io
import json
import logging
import time
from importlib import import_module
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.error import URLError
from urllib.request import Request, urlopen

from .config import CLIENT_VERSION, SDKConfig, get_config
from .errors import (
    BizyTRDConnectionError,
    BizyTRDError,
    BizyTRDPermissionError,
    BizyTRDResponseError,
    BizyTRDTimeoutError,
)
from .types import DownloadedOutputs, TaskHandle, TaskResult

RUNNING_STATUSES = {"running", "queuing"}
SAVING_STATUS = "saving"
FAILED_STATUSES = {"failed"}


def _require_aiohttp():
    try:
        return import_module("aiohttp")
    except ModuleNotFoundError as exc:
        raise BizyTRDConnectionError(
            "aiohttp is required for bizytrd_sdk async networking. Install project dependencies first."
        ) from exc


def process_response_data(response_data: dict[str, Any]) -> dict[str, Any]:
    if "result" in response_data:
        try:
            message = json.loads(response_data["result"])
            if "request_id" in response_data and "request_id" not in message:
                message["request_id"] = response_data["request_id"]
            return message
        except json.JSONDecodeError as exc:
            raise BizyTRDResponseError(
                f"Failed to decode JSON from response. response_data={response_data}"
            ) from exc
    return response_data


def build_headers(
    api_key: str | None = None,
    *,
    prompt_id: str | None = None,
) -> dict[str, str]:
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "User-Agent": "BizyAir Client",
        "x-bizyair-client-version": CLIENT_VERSION,
    }
    if api_key:
        headers["authorization"] = f"Bearer {api_key}"
    if prompt_id:
        headers["X-BIZYAIR-PROMPT-ID"] = prompt_id
    return headers


def _extract_request_id(data: dict[str, Any]) -> str:
    request_id = (
        (data.get("data") or {}).get("request_id")
        or (data.get("data") or {}).get("requestId")
        or data.get("request_id")
        or data.get("requestId")
    )
    if not request_id:
        raise BizyTRDResponseError(f"No request_id in submit response: {data}")
    return str(request_id)


def _parse_upload_token(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    if not isinstance(data, dict):
        raise BizyTRDResponseError(f"Upload token response missing data: {payload}")

    file_info = data.get("file")
    storage = data.get("storage")
    if not isinstance(file_info, dict) or not isinstance(storage, dict):
        raise BizyTRDResponseError(
            f"Upload token response missing file/storage: {payload}"
        )
    return file_info | storage


def _sign_request(
    method: str,
    bucket: str,
    object_key: str,
    headers: dict[str, str],
    access_key_id: str,
    access_key_secret: str,
) -> str:
    canonical_string = f"{method}\n"
    canonical_string += f"{headers.get('Content-MD5', '')}\n"
    canonical_string += f"{headers.get('Content-Type', '')}\n"
    canonical_string += f"{headers.get('Date', '')}\n"

    for key in sorted(headers.keys()):
        if key.lower().startswith("x-oss-"):
            canonical_string += f"{key.lower()}:{headers[key]}\n"

    canonical_string += f"/{bucket}/{object_key}"
    digest = hmac.new(
        access_key_secret.encode("utf-8"),
        canonical_string.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    signature = base64.b64encode(digest).decode("utf-8")
    return f"OSS {access_key_id}:{signature}"


class AsyncBizyTRD:
    """Async BizyTRD SDK client.

    This intentionally mirrors the current project's request/upload/polling logic.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        upload_base_url: str | None = None,
        timeout: int | None = None,
        polling_interval: float | None = None,
        max_polling_time: int | None = None,
        session: Any = None,
    ) -> None:
        resolved = get_config()
        self.config = SDKConfig(
            base_url=(base_url or resolved.base_url).rstrip("/"),
            api_key=(api_key if api_key is not None else resolved.api_key).strip(),
            upload_base_url=(upload_base_url or resolved.upload_base_url).rstrip("/"),
            timeout=int(timeout if timeout is not None else resolved.timeout),
            polling_interval=float(
                polling_interval
                if polling_interval is not None
                else resolved.polling_interval
            ),
            max_polling_time=int(
                max_polling_time
                if max_polling_time is not None
                else resolved.max_polling_time
            ),
        )
        self._session = session
        self._owns_session = session is None
        self.responses = _ResponsesAPI(self)
        self.uploads = _UploadsAPI(self)

    async def __aenter__(self) -> "AsyncBizyTRD":
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def close(self) -> None:
        if self._session is not None and self._owns_session:
            await self._session.close()
        self._session = None

    async def _ensure_session(self) -> Any:
        aiohttp = _require_aiohttp()
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    def _build_headers(self, *, prompt_id: str | None = None) -> dict[str, str]:
        return build_headers(self.config.api_key, prompt_id=prompt_id)

    async def _request(
        self,
        *,
        method: str,
        url: str,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
        callback: Any = process_response_data,
        timeout: int | float | None = None,
    ) -> dict[str, Any]:
        aiohttp = _require_aiohttp()
        session = await self._ensure_session()
        request_timeout = (
            aiohttp.ClientTimeout(total=float(timeout)) if timeout is not None else None
        )
        response_text = ""
        try:
            async with session.request(
                method,
                url,
                data=data,
                headers=headers,
                timeout=request_timeout,
            ) as response:
                response_text = await response.text()
                logging.debug("Response Data: %s", response_text)
                if response.status != 200:
                    error_message = (
                        f"HTTP Status {response.status}, response body: {response_text}"
                    )
                    logging.error("Error encountered: %s", error_message)
                    if response.status == 401:
                        raise BizyTRDPermissionError(
                            "Key is invalid, please refer to https://cloud.siliconflow.cn "
                            "to get the API key.\nIf you have the key, please click the "
                            "'BizyAir Key' button at the bottom right to set the key."
                        )
                    raise BizyTRDConnectionError(
                        f"Failed to connect to the server: {error_message}.\n"
                        + "Please check your API key and ensure the server is reachable.\n"
                        + "Also, verify your network settings and disable any proxies if necessary.\n"
                        + "After checking, please restart the ComfyUI service."
                    )
                parsed = json.loads(response_text)
        except aiohttp.ClientError as exc:
            raise BizyTRDConnectionError(str(exc)) from exc
        except asyncio.TimeoutError as exc:
            raise BizyTRDTimeoutError(f"Request timed out: {url}") from exc
        except json.JSONDecodeError as exc:
            raise BizyTRDResponseError(
                f"Invalid JSON response from server: {response_text[:500]}"
            ) from exc

        if callback:
            return callback(parsed)
        return parsed

    async def create_task(
        self,
        api_node: str,
        payload: dict[str, Any],
        *,
        prompt_id: str | None = None,
    ) -> TaskHandle:
        url = f"{self.config.base_url.rstrip('/')}/trd_api/{api_node}"
        headers = self._build_headers(prompt_id=prompt_id)
        json_payload = json.dumps(payload).encode("utf-8")

        logging.debug("Submitting task to %s", url)
        create_api_resp = await self._request(
            method="POST",
            url=url,
            data=json_payload,
            headers=headers,
        )
        logging.debug("Create task api resp: %s", create_api_resp)

        if "data" not in create_api_resp or "request_id" not in create_api_resp["data"]:
            logging.error("Task creation failed: %s", create_api_resp)
            raise BizyTRDResponseError(f"Invalid response: {create_api_resp}")

        request_id = _extract_request_id(create_api_resp)
        logging.info("Task created, request_id: %s", request_id)
        return TaskHandle(
            client=self,
            request_id=request_id,
            model=api_node,
            raw_payload=create_api_resp,
        )

    async def responses_create(
        self,
        *,
        model: str,
        input: dict[str, Any],
        prompt_id: str | None = None,
    ) -> TaskHandle:
        return await self.create_task(model, input, prompt_id=prompt_id)

    async def retrieve_task(
        self,
        request_id: str,
        *,
        prompt_id: str | None = None,
    ) -> dict[str, Any]:
        url = f"{self.config.base_url.rstrip('/')}/trd_api/{request_id}"
        headers = self._build_headers(prompt_id=prompt_id)
        return await self._request(method="GET", url=url, headers=headers)

    async def wait_for_task(
        self,
        request_id: str,
        *,
        prompt_id: str | None = None,
        polling_interval: float | None = None,
        max_polling_time: int | None = None,
        original_urls: set[str] | None = None,
    ) -> TaskResult:
        if original_urls is None:
            original_urls = set()

        url = f"{self.config.base_url.rstrip('/')}/trd_api/{request_id}"
        headers = self._build_headers(prompt_id=prompt_id)
        interval = float(
            polling_interval
            if polling_interval is not None
            else self.config.polling_interval
        )
        timeout = int(
            max_polling_time
            if max_polling_time is not None
            else self.config.max_polling_time
        )
        start_time = time.time()

        while time.time() - start_time < timeout:
            await asyncio.sleep(interval)

            try:
                status_api_resp = await self._request(
                    method="GET",
                    url=url,
                    headers=headers,
                )
            except BizyTRDError as exc:
                logging.error("Task %s status api error: %s", request_id, exc)
                continue

            data = status_api_resp.get("data")
            if not isinstance(data, dict):
                logging.error(
                    "Task %s status api resp no data: %s", request_id, status_api_resp
                )
                continue

            status = data.get("status")
            if not status:
                logging.error(
                    "Task %s status api resp no status: %s",
                    request_id,
                    status_api_resp,
                )
                continue

            logging.debug("Task %s status: %s", request_id, status)

            if status in FAILED_STATUSES:
                logging.error("Task %s failed: %s", request_id, status_api_resp)
                raise BizyTRDResponseError(
                    f"Task {request_id} failed: {status_api_resp}"
                )

            if status in RUNNING_STATUSES:
                continue

            if status == SAVING_STATUS:
                outputs = data.get("outputs") or {}
                if isinstance(outputs, dict):
                    for video_url in outputs.get("videos") or []:
                        original_urls.add(str(video_url))
                    for image_url in outputs.get("images") or []:
                        original_urls.add(str(image_url))
                continue

            outputs = data.get("outputs")
            if not isinstance(outputs, dict):
                logging.error("Task %s no outputs: %s", request_id, status_api_resp)
                raise BizyTRDResponseError(
                    f"Task {request_id} no outputs: {status_api_resp}"
                )

            return TaskResult(
                request_id=request_id,
                status=str(status),
                outputs=outputs,
                raw_payload=status_api_resp,
                original_urls=sorted(original_urls),
            )

        logging.error("Task %s timed out after %ss", request_id, timeout)
        raise BizyTRDTimeoutError(f"Task timed out, request ID: {request_id}")

    async def request_upload_token(
        self,
        file_name: str,
        *,
        file_type: str = "inputs",
    ) -> dict[str, Any]:
        if not str(self.config.api_key or "").strip():
            raise BizyTRDResponseError(
                "BizyTRD API key is empty. Set BIZYAIR_API_KEY or BIZYTRD_API_KEY."
            )

        url = (
            f"{self.config.upload_base_url.rstrip('/')}/upload/token"
            f"?file_name={quote(file_name)}&file_type={quote(file_type)}"
        )
        payload = await self._request(
            method="GET",
            url=url,
            headers=self._build_headers(),
            timeout=max(self.config.timeout, 10),
        )
        if payload.get("status") is False:
            raise BizyTRDResponseError(f"Upload token request failed: {payload}")
        return _parse_upload_token(payload)

    async def upload_bytes(
        self,
        file_content: bytes | bytearray | io.BytesIO,
        file_name: str,
        *,
        file_type: str = "inputs",
    ) -> str:
        auth_info = await self.request_upload_token(file_name, file_type=file_type)
        return await self._upload_file(file_content=file_content, **auth_info)

    async def upload_file(
        self,
        path: str | Path,
        *,
        file_name: str | None = None,
        file_type: str = "inputs",
    ) -> str:
        target_path = Path(path).expanduser()
        file_bytes = target_path.read_bytes()
        return await self.upload_bytes(
            file_bytes,
            file_name or target_path.name,
            file_type=file_type,
        )

    async def _upload_file(
        self,
        *,
        file_content: bytes | bytearray | io.BytesIO,
        bucket: str,
        object_key: str,
        endpoint: str,
        access_key_id: str,
        access_key_secret: str,
        security_token: str,
        **_: Any,
    ) -> str:
        aiohttp = _require_aiohttp()
        if isinstance(file_content, io.BytesIO):
            file_content.seek(0)
            body = file_content.read()
        else:
            body = bytes(file_content)

        date = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%a, %d %b %Y %H:%M:%S GMT"
        )
        headers = {
            "Host": f"{bucket}.{endpoint}",
            "Date": date,
            "Content-Type": "application/octet-stream",
            "Content-Length": str(len(body)),
            "x-oss-security-token": security_token,
        }
        headers["Authorization"] = _sign_request(
            "PUT",
            bucket,
            object_key,
            headers,
            access_key_id,
            access_key_secret,
        )

        url = f"https://{bucket}.{endpoint}/{object_key}"
        session = await self._ensure_session()
        try:
            async with session.put(url, headers=headers, data=body, timeout=300) as response:
                response_text = await response.text()
                if response.status >= 400:
                    raise BizyTRDResponseError(
                        f"Bizy upload failed: HTTP {response.status}, body={response_text[:500]}"
                    )
        except aiohttp.ClientError as exc:
            raise BizyTRDConnectionError(str(exc)) from exc
        except asyncio.TimeoutError as exc:
            raise BizyTRDTimeoutError(f"Upload timed out: {url}") from exc
        return url

    async def download_outputs(self, outputs: dict[str, Any]) -> DownloadedOutputs:
        session = await self._ensure_session()
        downloaded = DownloadedOutputs()

        for video_url in outputs.get("videos") or []:
            async with session.get(str(video_url), timeout=3600) as response:
                response.raise_for_status()
                downloaded.videos.append(await response.read())
                downloaded.urls.append(str(video_url))

        for image_url in outputs.get("images") or []:
            async with session.get(str(image_url), timeout=3600) as response:
                response.raise_for_status()
                downloaded.images.append(await response.read())
                downloaded.urls.append(str(image_url))

        for text in outputs.get("texts") or []:
            downloaded.texts.append(str(text))

        return downloaded


class BizyTRD:
    """Synchronous BizyTRD SDK client for upload-oriented call sites."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        upload_base_url: str | None = None,
        timeout: int | None = None,
        polling_interval: float | None = None,
        max_polling_time: int | None = None,
    ) -> None:
        resolved = get_config()
        self.config = SDKConfig(
            base_url=(base_url or resolved.base_url).rstrip("/"),
            api_key=(api_key if api_key is not None else resolved.api_key).strip(),
            upload_base_url=(upload_base_url or resolved.upload_base_url).rstrip("/"),
            timeout=int(timeout if timeout is not None else resolved.timeout),
            polling_interval=float(
                polling_interval
                if polling_interval is not None
                else resolved.polling_interval
            ),
            max_polling_time=int(
                max_polling_time
                if max_polling_time is not None
                else resolved.max_polling_time
            ),
        )

    def _build_headers(self, *, prompt_id: str | None = None) -> dict[str, str]:
        return build_headers(self.config.api_key, prompt_id=prompt_id)

    def _request(
        self,
        *,
        method: str,
        url: str,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
        callback: Any = process_response_data,
        timeout: int | float | None = None,
    ) -> dict[str, Any]:
        response_data = ""
        try:
            req = Request(url, data=data, headers=headers or {}, method=method)
            with urlopen(req, timeout=float(timeout or 3600)) as response:
                response_data = response.read().decode("utf-8")
        except URLError as exc:
            error_message = str(exc)
            response_body = exc.read().decode("utf-8") if hasattr(exc, "read") else "N/A"
            logging.error("URLError encountered: %s", error_message)
            logging.debug("Response Body: %s", response_body)
            code, message = "N/A", "N/A"
            try:
                response_dict = json.loads(response_body)
                if isinstance(response_dict, dict):
                    code = response_dict.get("code", "N/A")
                    message = response_dict.get("message", "N/A")
            except json.JSONDecodeError as json_exc:
                raise BizyTRDConnectionError(
                    f"Invalid server response: Failed to decode response body as JSON: {exc}. "
                    f"Response: {response_body[:200]}"
                ) from json_exc

            if "Unauthorized" in error_message:
                raise BizyTRDPermissionError(
                    "Key is invalid, please refer to https://cloud.siliconflow.cn "
                    "to get the API key.\nIf you have the key, please click the "
                    "'API Key' button at the bottom right to set the key."
                ) from exc
            if code != "N/A" and message != "N/A":
                if code in [20049, 20050]:
                    raise BizyTRDConnectionError(
                        f"Failed to handle your request:\n\n    {message}"
                    ) from exc
                raise BizyTRDConnectionError(
                    f"""Failed to handle your request: {error_message}

    Error code: {code}
    Error message: {message}

    The cause of this issue may be incorrect parameter status or ongoing background tasks.
    If retrying after waiting for a while still does not resolve the issue,
    please report it to Bizyair's official support."""
                ) from exc
            raise BizyTRDConnectionError(
                f"Failed to connect to the server: {url}.\nPlease check the network connection."
            ) from exc
        except TimeoutError as exc:
            raise BizyTRDTimeoutError(f"Request timed out: {url}") from exc

        try:
            parsed = json.loads(response_data)
        except json.JSONDecodeError as exc:
            raise BizyTRDResponseError(
                f"Invalid JSON response from server: {response_data[:500]}"
            ) from exc

        if callback:
            return callback(parsed)
        return parsed

    def request_upload_token(
        self,
        file_name: str,
        *,
        file_type: str = "inputs",
    ) -> dict[str, Any]:
        if not str(self.config.api_key or "").strip():
            raise BizyTRDResponseError(
                "BizyTRD API key is empty. Set BIZYAIR_API_KEY or BIZYTRD_API_KEY."
            )

        url = (
            f"{self.config.upload_base_url.rstrip('/')}/upload/token"
            f"?file_name={quote(file_name)}&file_type={quote(file_type)}"
        )
        payload = self._request(
            method="GET",
            url=url,
            headers=self._build_headers(),
            timeout=max(self.config.timeout, 10),
        )
        if payload.get("status") is False:
            raise BizyTRDResponseError(f"Upload token request failed: {payload}")
        return _parse_upload_token(payload)

    def upload_bytes(
        self,
        file_content: bytes | bytearray | io.BytesIO,
        file_name: str,
        *,
        file_type: str = "inputs",
    ) -> str:
        auth_info = self.request_upload_token(file_name, file_type=file_type)
        return self._upload_file(file_content=file_content, **auth_info)

    def upload_file(
        self,
        path: str | Path,
        *,
        file_name: str | None = None,
        file_type: str = "inputs",
    ) -> str:
        target_path = Path(path).expanduser()
        return self.upload_bytes(
            target_path.read_bytes(),
            file_name or target_path.name,
            file_type=file_type,
        )

    def _upload_file(
        self,
        *,
        file_content: bytes | bytearray | io.BytesIO,
        bucket: str,
        object_key: str,
        endpoint: str,
        access_key_id: str,
        access_key_secret: str,
        security_token: str,
        **_: Any,
    ) -> str:
        import requests

        if isinstance(file_content, io.BytesIO):
            file_content.seek(0)
            body = file_content.read()
        else:
            body = bytes(file_content)

        date = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%a, %d %b %Y %H:%M:%S GMT"
        )
        headers = {
            "Host": f"{bucket}.{endpoint}",
            "Date": date,
            "Content-Type": "application/octet-stream",
            "Content-Length": str(len(body)),
            "x-oss-security-token": security_token,
        }
        headers["Authorization"] = _sign_request(
            "PUT",
            bucket,
            object_key,
            headers,
            access_key_id,
            access_key_secret,
        )

        url = f"https://{bucket}.{endpoint}/{object_key}"
        try:
            response = requests.put(url, headers=headers, data=body, timeout=300)
        except requests.RequestException as exc:
            raise BizyTRDConnectionError(str(exc)) from exc
        if response.status_code >= 400:
            raise BizyTRDResponseError(
                f"Bizy upload failed: HTTP {response.status_code}, body={response.text[:500]}"
            )
        return url


class _ResponsesAPI:
    def __init__(self, client: AsyncBizyTRD) -> None:
        self._client = client

    async def create(
        self,
        *,
        model: str,
        input: dict[str, Any],
        prompt_id: str | None = None,
    ) -> TaskHandle:
        return await self._client.responses_create(
            model=model,
            input=input,
            prompt_id=prompt_id,
        )

    async def retrieve(
        self,
        request_id: str,
        *,
        prompt_id: str | None = None,
    ) -> dict[str, Any]:
        return await self._client.retrieve_task(request_id, prompt_id=prompt_id)

    async def wait(
        self,
        request_id: str,
        *,
        prompt_id: str | None = None,
        polling_interval: float | None = None,
        max_polling_time: int | None = None,
    ) -> TaskResult:
        return await self._client.wait_for_task(
            request_id,
            prompt_id=prompt_id,
            polling_interval=polling_interval,
            max_polling_time=max_polling_time,
        )


class _UploadsAPI:
    def __init__(self, client: AsyncBizyTRD) -> None:
        self._client = client

    async def request_token(
        self,
        file_name: str,
        *,
        file_type: str = "inputs",
    ) -> dict[str, Any]:
        return await self._client.request_upload_token(
            file_name,
            file_type=file_type,
        )

    async def create_bytes(
        self,
        file_content: bytes | bytearray | io.BytesIO,
        file_name: str,
        *,
        file_type: str = "inputs",
    ) -> str:
        return await self._client.upload_bytes(
            file_content,
            file_name,
            file_type=file_type,
        )

    async def create_file(
        self,
        path: str | Path,
        *,
        file_name: str | None = None,
        file_type: str = "inputs",
    ) -> str:
        return await self._client.upload_file(
            path,
            file_name=file_name,
            file_type=file_type,
        )
