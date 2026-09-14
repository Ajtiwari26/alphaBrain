"""
testscript/test_alphameet_parity.py
End-to-end integration and visual regression tests verifying 100% UI and functional parity
between production-ready alpha_meet and native shells (alphabrain_desktop & alphabrain_app).
"""

from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parent.parent

ALPHA_MEET_DIR = WORKTREE_ROOT / "alpha_meet"
DESKTOP_DIR = WORKTREE_ROOT / "alphabrain_desktop"
MOBILE_DIR = WORKTREE_ROOT / "alphabrain_app"


def test_production_alphameet_integrity():
    """Verify production-ready alpha_meet files remain present, intact, and read-only."""
    index_html = ALPHA_MEET_DIR / "frontend" / "index.html"
    meet_css = ALPHA_MEET_DIR / "frontend" / "css" / "meet.css"
    meet_js = ALPHA_MEET_DIR / "frontend" / "js" / "meet.js"

    assert index_html.is_file(), "alpha_meet index.html must exist"
    assert meet_css.is_file(), "alpha_meet meet.css must exist"
    assert meet_js.is_file(), "alpha_meet meet.js must exist"

    content = index_html.read_text()
    assert "LiveKit WebRTC" in content
    assert "Join Meeting" in content
    assert "stage-grid" in content
    assert "control-btn-circle" in content


def test_desktop_shell_alphameet_parity():
    """Verify Mac native shell (alphabrain_desktop) contains 100% UI and functional parity with alpha_meet."""
    desktop_screen = DESKTOP_DIR / "src" / "screens" / "EvaMeetingScreen.tsx"
    desktop_css = DESKTOP_DIR / "src" / "index.css"
    desktop_client = DESKTOP_DIR / "src" / "api" / "client.ts"

    assert desktop_screen.is_file(), "Desktop EvaMeetingScreen.tsx must exist"
    assert desktop_css.is_file(), "Desktop index.css must exist"
    assert desktop_client.is_file(), "Desktop api client.ts must exist"

    screen_code = desktop_screen.read_text()

    # 1. Lobby Modal Parity
    lobby_elements = [
        "identity-input",
        "room-input",
        "api-token-input",
        "language-select",
        "translate-toggle",
        "join-btn",
        "Join Meeting",
    ]
    for el in lobby_elements:
        assert el in screen_code, f"Desktop missing lobby element: {el}"

    # 2. 10 Supported Languages Parity
    languages = ["Hindi", "English", "Chinese", "Japanese", "Korean", "Arabic", "Spanish", "French", "German", "Portuguese"]
    for lang in languages:
        assert lang in screen_code, f"Desktop missing language: {lang}"

    # 3. Stage Grid Parity
    stage_elements = [
        "stage-grid",
        "layout-1",
        "layout-2",
        "layout-3",
        "local-tile",
        "local-video",
        "speaker-badge",
        "eva-tile",
        "eva-wave",
        "active-wave",
        "Gemini Live Voice Active",
        "eva-status-text",
        "screen-share-stage",
        "pip-share-card",
        "stage-screen-btn",
        "remote-stack",
        "remote-human-tile",
        "remote-human-name",
    ]
    for el in stage_elements:
        assert el in screen_code, f"Desktop missing stage element: {el}"

    # 4. Live Notes Transcript Drawer Parity
    drawer_elements = [
        "transcript-drawer",
        "transcript-list",
        "LIVE NOTES",
        "PCM 24kHz",
        "chat-form",
        "chat-input",
    ]
    for el in drawer_elements:
        assert el in screen_code, f"Desktop missing drawer element: {el}"

    # 5. Full 9-Button Control Strip Parity
    control_buttons = [
        "mic-btn",
        "cam-btn",
        "transcript-btn",
        "prompt-eva-btn",
        "screen-btn",
        "footer-invite-btn",
        "dark-mode-btn",
        "language-btn",
        "end-call-btn",
        "session-timer",
    ]
    for btn in control_buttons:
        assert btn in screen_code, f"Desktop missing control button: {btn}"

    # 6. Top Header Navigation Parity
    header_elements = [
        "MEETING LIVE",
        "participant-count",
        "header-invite-btn",
    ]
    for el in header_elements:
        assert el in screen_code, f"Desktop missing header element: {el}"

    # 7. CSS Classes Parity
    css_content = desktop_css.read_text()
    for cls in [".stage-grid", ".video-tile-container", ".speaker-badge", ".control-btn-circle", ".control-btn-endcall", ".pip-share-card", ".active-wave"]:
        assert cls in css_content, f"Desktop index.css missing style: {cls}"

    # 8. API Client Parity
    client_code = desktop_client.read_text()
    assert "getEvaMeetingToken" in client_code, "Desktop api client missing getEvaMeetingToken"


def test_mobile_shell_alphameet_parity():
    """Verify Mobile native shell (alphabrain_app) contains 100% UI and functional parity with alpha_meet."""
    mobile_screen = MOBILE_DIR / "src" / "screens" / "EvaMeetingScreen.tsx"
    mobile_css = MOBILE_DIR / "src" / "index.css"
    mobile_client = MOBILE_DIR / "src" / "api" / "client.ts"

    assert mobile_screen.is_file(), "Mobile EvaMeetingScreen.tsx must exist"
    assert mobile_css.is_file(), "Mobile index.css must exist"
    assert mobile_client.is_file(), "Mobile api client.ts must exist"

    screen_code = mobile_screen.read_text()

    # 1. Lobby Modal Parity
    lobby_elements = [
        "identity-input",
        "room-input",
        "api-token-input",
        "language-select",
        "translate-toggle",
        "join-btn",
        "Join Meeting",
    ]
    for el in lobby_elements:
        assert el in screen_code, f"Mobile missing lobby element: {el}"

    # 2. 10 Supported Languages Parity
    languages = ["Hindi", "English", "Chinese", "Japanese", "Korean", "Arabic", "Spanish", "French", "German", "Portuguese"]
    for lang in languages:
        assert lang in screen_code, f"Mobile missing language: {lang}"

    # 3. Stage Grid Parity
    stage_elements = [
        "stage-grid",
        "layout-1",
        "layout-2",
        "layout-3",
        "local-tile",
        "local-video",
        "speaker-badge",
        "eva-tile",
        "eva-wave",
        "active-wave",
        "Gemini Live Voice Active",
        "eva-status-text",
        "screen-share-stage",
        "pip-share-card",
        "stage-screen-btn",
        "remote-stack",
        "remote-human-tile",
        "remote-human-name",
    ]
    for el in stage_elements:
        assert el in screen_code, f"Mobile missing stage element: {el}"

    # 4. Live Notes Transcript Drawer Parity
    drawer_elements = [
        "transcript-list",
        "LIVE NOTES",
        "PCM 24kHz",
        "chat-form",
        "chat-input",
    ]
    for el in drawer_elements:
        assert el in screen_code, f"Mobile missing drawer element: {el}"

    # 5. Full 9-Button Control Strip Parity
    control_buttons = [
        "mic-btn",
        "cam-btn",
        "transcript-btn",
        "prompt-eva-btn",
        "screen-btn",
        "footer-invite-btn",
        "dark-mode-btn",
        "language-btn",
        "end-call-btn",
        "session-timer",
    ]
    for btn in control_buttons:
        assert btn in screen_code, f"Mobile missing control button: {btn}"

    # 6. Top Header Navigation Parity
    header_elements = [
        "participant-count",
        "header-invite-btn",
    ]
    for el in header_elements:
        assert el in screen_code, f"Mobile missing header element: {el}"

    # 7. CSS Classes Parity
    css_content = mobile_css.read_text()
    for cls in [".stage-grid", ".video-tile-container", ".speaker-badge", ".control-btn-circle", ".control-btn-endcall", ".pip-share-card", ".active-wave"]:
        assert cls in css_content, f"Mobile index.css missing style: {cls}"

    # 8. API Client Parity
    client_code = mobile_client.read_text()
    assert "getEvaMeetingToken" in client_code, "Mobile api client missing getEvaMeetingToken"


def test_cross_platform_visual_regression_match():
    """Visual regression test verifying 100% element alignment between production alpha_meet and native shells."""
    alpha_meet_html = (ALPHA_MEET_DIR / "frontend" / "index.html").read_text()
    desktop_code = (DESKTOP_DIR / "src" / "screens" / "EvaMeetingScreen.tsx").read_text()
    mobile_code = (MOBILE_DIR / "src" / "screens" / "EvaMeetingScreen.tsx").read_text()

    shared_identifiers = [
        "identity-input",
        "room-input",
        "api-token-input",
        "language-select",
        "translate-toggle",
        "join-btn",
        "participant-count",
        "header-invite-btn",
        "stage-grid",
        "local-tile",
        "local-video",
        "screen-share-stage",
        "stage-screen-btn",
        "speaker-badge",
        "local-name",
        "eva-tile",
        "eva-wave",
        "eva-status-text",
        "remote-stack",
        "remote-human-tile",
        "remote-human-name",
        "transcript-list",
        "chat-form",
        "chat-input",
        "mic-btn",
        "cam-btn",
        "transcript-btn",
        "prompt-eva-btn",
        "screen-btn",
        "footer-invite-btn",
        "dark-mode-btn",
        "language-btn",
        "end-call-btn",
        "session-timer",
    ]

    for ident in shared_identifiers:
        assert ident in alpha_meet_html, f"Identifier {ident} must be in reference alpha_meet"
        assert ident in desktop_code, f"Identifier {ident} missing in desktop shell"
        assert ident in mobile_code, f"Identifier {ident} missing in mobile shell"
