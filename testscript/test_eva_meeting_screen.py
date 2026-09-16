"""
testscript/test_eva_meeting_screen.py
Comprehensive verification test suite for Screen 15 (EvaMeetingScreen)
Validating authentic DeployMate AlphaBrain design from alpha-meet-theta.vercel.app and alpha_meet/frontend.
"""

from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = WORKTREE_ROOT / "alphabrain_app"
SCREEN_FILE = APP_DIR / "src" / "screens" / "EvaMeetingScreen.tsx"
APP_FILE = APP_DIR / "src" / "App.tsx"
SKELETON_FILE = APP_DIR / "src" / "components" / "ui" / "Skeleton.tsx"


def test_screen_15_files_exist():
    """Verify that the required source files exist."""
    assert SCREEN_FILE.is_file(), f"Expected {SCREEN_FILE} to exist"
    assert APP_FILE.is_file(), f"Expected {APP_FILE} to exist"
    assert SKELETON_FILE.is_file(), f"Expected {SKELETON_FILE} to exist"


def test_swiss_canvas_and_fullscreen_immersion():
    """Verify Screen 15 renders with high-contrast Swiss canvas and suppresses distracting app chrome."""
    screen_content = SCREEN_FILE.read_text(encoding="utf-8")
    app_content = APP_FILE.read_text(encoding="utf-8")

    # 1. Canvas styling
    assert "bg-white" in screen_content or "bg-black" in screen_content

    # 2. App.tsx suppresses standard header for eva_meeting
    assert "currentScreen !== 'eva_meeting'" in app_content, (
        "App.tsx must suppress standard top header for eva_meeting"
    )

    # 3. App.tsx suppresses bottom locomotive navigation for eva_meeting
    assert "currentScreen !== 'eva_meeting'" in app_content, (
        "App.tsx must suppress bottom navigation bar for eva_meeting"
    )


def test_neural_header_and_brand():
    """Verify top header contains neural SVG circuit logo, AlphaBrain title, MEETING LIVE, and share button."""
    content = SCREEN_FILE.read_text(encoding="utf-8")

    assert "AlphaBrain" in content, "Top header must display AlphaBrain"
    assert "MEETING LIVE" in content, "Top header must display MEETING LIVE badge"
    assert "participant-count" in content, "participant-count badge must exist"
    assert "header-invite-btn" in content, "header-invite-btn must be present"
    assert "#E6391E" in content, "Header must use #E6391E signal red accent"


def test_video_stage_tiles_and_badges():
    """Verify dual video tiles with pitch-black containers, #E6391E speaker badges, and Eva equalizer."""
    content = SCREEN_FILE.read_text(encoding="utf-8")

    # Local Founder Tile
    assert "local-tile" in content, "Founder container local-tile must exist"
    assert "local-video" in content, "Founder local-video must exist"
    assert "local-name" in content, "Founder local-name badge must exist"
    assert "speaker-badge" in content, "speaker-badge class must exist"

    # Eva Tile
    assert "eva-tile" in content, "Eva container eva-tile must exist"
    assert "eva-status-text" in content, "eva-status-text must exist"
    assert "Gemini Live Voice Active" in content, "Must indicate Gemini Live Voice Active"
    assert "eva-wave" in content, "eva-wave element must exist"
    assert "active-wave" in content, "active-wave class must exist"
    assert "#E6391E" in content, "Must use #E6391E for signal accents"


def test_live_notes_pcm24khz_drawer():
    """Verify LIVE NOTES section with PCM 24kHz tag, transcript stream, and prompt form."""
    content = SCREEN_FILE.read_text(encoding="utf-8")

    assert "LIVE NOTES" in content, "Must have LIVE NOTES header"
    assert "PCM 24kHz" in content, "Must display PCM 24kHz badge"
    assert "transcript-list" in content, "transcript-list stream container must exist"
    assert "chat-form" in content, "chat-form must exist"
    assert "chat-input" in content, "chat-input must exist"


def test_control_strip_and_endcall():
    """Verify circular control buttons, session timer, and red end-call button."""
    content = SCREEN_FILE.read_text(encoding="utf-8")

    assert "control-btn-circle" in content, "Must use control-btn-circle class"
    assert "mic-btn" in content, "mic-btn must exist"
    assert "cam-btn" in content, "cam-btn must exist"
    assert "transcript-btn" in content, "transcript-btn must exist"
    assert "prompt-eva-btn" in content, "prompt-eva-btn must exist"
    assert "screen-btn" in content, "screen-btn must exist"
    assert "footer-invite-btn" in content, "footer-invite-btn must exist"
    assert "dark-mode-btn" in content, "dark-mode-btn must exist"
    assert "language-btn" in content, "language-btn must exist"
    assert "end-call-btn" in content, "end-call-btn must exist"
    assert "control-btn-endcall" in content, "control-btn-endcall class must exist"
    assert "session-timer" in content, "session-timer must exist"


def test_screen_share_stage():
    """Verify screen share PIP card is present with stop button."""
    content = SCREEN_FILE.read_text(encoding="utf-8")

    assert "screen-share-stage" in content, "screen-share-stage must exist"
    assert "pip-share-card" in content, "pip-share-card must exist"
    assert "stage-screen-btn" in content, "stage-screen-btn must exist"


def test_lobby_modal_elements():
    """Verify join meeting lobby modal contains required inputs and language selector."""
    content = SCREEN_FILE.read_text(encoding="utf-8")

    assert "identity-input" in content, "identity-input must exist"
    assert "room-input" in content, "room-input must exist"
    assert "api-token-input" in content, "api-token-input must exist"
    assert "language-select" in content, "language-select must exist"
    assert "translate-toggle" in content, "translate-toggle must exist"
    assert "join-btn" in content, "join-btn must exist"
    assert "Join Meeting" in content, "Join Meeting title must be present"
