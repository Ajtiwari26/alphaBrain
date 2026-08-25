"""
testscript/test_meet_room.py
Automated tests for LiveKit WebRTC token generator, Eva meeting agent, and meeting REST endpoints.
"""

from urllib.parse import unquote, urlsplit

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from alpha_core.api.app import app, eva_meet_agent
from alpha_core.db.connection import init_db
from alpha_meet.eva_agent import EvaMeetingAgent
from alpha_meet.eva_live_agent import eva_room_manager
from alpha_meet.tokens import LiveKitTokenGenerator


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    await init_db()


def test_livekit_token_generator():
    generator = LiveKitTokenGenerator(
        api_key="test_api_key_12345",
        api_secret="test_secret_with_32_characters_key_len",
    )
    token = generator.generate_token(
        room_name="test-room-101",
        participant_identity="Ajay (Founder)",
        role="founder",
    )
    assert token is not None
    assert isinstance(token, str)
    assert len(token) > 20


def test_eva_meeting_agent():
    agent = EvaMeetingAgent(room_name="test-room-101")
    turn = agent.append_turn("Client", "Can we build a multi-tenant SaaS?")
    assert turn["speaker"] == "Client"
    assert len(agent.transcript_history) == 1

    slide = agent.generate_presentation_slide(project_name="SaaS MVP")
    assert "SaaS MVP" in slide["title"]
    assert "Stitch MCP (Gemini 3.1 Pro)" in slide["tech_stack"]["ui_generation"]
    assert len(slide["verified_gates"]) == 4


@pytest.mark.asyncio
async def test_meet_api_endpoints(api_headers, monkeypatch):
    async def fake_ensure_room(room_name):
        return {
            "identity": "eva-cto",
            "room_name": room_name,
            "state": "ready",
            "voice": "Aoede",
        }

    monkeypatch.setattr(eva_room_manager, "ensure_room", fake_ensure_room)
    monkeypatch.setattr(
        eva_meet_agent,
        "generate_response",
        lambda _speaker, _text: (
            "For DeployMate, use Next.js, FastAPI, and PostgreSQL with verified gates."
        ),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Test /meet page HTML
        resp_page = await ac.get("/meet")
        assert resp_page.status_code == 200
        assert "DeployMate Alpha Brain" in resp_page.text
        assert "default-src 'self'" in resp_page.headers["content-security-policy"]
        assert resp_page.headers["x-content-type-options"] == "nosniff"
        assert resp_page.headers["referrer-policy"] == "no-referrer"

        # 2. Test /api/meet/token
        resp_tok = await ac.post(
            "/api/meet/token",
            headers=api_headers,
            json={
                "room_name": "deploymate-main",
                "identity": "Ajay (Founder)",
                "is_admin": True,
            },
        )
        assert resp_tok.status_code == 200
        data = resp_tok.json()
        assert "token" in data
        assert data["identity"] == "Ajay (Founder)"
        assert data["eva"]["state"] == "ready"

        # 3. Create client-safe invite and join without exposing admin API token.
        resp_invite = await ac.post(
            "/api/meet/invite",
            headers=api_headers,
            json={"room_name": "deploymate-main", "identity": "Test Client"},
        )
        assert resp_invite.status_code == 200
        fragment = urlsplit(resp_invite.json()["join_url"]).fragment
        invite_token = unquote(fragment.removeprefix("invite="))
        resp_client_token = await ac.post(
            "/api/meet/token",
            json={"invite_token": invite_token},
        )
        assert resp_client_token.status_code == 200
        assert resp_client_token.json()["identity"] == "Test Client"
        assert resp_client_token.json()["role"] == "client"

        # 4. Test /api/meet/slide
        resp_slide = await ac.get(
            "/api/meet/slide?project=alphaBrain",
            headers=api_headers,
        )
        assert resp_slide.status_code == 200
        assert "Architectural Plan" in resp_slide.json()["title"]

        # 5. Test /api/meet/speak
        resp_speak = await ac.post(
            "/api/meet/speak",
            headers=api_headers,
            json={
                "speaker": "Ajay",
                "text": "What tech stack do you recommend?",
            },
        )
        assert resp_speak.status_code == 200
        assert "DeployMate" in resp_speak.json()["eva_reply"]
        assert "Next.js" in resp_speak.json()["eva_reply"]
        assert any(
            turn["speaker"] == "Ajay" and turn["text"] == "What tech stack do you recommend?"
            for turn in resp_speak.json()["transcript"]
        )


def test_meeting_frontend_uses_livekit_not_browser_voice_simulation():
    root = __import__("pathlib").Path(__file__).resolve().parent.parent
    html = (root / "alpha_meet/frontend/index.html").read_text()
    javascript = (root / "alpha_meet/frontend/js/meet.js").read_text()

    assert "livekit-client@2.22.0" in html
    assert "/static/meet/js/meet.js?v=" in html
    assert "new Room(" in javascript
    assert "setMicrophoneEnabled(true)" in javascript
    assert "setScreenShareEnabled" in javascript
    assert 'registerTextStreamHandler("lk.transcription"' in javascript
    assert "RoomEvent.TranscriptionReceived" in javascript
    assert "speechSynthesis" not in javascript
    assert "SpeechRecognition" not in javascript
    assert "onclick=" not in html
    assert "onsubmit=" not in html
    assert 'getElementById("chat-form")?.addEventListener' in javascript
    assert 'EVA_TARGET_TOPIC = "alpha.eva.target"' in javascript
    assert "localParticipant.publishData" in javascript
