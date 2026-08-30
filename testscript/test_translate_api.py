"""Authenticated text-translation endpoint tests without external provider calls."""

from types import SimpleNamespace

import pytest
from google import genai
from httpx import ASGITransport, AsyncClient

from alpha_core.api.app import app
from alpha_core.security import create_meeting_invite


@pytest.mark.asyncio
async def test_translate_requires_founder_or_signed_meeting_invite():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/meet/translate-text",
            json={"text": "नमस्ते", "target_language": "en"},
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_translate_accepts_signed_invite_without_founder_token():
    invite_token = create_meeting_invite("translation-room", "Client", role="client")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/meet/translate-text",
            json={
                "text": "This text is already English",
                "target_language": "en",
                "invite_token": invite_token,
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "translated_text": "This text is already English",
        "is_translated": False,
    }


@pytest.mark.asyncio
async def test_translate_uses_requested_language_and_provider_result(api_headers, monkeypatch):
    captured: dict[str, object] = {}

    class FakeModels:
        def generate_content(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(text="Hola equipo")

    monkeypatch.setattr(genai, "Client", lambda **_kwargs: SimpleNamespace(models=FakeModels()))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/meet/translate-text",
            headers=api_headers,
            json={"text": "Hello team", "target_language": "es"},
        )

    assert response.status_code == 200
    assert response.json() == {"translated_text": "Hola equipo", "is_translated": True}
    instruction = captured["config"].system_instruction
    assert "language code es" in instruction


@pytest.mark.asyncio
async def test_translate_rejects_invalid_language_before_provider_call(api_headers):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/meet/translate-text",
            headers=api_headers,
            json={"text": "Hello", "target_language": "../../secret"},
        )

    assert response.status_code == 422
