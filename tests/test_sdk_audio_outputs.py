import asyncio


def test_task_result_output_urls_include_audio_urls():
    from bizytrd_sdk.types import TaskResult

    result = TaskResult(
        request_id="request-1",
        status="succeeded",
        outputs={
            "videos": ["https://example.com/video.mp4"],
            "images": ["https://example.com/image.webp"],
            "audios": ["https://example.com/audio.mp3"],
        },
        raw_payload={},
    )

    assert result.output_urls == [
        "https://example.com/video.mp4",
        "https://example.com/image.webp",
        "https://example.com/audio.mp3",
    ]


def test_async_client_download_outputs_downloads_audio_bytes(monkeypatch):
    from bizytrd_sdk import AsyncBizyTRD

    class FakeResponse:
        def __init__(self, payload: bytes):
            self._payload = payload

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        def raise_for_status(self):
            return None

        async def read(self):
            return self._payload

    class FakeSession:
        closed = False

        def get(self, url, timeout):
            return FakeResponse(f"bytes:{url}".encode("utf-8"))

    monkeypatch.setenv("BIZYTRD_API_KEY", "test-key")
    client = AsyncBizyTRD(session=FakeSession())

    downloaded = asyncio.run(
        client.download_outputs({"audios": ["https://example.com/audio.mp3"]})
    )

    assert downloaded.audios == [b"bytes:https://example.com/audio.mp3"]
    assert downloaded.urls == ["https://example.com/audio.mp3"]


def test_sync_client_exposes_audio_upload_helpers(monkeypatch):
    from bizytrd_sdk import BizyTRD

    class RecordingClient(BizyTRD):
        def __init__(self):
            super().__init__(api_key="test-key")
            self.calls = []

        def upload_bytes(self, file_content, file_name, *, file_type="inputs"):
            self.calls.append((file_content, file_name, file_type))
            return "https://example.com/audio.mp3"

    client = RecordingClient()

    assert client.upload_audio_bytes(b"audio-bytes", "audio.mp3") == "https://example.com/audio.mp3"
    assert client.calls == [(b"audio-bytes", "audio.mp3", "inputs")]


def test_async_client_exposes_audio_upload_helpers(monkeypatch):
    from bizytrd_sdk import AsyncBizyTRD

    class RecordingClient(AsyncBizyTRD):
        def __init__(self):
            super().__init__(api_key="test-key", session=object())
            self.calls = []

        async def upload_bytes(self, file_content, file_name, *, file_type="inputs"):
            self.calls.append((file_content, file_name, file_type))
            return "https://example.com/audio.mp3"

    client = RecordingClient()
    result = asyncio.run(client.upload_audio_bytes(b"audio-bytes", "audio.mp3"))

    assert result == "https://example.com/audio.mp3"
    assert client.calls == [(b"audio-bytes", "audio.mp3", "inputs")]
