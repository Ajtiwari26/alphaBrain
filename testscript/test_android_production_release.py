"""
testscript/test_android_production_release.py
Production verification tests for Android Production Build Release deliverable.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = PROJECT_ROOT / "alphabrain_app" / "android" / "app"
BUILD_GRADLE = APP_DIR / "build.gradle"
GITIGNORE = PROJECT_ROOT / ".gitignore"
STRINGS_XML = APP_DIR / "src" / "main" / "res" / "values" / "strings.xml"
COLORS_XML = APP_DIR / "src" / "main" / "res" / "values" / "colors.xml"


def test_build_gradle_production_signing_config():
    assert BUILD_GRADLE.exists(), "alphabrain_app/android/app/build.gradle must exist"
    content = BUILD_GRADLE.read_text(encoding="utf-8")

    assert "signingConfigs" in content, "signingConfigs block must be configured"
    assert "release" in content, "release signingConfig must be defined"
    assert "KEYSTORE_PASSWORD" in content, "Keystore password must be parameterized via env vars"
    assert "KEY_PASSWORD" in content, "Key password must be parameterized via env vars"
    assert "signingConfig signingConfigs.release" in content, "release buildType must use release signingConfig"
    assert "compileOptions" in content, "Java 17 compileOptions must be present"
    assert "JavaVersion.VERSION_17" in content, "Java 17 compatibility must be enforced"


def test_keystore_ignored_in_git():
    assert GITIGNORE.exists(), ".gitignore must exist in root"
    content = GITIGNORE.read_text(encoding="utf-8")
    assert "*.keystore" in content or "release.keystore" in content, "Keystores must be excluded from Git"


def test_branding_assets_and_metadata():
    assert STRINGS_XML.exists(), "strings.xml must exist"
    strings_content = STRINGS_XML.read_text(encoding="utf-8")
    assert "AlphaBrain &amp; DeployMate" in strings_content or "AlphaBrain" in strings_content

    assert COLORS_XML.exists(), "colors.xml must exist"
    colors_content = COLORS_XML.read_text(encoding="utf-8")
    assert "#E6391E" in colors_content, "AlphaBrain brand red #E6391E must be present"
    assert "#0A0A0A" in colors_content, "AlphaBrain brand black #0A0A0A must be present"


def test_production_release_apk_generated():
    # Verify the compiled production release APK exists and has non-trivial size
    root_apk = PROJECT_ROOT / "alphabrain-production-release.apk"
    gradle_apk_dir = APP_DIR / "build" / "outputs" / "apk" / "release"
    gradle_apk = list(gradle_apk_dir.glob("*.apk")) if gradle_apk_dir.exists() else []

    assert root_apk.exists() or len(gradle_apk) > 0, "A valid production release APK must be generated"
    apk_file = root_apk if root_apk.exists() else gradle_apk[0]
    assert apk_file.stat().st_size > 100_000, f"APK file size {apk_file.stat().st_size} bytes is unexpectedly small"
