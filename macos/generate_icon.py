#!/usr/bin/env python3
"""Generate AppNews.icns for the Desktop launcher.

Draws a simple "news card" glyph (gradient tile + white card + headline bars
+ accent dot) as a 1024x1024 RGBA PNG using nothing but the standard library
(struct + zlib for PNG encoding — no Pillow dependency), then shells out to
macOS's built-in `sips` and `iconutil` to produce the .icns bundle icon.
"""
from __future__ import annotations

import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path

SIZE = 1024
MACOS_DIR = Path(__file__).resolve().parent
PNG_PATH = MACOS_DIR / "AppIcon1024.png"
ICONSET_DIR = MACOS_DIR / "AppIcon.iconset"
ICNS_PATH = MACOS_DIR / "AppNews.icns"

ICONSET_SIZES = [
    ("icon_16x16.png", 16),
    ("icon_16x16@2x.png", 32),
    ("icon_32x32.png", 32),
    ("icon_32x32@2x.png", 64),
    ("icon_128x128.png", 128),
    ("icon_128x128@2x.png", 256),
    ("icon_256x256.png", 256),
    ("icon_256x256@2x.png", 512),
    ("icon_512x512.png", 512),
    ("icon_512x512@2x.png", 1024),
]


def write_png(path: Path, width: int, height: int, rgba: bytes) -> None:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)  # 8-bit RGBA

    stride = width * 4
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # scanline filter: none
        raw.extend(rgba[y * stride : (y + 1) * stride])
    idat = zlib.compress(bytes(raw), 9)

    with open(path, "wb") as f:
        f.write(sig)
        f.write(chunk(b"IHDR", ihdr))
        f.write(chunk(b"IDAT", idat))
        f.write(chunk(b"IEND", b""))


def rounded_row_bounds(y: int, top: int, bottom: int, left: int, right: int, r: int):
    """Scanline x-bounds for a rounded rect at row y, or (None, None) outside it."""
    if y < top or y >= bottom:
        return None, None
    dy_top = y - top
    dy_bot = (bottom - 1) - y
    inset = 0
    for dy in (dy_top, dy_bot):
        if dy < r:
            d = r - dy
            under_sqrt = r * r - d * d
            corner_inset = r - int(under_sqrt**0.5) if under_sqrt >= 0 else r
            inset = max(inset, corner_inset)
    x0, x1 = left + inset, right - inset
    return (x0, x1) if x0 < x1 else (None, None)


def lerp(a: int, b: int, t: float) -> int:
    return int(a + (b - a) * t)


def build_icon(size: int = SIZE) -> bytes:
    buf = bytearray(size * size * 4)  # transparent

    def fill_row(y: int, x0: int | None, x1: int | None, color: tuple[int, int, int, int]) -> None:
        if x0 is None:
            return
        x0, x1 = max(0, x0), min(size, x1)
        if x0 >= x1:
            return
        row_off = y * size * 4
        buf[row_off + x0 * 4 : row_off + x1 * 4] = bytes(color) * (x1 - x0)

    # Outer rounded tile, indigo -> violet vertical gradient.
    margin, tile_r = 60, 200
    top, bottom, left, right = margin, size - margin, margin, size - margin
    top_c, bottom_c = (99, 102, 241), (124, 58, 237)
    for y in range(top, bottom):
        x0, x1 = rounded_row_bounds(y, top, bottom, left, right, tile_r)
        t = (y - top) / (bottom - top)
        color = (
            lerp(top_c[0], bottom_c[0], t),
            lerp(top_c[1], bottom_c[1], t),
            lerp(top_c[2], bottom_c[2], t),
            255,
        )
        fill_row(y, x0, x1, color)

    # Inner white "card".
    c_margin, c_r, bottom_extra = 190, 70, 40
    c_top, c_bottom = c_margin, size - c_margin - bottom_extra
    c_left, c_right = c_margin, size - c_margin
    for y in range(c_top, c_bottom):
        x0, x1 = rounded_row_bounds(y, c_top, c_bottom, c_left, c_right, c_r)
        fill_row(y, x0, x1, (244, 244, 245, 255))

    # Headline bars inside the card.
    bar_color = (79, 70, 229, 255)
    bar_height = 46
    inner_left = c_left + 50
    inner_right = c_right - 50
    for rel_y, rel_w in ((0.22, 0.85), (0.42, 0.68), (0.62, 0.5)):
        y_start = int(c_top + rel_y * (c_bottom - c_top))
        width_px = int((inner_right - inner_left) * rel_w)
        for y in range(y_start, y_start + bar_height):
            fill_row(y, inner_left, inner_left + width_px, bar_color)

    # Accent "live" dot, top-right of the tile.
    cx, cy, cr = size - 260, 260, 90
    accent = (16, 185, 129, 255)
    for y in range(cy - cr, cy + cr):
        dy = y - cy
        under_sqrt = cr * cr - dy * dy
        if under_sqrt < 0:
            continue
        dx = int(under_sqrt**0.5)
        fill_row(y, cx - dx, cx + dx, accent)

    return bytes(buf)


def require_tool(name: str) -> None:
    if shutil.which(name) is None:
        sys.exit(f"Required tool '{name}' not found (this script needs macOS).")


def main() -> None:
    require_tool("sips")
    require_tool("iconutil")

    print("Drawing 1024x1024 icon…")
    write_png(PNG_PATH, SIZE, SIZE, build_icon(SIZE))

    if ICONSET_DIR.exists():
        shutil.rmtree(ICONSET_DIR)
    ICONSET_DIR.mkdir()

    print("Generating iconset sizes with sips…")
    for filename, px in ICONSET_SIZES:
        out = ICONSET_DIR / filename
        subprocess.run(
            ["sips", "-z", str(px), str(px), str(PNG_PATH), "--out", str(out)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    print("Packing .icns with iconutil…")
    subprocess.run(
        ["iconutil", "-c", "icns", str(ICONSET_DIR), "-o", str(ICNS_PATH)], check=True
    )

    print(f"Wrote {ICNS_PATH}")


if __name__ == "__main__":
    main()
