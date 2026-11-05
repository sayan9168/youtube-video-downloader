#!/usr/bin/env python3
"""Regenerate the bundled demo media and PWA icons.

Only needed when the artwork changes; the generated files are committed so the
app works out of the box.

Requirements:
    pip install pillow imageio-ffmpeg
Usage:
    python scripts/generate_assets.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
DEMO_DIR = ROOT / "static" / "demo"
ICON_DIR = ROOT / "static" / "icons"

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def load_font(size: int) -> ImageFont.FreeTypeFont:
    for candidate in FONT_CANDIDATES:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def gradient(size: tuple[int, int], top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    width, height = size
    image = Image.new("RGB", size)
    draw = ImageDraw.Draw(image)
    for y in range(height):
        ratio = y / max(1, height - 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * ratio) for i in range(3))
        draw.line([(0, y), (width, y)], fill=color)
    return image


def draw_download_glyph(draw: ImageDraw.ImageDraw, box: tuple[float, float, float, float], color=(255, 255, 255, 255)):
    """Draw a modern download arrow (shaft + arrow head + tray)."""
    left, top, right, bottom = box
    size = right - left
    cx = (left + right) / 2
    shaft_width = size * 0.17
    head_width = size * 0.62
    shaft_top = top + size * 0.1
    shaft_bottom = top + size * 0.55
    draw.rounded_rectangle(
        [cx - shaft_width / 2, shaft_top, cx + shaft_width / 2, shaft_bottom],
        radius=shaft_width / 2,
        fill=color,
    )
    draw.polygon(
        [
            (cx - head_width / 2, shaft_bottom - size * 0.06),
            (cx + head_width / 2, shaft_bottom - size * 0.06),
            (cx, bottom - size * 0.08),
        ],
        fill=color,
    )
    tray_top = bottom - size * 0.04
    tray_height = size * 0.1
    draw.rounded_rectangle(
        [left + size * 0.1, tray_top - tray_height, right - size * 0.1, tray_top],
        radius=tray_height / 2,
        fill=color,
    )


def make_icon(size: int, maskable: bool = False) -> Image.Image:
    scale = 4
    canvas = size * scale
    image = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    padding = int(canvas * (0.12 if maskable else 0.05))
    inner = canvas - padding * 2
    radius = int(inner * (0.5 if maskable else 0.24))

    background = gradient((inner, inner), (248, 113, 113), (185, 28, 28)).convert("RGBA")
    mask = Image.new("L", (inner, inner), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, inner - 1, inner - 1], radius=radius, fill=255)
    image.paste(background, (padding, padding), mask)

    glyph_inset = inner * (0.28 if maskable else 0.24)
    glyph_box = (
        padding + glyph_inset,
        padding + glyph_inset,
        padding + inner - glyph_inset,
        padding + inner - glyph_inset,
    )
    draw = ImageDraw.Draw(image)
    if maskable:
        # keep the glyph small enough for the safe zone
        glyph_box = tuple(
            padding + inner * 0.3 + (value - padding - inner * 0.3) * 0.88 for value in glyph_box
        )
        draw = ImageDraw.Draw(image)
    draw_download_glyph(draw, glyph_box)
    return image.resize((size, size), Image.LANCZOS)


def make_thumbnail() -> None:
    width, height = 1280, 720
    image = gradient((width, height), (15, 23, 42), (30, 27, 75)).convert("RGBA")
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for cx, cy, radius, color in [
        (1080, 90, 320, (239, 68, 68, 70)),
        (120, 660, 280, (59, 130, 246, 55)),
        (700, 380, 320, (168, 85, 247, 45)),
    ]:
        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=color)
    image = Image.alpha_composite(image, overlay)

    draw = ImageDraw.Draw(image)
    # play button
    cx, cy, radius = width // 2, 330, 96
    draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=(255, 255, 255, 235))
    draw.polygon([(cx - 30, cy - 44), (cx - 30, cy + 44), (cx + 48, cy)], fill=(190, 18, 60, 255))

    title_font = load_font(64)
    sub_font = load_font(34)
    title = "DEMO VIDEO"
    sub = "Sample clip for the downloader UI"
    title_w = draw.textlength(title, font=title_font)
    sub_w = draw.textlength(sub, font=sub_font)
    draw.text(((width - title_w) / 2, 470), title, font=title_font, fill=(255, 255, 255, 255))
    draw.text(((width - sub_w) / 2, 560), sub, font=sub_font, fill=(226, 232, 240, 235))
    image.convert("RGB").save(DEMO_DIR / "thumbnail.jpg", quality=82, optimize=True)


def make_subtitles() -> None:
    lines = {
        "en": [
            "Demo mode is running.",
            "Every feature of the downloader works without touching YouTube.",
            "Queue several links to watch the progress bars.",
            "Subtitles, playlists and history are all previewed here.",
        ],
        "bn": [
            "এটি ডেমো মোড।",
            "ইউটিউবে কোনো অনুরোধ পাঠানো হচ্ছে না।",
            "একাধিক লিংক দিয়ে কিউ ও প্রগ্রেস বার দেখুন।",
            "সাবটাইটেল, প্লেলিস্ট ও হিস্ট্রি সবই এখানে দেখা যাবে।",
        ],
    }
    for lang, texts in lines.items():
        srt, vtt = [], ["WEBVTT", ""]
        for index, text in enumerate(texts, start=1):
            start = (index - 1) * 3
            end = start + 3
            stamp_srt = f"00:00:{start:02d},000 --> 00:00:{end:02d},000"
            stamp_vtt = stamp_srt.replace(",", ".")
            srt.append(f"{index}\n{stamp_srt}\n{text}\n")
            vtt.append(f"{stamp_vtt}\n{text}\n")
        (DEMO_DIR / f"subtitle.{lang}.srt").write_text("\n".join(srt), encoding="utf-8")
        (DEMO_DIR / f"subtitle.{lang}.vtt").write_text("\n".join(vtt), encoding="utf-8")


def make_media() -> None:
    try:
        import imageio_ffmpeg
    except ImportError:
        print("imageio-ffmpeg not installed - skipping sample media generation")
        return
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    video = DEMO_DIR / "sample.mp4"
    subprocess.run(
        [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=12:duration=4",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "34",
            "-c:a", "aac", "-b:a", "48k", "-shortest", "-movflags", "+faststart",
            str(video),
        ],
        check=True,
    )
    subprocess.run(
        [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(video), "-vn",
         "-c:a", "libmp3lame", "-b:a", "64k", str(DEMO_DIR / "sample.mp3")],
        check=True,
    )


def main() -> int:
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    ICON_DIR.mkdir(parents=True, exist_ok=True)

    make_thumbnail()
    make_subtitles()
    make_media()

    icon_192 = make_icon(192)
    icon_192.save(ICON_DIR / "icon-192.png", optimize=True)
    icon_512 = make_icon(512)
    icon_512.save(ICON_DIR / "icon-512.png", optimize=True)
    make_icon(512, maskable=True).save(ICON_DIR / "icon-maskable-512.png", optimize=True)
    make_icon(180).save(ICON_DIR / "apple-touch-icon.png", optimize=True)
    make_icon(64).save(ICON_DIR / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])

    print("Assets written to", DEMO_DIR, "and", ICON_DIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
