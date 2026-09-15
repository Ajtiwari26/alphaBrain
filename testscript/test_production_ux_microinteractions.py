"""Tests for Production UX and Micro-Interactions across Desktop and Mobile apps."""

from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
DESKTOP_SRC = WORKSPACE_ROOT / "alphabrain_desktop" / "src"
MOBILE_SRC = WORKSPACE_ROOT / "alphabrain_app" / "src"


def test_desktop_css_tokens_and_keyframes():
    """Verify that desktop index.css defines smooth transitions, hover-lift, skeleton shimmer, and spinner."""
    css_path = DESKTOP_SRC / "index.css"
    assert css_path.exists(), "Desktop index.css must exist"
    css_content = css_path.read_text()

    assert "--ease-spring" in css_content
    assert ".transition-smooth" in css_content
    assert ".transition-transform-smooth" in css_content
    assert ".hover-lift" in css_content
    assert ".btn-tactile" in css_content
    assert ".card-tactile" in css_content
    assert "skeleton-shimmer" in css_content
    assert ".animate-shimmer" in css_content
    assert "smooth-spin" in css_content
    assert ".animate-spin-smooth" in css_content
    assert "@keyframes screen-enter" in css_content
    assert ".animate-screen-enter" in css_content


def test_mobile_css_tokens_and_keyframes():
    """Verify that mobile index.css defines smooth transitions, hover-lift, skeleton shimmer, and spinner."""
    css_path = MOBILE_SRC / "index.css"
    assert css_path.exists(), "Mobile index.css must exist"
    css_content = css_path.read_text()

    assert "--ease-spring" in css_content
    assert ".transition-smooth" in css_content
    assert ".transition-transform-smooth" in css_content
    assert ".hover-lift" in css_content
    assert ".btn-tactile" in css_content
    assert ".card-tactile" in css_content
    assert "skeleton-shimmer" in css_content
    assert ".animate-shimmer" in css_content
    assert "smooth-spin" in css_content
    assert ".animate-spin-smooth" in css_content
    assert "@keyframes screen-enter" in css_content
    assert ".animate-screen-enter" in css_content


def test_desktop_ui_primitives_exist():
    """Verify reusable LoadingSpinner and Skeleton primitives exist in desktop."""
    spinner_path = DESKTOP_SRC / "components" / "ui" / "LoadingSpinner.tsx"
    skeleton_path = DESKTOP_SRC / "components" / "ui" / "Skeleton.tsx"

    assert spinner_path.exists(), "LoadingSpinner.tsx must exist in desktop components/ui"
    assert skeleton_path.exists(), "Skeleton.tsx must exist in desktop components/ui"

    spinner_code = spinner_path.read_text()
    assert "animate-spin-smooth" in spinner_code
    assert "role=\"status\"" in spinner_code

    skeleton_code = skeleton_path.read_text()
    assert "animate-shimmer" in skeleton_code
    assert "SkeletonTable" in skeleton_code
    assert "SkeletonCard" in skeleton_code


def test_mobile_ui_primitives_exist():
    """Verify reusable LoadingSpinner and Skeleton primitives exist in mobile."""
    spinner_path = MOBILE_SRC / "components" / "ui" / "LoadingSpinner.tsx"
    skeleton_path = MOBILE_SRC / "components" / "ui" / "Skeleton.tsx"

    assert spinner_path.exists(), "LoadingSpinner.tsx must exist in mobile components/ui"
    assert skeleton_path.exists(), "Skeleton.tsx must exist in mobile components/ui"

    spinner_code = spinner_path.read_text()
    assert "animate-spin-smooth" in spinner_code
    assert "role=\"status\"" in spinner_code

    skeleton_code = skeleton_path.read_text()
    assert "animate-shimmer" in skeleton_code
    assert "SkeletonList" in skeleton_code
    assert "SkeletonCard" in skeleton_code


def test_desktop_screens_loading_and_microinteractions():
    """Verify desktop screens integrate loading skeletons, spinners, and hover transitions."""
    projects_screen = (DESKTOP_SRC / "screens" / "ProjectsScreen.tsx").read_text()
    assert "LoadingSpinner" in projects_screen
    assert "SkeletonTable" in projects_screen
    assert "hover-lift" in projects_screen

    triage_screen = (DESKTOP_SRC / "screens" / "TriageQueueScreen.tsx").read_text()
    assert "LoadingSpinner" in triage_screen
    assert "SkeletonTable" in triage_screen
    assert "hover-lift" in triage_screen

    model_router = (DESKTOP_SRC / "screens" / "ModelRouterScreen.tsx").read_text()
    assert "LoadingSpinner" in model_router
    assert "SkeletonCard" in model_router
    assert "hover-lift" in model_router

    emergency_screen = (DESKTOP_SRC / "screens" / "EmergencyStopScreen.tsx").read_text()
    assert "LoadingSpinner" in emergency_screen
    assert "hover-lift" in emergency_screen

    departments_screen = (DESKTOP_SRC / "screens" / "DepartmentsScreen.tsx").read_text()
    assert "hover-lift" in departments_screen
    assert "transition-smooth" in departments_screen


def test_mobile_screens_loading_and_microinteractions():
    """Verify mobile screens integrate loading skeletons, spinners, and tactile hover transitions."""
    projects_screen = (MOBILE_SRC / "screens" / "ProjectsScreen.tsx").read_text()
    assert "LoadingSpinner" in projects_screen
    assert "SkeletonList" in projects_screen
    assert "hover-lift" in projects_screen
    assert "card-tactile" in projects_screen

    triage_screen = (MOBILE_SRC / "screens" / "TriageQueueScreen.tsx").read_text()
    assert "LoadingSpinner" in triage_screen
    assert "SkeletonList" in triage_screen
    assert "hover-lift" in triage_screen
    assert "card-tactile" in triage_screen

    model_router = (MOBILE_SRC / "screens" / "ModelRouterScreen.tsx").read_text()
    assert "LoadingSpinner" in model_router
    assert "SkeletonCard" in model_router
    assert "hover-lift" in model_router
    assert "card-tactile" in model_router

    worktrees_screen = (MOBILE_SRC / "screens" / "WorktreesScreen.tsx").read_text()
    assert "LoadingSpinner" in worktrees_screen
    assert "SkeletonList" in worktrees_screen
    assert "hover-lift" in worktrees_screen
    assert "card-tactile" in worktrees_screen

    dashboard_screen = (MOBILE_SRC / "screens" / "DashboardScreen.tsx").read_text()
    assert "hover-lift" in dashboard_screen
    assert "transition-smooth" in dashboard_screen
    assert "card-tactile" in dashboard_screen

    app_tsx = (MOBILE_SRC / "App.tsx").read_text()
    assert "LoadingSpinner" in app_tsx
    assert "SkeletonCard" in app_tsx
    assert "hover-lift" in app_tsx
    assert "btn-tactile" in app_tsx
