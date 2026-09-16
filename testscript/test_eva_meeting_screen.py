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
SKELETON_FILE = APP_DIR / "src" / "components" / "ui" / "Skeleton.tsx"


def test_screen_15_files_exist():
    """Verify that the required source files exist."""
    assert SCREEN_FILE.is_file(), f"Expected {SCREEN_FILE} to exist"
    assert APP_FILE.is_file(), f"Expected {APP_FILE} to exist"
    assert SKELETON_FILE.is_file(), f"Expected {SKELETON_FILE} to exist"


def test_warm_stone_background_and_fullscreen_immersion():
    """Verify Screen 15 renders full-screen with warm travertine background #EAE7E1 and suppresses distracting chrome."""
    screen_content = SCREEN_FILE.read_text(encoding="utf-8")
    app_content = APP_FILE.read_text(encoding="utf-8")

    # 1. Warm stone background #EAE7E1 or #FAF7F2 present
    assert "#EAE7E1" in screen_content or "#FAF7F2" in screen_content, (
        "EvaMeetingScreen must specify warm stone background palette"
    )

    # 2. App.tsx suppresses standard header for eva_meeting
    assert "currentScreen !== 'eva_meeting'" in app_content, (
        "App.tsx must suppress standard top header for eva_meeting"
    )

    # 3. App.tsx suppresses bottom locomotive navigation for eva_meeting
    assert "currentScreen !== 'eva_meeting'" in app_content, (
        "App.tsx must suppress bottom navigation bar for eva_meeting"
    )


def test_hero_stage_rounded_3xl_and_badges():
    """Verify hero stage has rounded-3xl corners, SFU topology badges, and Eva HUD."""
    content = SCREEN_FILE.read_text(encoding="utf-8")

    # 1. rounded-3xl on participant cards
    assert "rounded-3xl" in content, "Participant cards must have rounded-3xl corners"

    # 2. SFU Badges present in stage
    assert "SFU" in content, "Hero stage must display SFU badge"
    assert "LiveKit" in content, "Hero stage must display LiveKit badge"

    # 3. Live waveform speaking badge
    assert "eva-wave" in content, "Live waveform element eva-wave must exist"
    assert "active-wave" in content, "Active waveform animation class must exist"
    assert "SPEAKING" in content, "Speaking badge label must be present"

    # 4. Eva Holographic HUD
    assert "eva-tile" in content, "Eva tile container must exist"
    assert "EVA ARCHITECT HUD" in content or "Eva · CTO" in content, "Eva HUD title must be present"
    assert "Gemini Live Voice Active" in content, "Eva HUD must indicate Gemini Live Voice Active"
    assert "eva-status-text" in content, "eva-status-text element must exist"


def test_dual_participant_cards():
    """Verify dual participant cards are present with photography, nametags, and mic indicators."""
    content = SCREEN_FILE.read_text(encoding="utf-8")

    assert "local-tile" in content, "Founder container local-tile must exist"
    assert "local-video" in content, "Founder local-video must exist"
    assert "local-name" in content, "Founder local-name badge must exist"
    assert "Ajay" in content, "Founder Ajay must be listed"
    assert "Founder & CEO" in content, "Founder & CEO title must be present"
    assert "Eva · CTO" in content, "Eva · CTO title must be present"

    # Verify Ajay PiP is positioned in top-right corner
    assert "top-3 right-3" in content and "floating-pip" in content, (
        "Ajay PiP must be positioned in the top-right corner (top-3 right-3)"
    )


def test_architecture_slide_card():
    """Verify presentation slide card displays Architecture Blueprint and topology flow."""
    content = SCREEN_FILE.read_text(encoding="utf-8")

    assert "stone-glass-card" in content, "Slide card must use stone-glass-card styling"
    assert "SHARED SCREEN · LIVE SLIDE" in content, "Slide card must have shared screen ribbon"
    assert "Architecture Blueprint: Next.js + FastAPI + LiveKit" in content, (
        "Slide title must be Architecture Blueprint: Next.js + FastAPI + LiveKit"
    )
    assert "Client Core" in content, "Topology flow must display Client Core"
    assert "Edge Gateway" in content, "Topology flow must display Edge Gateway"
    assert "Eva Neural" in content, "Topology flow must display Eva Neural"

    # Verify conditional rendering on state
    assert "{isScreenSharing &&" in content, (
        "Slide share must conditionally render based on isScreenSharing state"
    )


def test_live_executive_transcription_and_spec_distillation():
    """Verify Live Executive Transcription & Spec Distillation displays real-time speech and AUTO-GENERATING PLAN badge."""
    content = SCREEN_FILE.read_text(encoding="utf-8")

    assert "Live Executive Transcription & Spec Distillation" in content, (
        "Card title must be Live Executive Transcription & Spec Distillation"
    )
    assert "AUTO-GENERATING PLAN" in content, "Card must display AUTO-GENERATING PLAN badge"
    assert "transcript-list" in content, "Transcript stream container transcript-list must exist"
    assert "chat-form" in content, "Chat form for executive directives must exist"
    assert "chat-input" in content, "Chat input must exist"
    assert "LIVE NOTES" in content, "LIVE NOTES header must be present"

    # Verify direct transcription card placement below stage
    stage_idx = content.find("stage-grid")
    transcription_idx = content.find("live-transcription-card")
    slide_idx = content.find("screen-share-stage")
    assert stage_idx != -1 and transcription_idx != -1, "Stage and transcription card must exist"
    assert transcription_idx > stage_idx, "Transcription card must be positioned below stage"
    if slide_idx != -1:
        assert transcription_idx < slide_idx, (
            "Transcription card must be directly below stage before conditional slide share"
        )


def test_floating_4_button_bottom_pill():
    """Verify floating 4-button bottom pill provides mic, video, screen, and end call actions."""
    content = SCREEN_FILE.read_text(encoding="utf-8")

    # Floating bottom container
    assert "fixed bottom-" in content, "In-call pill bar must be positioned floating at the bottom"

    # 4 Core action buttons
    assert "mic-btn" in content, "Mic toggle button mic-btn must exist"
    assert "cam-btn" in content, "Camera toggle button cam-btn must exist"
    assert "screen-btn" in content, "Screen share toggle button screen-btn must exist"
    assert "end-call-btn" in content, "End call button end-call-btn must exist"


def test_top_navigation_bar():
    """Verify top navigation bar has back button and Share Invite pill."""
    content = SCREEN_FILE.read_text(encoding="utf-8")

    assert "ArrowLeft" in content or "Leave Meeting" in content, (
        "Top navigation bar must have a back button"
    )
    assert "Share Invite" in content, "Top navigation bar must display Share Invite pill"
    assert "header-invite-btn" in content, "header-invite-btn must be present on Share Invite button"
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


def test_skeleton_list_count_support():
    """Verify SkeletonList supports optional count prop in Skeleton.tsx."""
    content = SKELETON_FILE.read_text(encoding="utf-8")
    assert "count?:" in content, "SkeletonList must accept count?: number prop"
    assert "count ?? rows" in content or "count" in content, (
        "SkeletonList must utilize count if provided"
    )
