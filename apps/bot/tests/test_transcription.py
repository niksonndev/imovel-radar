import asyncio

import httpx
import pytest

from infrastructure.ai.transcription import transcribe_audio


def test_transcribe_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/audio/transcriptions"
        assert b'filename="audio.ogg"' in request.content
        assert b"Content-Type: audio/ogg" in request.content
        return httpx.Response(
            200, json={"text": "quero alugar em ponta verde até 2000"}, request=request
        )

    transport = httpx.MockTransport(mock_handler)
    real_async_client = httpx.AsyncClient

    def custom_async_client(*args, **kwargs):
        kwargs["transport"] = transport
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", custom_async_client)

    result = asyncio.run(transcribe_audio(b"audio-bytes", api_key="k", content_type="audio/ogg"))
    assert result == "quero alugar em ponta verde até 2000"


def test_transcribe_error_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="err", request=request)

    transport = httpx.MockTransport(mock_handler)
    real_async_client = httpx.AsyncClient

    def custom_async_client(*args, **kwargs):
        kwargs["transport"] = transport
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", custom_async_client)

    result = asyncio.run(transcribe_audio(b"audio", api_key="k"))
    assert result is None


def test_transcribe_empty_guard() -> None:
    assert asyncio.run(transcribe_audio(b"", api_key="k")) is None
    assert asyncio.run(transcribe_audio(b"bytes", api_key="")) is None
