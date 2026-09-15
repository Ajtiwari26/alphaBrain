import xml.etree.ElementTree as ET
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parent.parent


def test_svg_assets_exist_and_are_valid():
    svg_paths = [
        WORKTREE_ROOT / "alphabrain_app" / "public" / "alphabrain_logo.svg",
        WORKTREE_ROOT / "alphabrain_app" / "public" / "deploymate_logo.svg",
        WORKTREE_ROOT / "alphabrain_desktop" / "public" / "alphabrain_logo.svg",
        WORKTREE_ROOT / "alphabrain_desktop" / "public" / "deploymate_logo.svg",
    ]

    for p in svg_paths:
        assert p.exists(), f"Asset does not exist: {p}"
        assert p.stat().st_size > 0, f"Asset is empty: {p}"
        # Validate XML structure
        tree = ET.parse(p)
        root = tree.getroot()
        assert "svg" in root.tag.lower(), f"Root tag is not svg: {root.tag} in {p}"


def test_mac_app_sidebar_cobranding():
    app_tsx = WORKTREE_ROOT / "alphabrain_desktop" / "src" / "App.tsx"
    assert app_tsx.exists()
    content = app_tsx.read_text()
    assert "aside" in content, "Mac app sidebar <aside> not found"
    assert "AlphaBrain is powered by DeployMate" in content, (
        "Mac app sidebar does not visibly display 'AlphaBrain is powered by DeployMate'"
    )
    assert "/alpha_symbol.svg" in content or "/alphabrain_logo.svg" in content, (
        "AlphaBrain SVG logo not found in Mac app"
    )
    assert "/deploymate_logo.svg" in content, (
        "DeployMate SVG logo not found in Mac app"
    )


def test_mobile_splash_screen_cobranding():
    splash_tsx = WORKTREE_ROOT / "alphabrain_app" / "src" / "screens" / "SplashScreen.tsx"
    assert splash_tsx.exists()
    content = splash_tsx.read_text()
    assert "AlphaBrain is powered by DeployMate" in content, (
        "Mobile splash screen does not visibly display 'AlphaBrain is powered by DeployMate'"
    )
    assert "/alpha_symbol.svg" in content or "/alphabrain_logo.svg" in content, (
        "AlphaBrain SVG logo not found in mobile splash screen"
    )
    assert "/deploymate_logo.svg" in content, (
        "DeployMate SVG logo not found in mobile splash screen"
    )


def test_meeting_interfaces_cobranding():
    desktop_meeting = (
        WORKTREE_ROOT / "alphabrain_desktop" / "src" / "screens" / "EvaMeetingScreen.tsx"
    )
    mobile_meeting = (
        WORKTREE_ROOT / "alphabrain_app" / "src" / "screens" / "EvaMeetingScreen.tsx"
    )

    for meeting_file in [desktop_meeting, mobile_meeting]:
        assert meeting_file.exists(), f"Meeting screen does not exist: {meeting_file}"
        content = meeting_file.read_text()
        assert "AlphaBrain is powered by DeployMate" in content, (
            f"{meeting_file.name} does not visibly display 'AlphaBrain is powered by DeployMate'"
        )
        assert "/deploymate_logo.svg" in content, (
            f"{meeting_file.name} does not reference DeployMate SVG logo"
        )


def test_accessibility_compliance():
    """Verify alt attributes for assistive technology across co-branded components."""
    import re
    for rel_path in [
        "alphabrain_desktop/src/App.tsx",
        "alphabrain_desktop/src/screens/EvaMeetingScreen.tsx",
        "alphabrain_app/src/screens/SplashScreen.tsx",
        "alphabrain_app/src/screens/EvaMeetingScreen.tsx",
    ]:
        p = WORKTREE_ROOT / rel_path
        content = p.read_text()
        imgs = re.findall(r"<img[^>]*>", content)
        for img in imgs:
            assert "alt=" in img, f"img tag missing alt attribute in {rel_path}: {img}"
            assert 'alt=""' not in img, f"empty alt attribute in {rel_path}: {img}"
