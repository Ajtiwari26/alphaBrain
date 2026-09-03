"""
testscript/test_eva_token_factory.py
Unit tests verifying Eva's read-only consumer token invariants for LiveKit.
"""

import pytest

from alpha_core.eva.token_factory import (
    inspect_eva_token,
    mint_eva_consumer_token,
)


def test_mint_eva_consumer_token_default_grants():
    room = "test-boardroom-alpha"
    identity = "eva-cto-observer"
    name = "Eva (CTO)"
    key = "devkey" + "a" * 20
    secret = "secret" + "b" * 30

    token = mint_eva_consumer_token(
        room_name=room,
        identity=identity,
        name=name,
        valid_minutes=45,
        api_key=key,
        api_secret=secret,
    )

    assert isinstance(token, str)
    assert len(token) > 50

    inspection = inspect_eva_token(token, api_secret=secret)
    assert inspection["identity"] == identity
    assert inspection["name"] == name
    assert inspection["room"] == room

    # Strict architectural invariants
    assert inspection["can_publish"] is False
    assert inspection["can_subscribe"] is True
    assert inspection["can_publish_data"] is False
    assert inspection["hidden"] is True
    assert inspection["is_compliant"] is True


def test_mint_eva_consumer_token_rejects_empty_room():
    with pytest.raises(ValueError, match="room_name must be non-empty"):
        mint_eva_consumer_token(
            room_name="   ",
            api_key="key" * 10,
            api_secret="secret" * 10,
        )


def test_mint_eva_consumer_token_rejects_missing_credentials(monkeypatch):
    monkeypatch.setattr("alpha_core.config.settings.LIVEKIT_API_KEY", "")
    monkeypatch.setattr("alpha_core.config.settings.LIVEKIT_API_SECRET", "")

    with pytest.raises(ValueError, match="must be configured"):
        mint_eva_consumer_token(room_name="room-1")
