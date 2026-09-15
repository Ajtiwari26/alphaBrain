"""
testscript/test_android_production_release.py
Acceptance tests for Android Production Build Release task.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = PROJECT_ROOT / "alphabrain_app" / "android" / "app"
BUILD_GRADLE = APP_DIR / "build.gradle"
KEYSTORE = APP_DIR / "release.keystore"
RES_DIR = APP_DIR / "src" / "main" / "res"


def test_build_gradle_production_signing_config():
    assert BUILD_GRADLE.exists(), "alphabrain_app/android/app/build.gradle must exist"
    content = BUILD_GRADLE.read_text(encoding="utf-8")

    assert "signingConfigs" in content, "signingConfigs block must be configured"
    assert "release" in content, "release signingConfig must be defined"
    assert "release.keystore" in content
    assert "signingConfig signingConfigs.release" in content, "release buildType must use release signingConfig"


def test_production_keystore_exists():
    assert KEYSTORE.exists(), "Production release.keystore must exist in app directory"
    assert KEYSTORE.stat().st_size > 0, "Keystore file must not be empty"


def test_branding_assets_packaged():
    assert RES_DIR.exists(), "Android res directory must exist"
    drawables = list(RES_DIR.glob("**/ic_launcher*")) + list(RES_DIR.glob("**/splash*"))
    assert len(drawables) > 0, "Branding icons and splash drawables must be present"


def test_production_apk_build_and_verification():
    from testscript.build_signed_apk import OUTPUT_DIR
    from testscript.build_signed_apk import main as build_apk_main

    build_apk_main()
    signed_apk = OUTPUT_DIR / "app-release.apk"
    assert signed_apk.exists(), "app-release.apk must be successfully generated"
    assert signed_apk.stat().st_size > 5000, "Signed APK size must be non-trivial"
