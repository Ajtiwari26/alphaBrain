"""
testscript/generate_app_icons.py
Generates Android launcher icons (adaptive, legacy, round) and splash screen drawables
using the approved high-resolution AlphaBrain neural network logo mark.
"""

from pathlib import Path

from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RES_DIR = PROJECT_ROOT / "alphabrain_app" / "android" / "app" / "src" / "main" / "res"
SOURCE_LOGO = PROJECT_ROOT / "testscript" / "splash_preview" / "svg_full_render.png"


def load_alpha_logo() -> Image.Image:
    im = Image.open(SOURCE_LOGO).convert("RGBA")
    gray = im.convert("L")
    inv = gray.point(lambda p: 255 - p if p < 240 else 0)
    bbox = inv.getbbox()
    if not bbox:
        raise ValueError("Could not determine logo bounding box.")

    cropped = im.crop(bbox)
    alpha_mask = gray.crop(bbox).point(lambda p: 255 - p if p < 250 else 0)
    black_img = Image.new("RGBA", cropped.size, (10, 10, 10, 255))
    black_img.putalpha(alpha_mask)
    return black_img


def create_foreground(logo: Image.Image, size: int) -> Image.Image:
    """Creates adaptive icon foreground canvas with logo in safe zone (60%)."""
    target_dim = int(size * 0.60)
    aspect = logo.width / logo.height
    if aspect > 1:
        new_w = target_dim
        new_h = int(target_dim / aspect)
    else:
        new_h = target_dim
        new_w = int(target_dim * aspect)

    resized = logo.resize((new_w, new_h), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    offset = ((size - new_w) // 2, (size - new_h) // 2)
    canvas.paste(resized, offset, resized)
    return canvas


def create_legacy_icon(logo: Image.Image, size: int) -> Image.Image:
    """Creates standard square launcher icon on pure white background."""
    canvas = Image.new("RGBA", (size, size), (255, 255, 255, 255))
    target_dim = int(size * 0.76)
    aspect = logo.width / logo.height
    if aspect > 1:
        new_w = target_dim
        new_h = int(target_dim / aspect)
    else:
        new_h = target_dim
        new_w = int(target_dim * aspect)

    resized = logo.resize((new_w, new_h), Image.Resampling.LANCZOS)
    offset = ((size - new_w) // 2, (size - new_h) // 2)
    canvas.paste(resized, offset, resized)
    return canvas


def create_round_icon(logo: Image.Image, size: int) -> Image.Image:
    """Creates circular launcher icon with white background and transparent corners."""
    square = create_legacy_icon(logo, size)
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size, size), fill=255)

    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(square, (0, 0), mask)
    return canvas


def create_splash(logo: Image.Image, width: int, height: int) -> Image.Image:
    """Creates splash screen with logo centered on pure white background."""
    canvas = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    min_dim = min(width, height)
    target_dim = int(min_dim * 0.40)
    aspect = logo.width / logo.height
    if aspect > 1:
        new_w = target_dim
        new_h = int(target_dim / aspect)
    else:
        new_h = target_dim
        new_w = int(target_dim * aspect)

    resized = logo.resize((new_w, new_h), Image.Resampling.LANCZOS)
    offset_x = (width - new_w) // 2
    offset_y = int((height - new_h) * 0.46)
    canvas.paste(resized, (offset_x, offset_y), resized)
    return canvas.convert("RGB")


def main() -> None:
    logo = load_alpha_logo()
    print("Logo loaded, generating Android icons and splash assets...")

    densities = {
        "mdpi": {"legacy": 48, "fg": 108},
        "hdpi": {"legacy": 72, "fg": 162},
        "xhdpi": {"legacy": 96, "fg": 216},
        "xxhdpi": {"legacy": 144, "fg": 324},
        "xxxhdpi": {"legacy": 192, "fg": 432},
    }

    for density, sizes in densities.items():
        mipmap_dir = RES_DIR / f"mipmap-{density}"
        mipmap_dir.mkdir(parents=True, exist_ok=True)

        # 1. ic_launcher.png
        legacy = create_legacy_icon(logo, sizes["legacy"])
        legacy.save(mipmap_dir / "ic_launcher.png")

        # 2. ic_launcher_round.png
        round_icon = create_round_icon(logo, sizes["legacy"])
        round_icon.save(mipmap_dir / "ic_launcher_round.png")

        # 3. ic_launcher_foreground.png
        fg = create_foreground(logo, sizes["fg"])
        fg.save(mipmap_dir / "ic_launcher_foreground.png")

        print(f"Generated mipmap-{density} icons (legacy={sizes['legacy']}, fg={sizes['fg']})")

    # Splash screens
    splash_targets = [
        ("drawable/splash.png", 480, 320),
        ("drawable-land-mdpi/splash.png", 480, 320),
        ("drawable-land-hdpi/splash.png", 800, 480),
        ("drawable-land-xhdpi/splash.png", 1280, 720),
        ("drawable-land-xxhdpi/splash.png", 1600, 960),
        ("drawable-land-xxxhdpi/splash.png", 1920, 1280),
        ("drawable-port-mdpi/splash.png", 320, 480),
        ("drawable-port-hdpi/splash.png", 480, 800),
        ("drawable-port-xhdpi/splash.png", 720, 1280),
        ("drawable-port-xxhdpi/splash.png", 960, 1600),
        ("drawable-port-xxxhdpi/splash.png", 1280, 1920),
    ]

    for rel_path, w, h in splash_targets:
        dest = RES_DIR / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        splash_img = create_splash(logo, w, h)
        splash_img.save(dest)
        print(f"Generated {rel_path} ({w}x{h})")

    # Remove stale Android robot vector foreground in drawable-v24 if present
    v24_fg = RES_DIR / "drawable-v24" / "ic_launcher_foreground.xml"
    if v24_fg.exists():
        v24_fg.unlink()
        print("Removed obsolete default drawable-v24/ic_launcher_foreground.xml")

    print("All Android app icons and splash screens successfully updated!")


if __name__ == "__main__":
    main()
