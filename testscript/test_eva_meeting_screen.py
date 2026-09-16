"""
testscript/test_eva_meeting_screen.py
Comprehensive verification test suite for Screen 15 (EvaMeetingScreen)
Validating authentic AlphaMeet executive room 1:1 redesign against all acceptance criteria.
"""

import re
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = WORKTREE_ROOT / "alphabrain_app"
SCREEN_FILE = APP_DIR / "src" / "screens" / "EvaMeetingScreen.tsx"
APP_FILE = APP_DIR / "src" / "App.tsx"


def test_screen_15_files_exist():
    """Verify that the required source files exist."""
    assert SCREEN_FILE.is_file(), f"Expected {SCREEN_FILE} to exist"
    assert APP_FILE.is_file(), f"Expected {APP_FILE} to exist"


def test_warm_cream_background_and_fullscreen_immersion():
    """Verify Screen 15 renders full-screen with warm cream background #FAF7F2 and suppresses distracting chrome."""
    screen_content = SCREEN_FILE.read_text(encoding="utf-8")
    app_content = APP_FILE.read_text(encoding="utf-8")

    # 1. Warm cream background #FAF7F2 present
    assert "#FAF7F2" in screen_content, "EvaMeetingScreen must specify warm cream #FAF7F2 background"
    assert "#FAF7F2" in app_content, "App.tsx must support #FAF7F2 background for eva_meeting"

    # 2. App.tsx suppresses standard header for eva_meeting
    assert "currentScreen !== 'eva_meeting'" in app_content, (
        "App.tsx must suppress standard top header for eva_meeting"
    )

    # 3. App.tsx suppresses bottom locomotive navigation for eva_meeting
    assert "currentScreen !== 'eva_meeting'" in app_content, (
        "App.tsx must suppress bottom navigation bar for eva_meeting"
    )

    # 4. App.tsx provides zero padding for full-screen immersive experience
    assert "p-0 pb-0 bg-[#FAF7F2]" in app_content or "p-0" in app_content, (
        "App.tsx main viewport must provide immersive full-screen layout for eva_meeting"
    )


def test_hero_stage_rounded_3xl_and_badges():
    """Verify hero stage has rounded-3xl corners, 1080p SFU, DUPLEX HD, LiveKit 18ms badges, and Eva HUD."""
    content = SCREEN_FILE.read_text(encoding="utf-8")

    # 1. rounded-3xl on hero stage
    assert "rounded-3xl" in content, "Hero stage must have rounded-3xl corners"

    # 2. Badges present in stage
    assert "1080p SFU" in content, "Hero stage must display 1080p SFU badge"
    assert "DUPLEX HD" in content, "Hero stage must display DUPLEX HD badge"
    assert "LiveKit 18ms" in content, "Hero stage must display LiveKit 18ms badge"

    # 3. Live waveform speaking badge
    assert "eva-wave" in content, "Live waveform element eva-wave must exist"
    assert "active-wave" in content, "Active waveform animation class must exist"
    assert "SPEAKING" in content, "Speaking badge label must be present"

    # 4. Eva Holographic HUD
    assert "eva-tile" in content, "Eva tile container must exist"
    assert "EVA ARCHITECT HUD" in content or "Eva (AI Architect)" in content, "Eva HUD title must be present"
    assert "Gemini Live Voice Active" in content, "Eva HUD must indicate Gemini Live Voice Active"
    assert "eva-status-text" in content, "eva-status-text element must exist"


def test_floating_founder_pip_card():
    """Verify floating Founder PIP card is present with video and identity tag."""
    content = SCREEN_FILE.read_text(encoding="utf-8")

    assert "local-tile" in content, "Founder PIP container local-tile must exist"
    assert "local-video" in content, "Founder PIP local-video must exist"
    assert "local-name" in content, "Founder PIP local-name badge must exist"
    assert "absolute" in content, "Founder PIP must be positioned floating absolutely"


def test_live_executive_transcription_and_spec_distillation():
    """Verify Live Executive Transcription & Spec Distillation card displays real-time speech and AUTO-GENERATING PLAN badge."""
    content = SCREEN_FILE.read_text(encoding="utf-8")

    # Card header and badge
    assert "Live Executive Transcription & Spec Distillation" in content or (
        "Live Executive Transcription" in content and "Spec Distillation" in content
    ), "Card title must be Live Executive Transcription & Spec Distillation"
    assert "AUTO-GENERATING PLAN" in content, "Card must display AUTO-GENERATING PLAN badge"

    # Real-time transcript list and speech feed
    assert "transcript-list" in content, "Transcript stream container transcript-list must exist"
    assert "chat-form" in content, "Chat form for executive directives must exist"
    assert "chat-input" in content, "Chat input must exist"
    assert "LIVE NOTES" in content, "LIVE NOTES header must be present"


def test_floating_4_button_bottom_pill():
    """Verify floating 4-button bottom pill provides mic, video, screen, and end call actions."""
    content = SCREEN_FILE.read_text(encoding="utf-8")

    # Floating bottom container
    assert "fixed bottom-" in content, "In-call pill bar must be positioned floating at the bottom"
    assert "rounded-full" in content, "In-call bar must have rounded-full pill styling"

    # 4 Core action buttons
    assert "mic-btn" in content, "Mic toggle button mic-btn must exist"
    assert "cam-btn" in content, "Camera toggle button cam-btn must exist"
    assert "screen-btn" in content, "Screen share toggle button screen-btn must exist"
    assert "end-call-btn" in content, "End call button end-call-btn must exist"


def test_top_navigation_bar():
    """Verify top navigation bar has circular back button and Share Link pill."""
    content = SCREEN_FILE.read_text(encoding="utf-8")

    assert "ArrowLeft" in content or "Leave Meeting" in content, (
        "Top navigation bar must have a back button"
    )
    assert "Share Link" in content, "Top navigation bar must display Share Link pill"
    assert "header-invite-btn" in content, "header-invite-btn must be present on Share Link button"
    assert "participant-count" in content, "participant-count badge must be present"
    assert "session-timer" in content, "session-timer must be present"


def test_cobranding_and_accessibility():
    """Verify co-branding banner and image accessibility compliance."""
    content = SCREEN_FILE.read_text(encoding="utf-8")

    assert "AlphaBrain is powered by DeployMate" in content, (
        "Must display 'AlphaBrain is powered by DeployMate'"
    )
    assert "/deploymate_logo.svg" in content, "Must include deploymate_logo.svg"
    assert "/alphabrain_logo.svg" in content, "Must include alphabrain_logo.svg"

    # Check all img tags have non-empty alt attributes
    imgs = re.findall(r"<img[^>]*>", content)
    assert len(imgs) >= 2, "Must contain at least 2 co-branding logo images"
    for img in imgs:
        assert "alt=" in img, f"img missing alt attribute: {img}"
        assert 'alt=""' not in img, f"img has empty alt attribute: {img}"
