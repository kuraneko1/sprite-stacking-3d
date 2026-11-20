"""100% Pixel-Art Asset, FX, Shadow & Bitmap Font Generator.

Eliminates smooth vector Canvas primitives (`ctx.arc`, `ctx.ellipse`, `ctx.stroke`,
`ctx.fillText`) and OS Unicode emojis by generating crisp, nearest-neighbor PNG assets:
  - ASCII-grid 16x16 (or WxH) pixel icons & sprites (`draw_pattern`)
  - 1px crisp dark pixel outlines (`add_pixel_outline`)
  - Checkerboard-dithered contact shadows (`make_dithered_shadow`)
  - Stepped pixel ground rings / auras (`make_stepped_ring`)
  - Multi-frame animated motion arcs/slashes (`make_slash_frames`)
  - Jagged vertical pixel lightning/beam frames (`make_jagged_bolt_frames`)
  - 2-frame pixel hit sparks (`make_spark_frames`)
  - Outlined 5x7 pixel bitmap font strips (`make_bitmap_font_strip`)
"""
import math
import os
import numpy as np
from PIL import Image


def save_rgba(arr: np.ndarray, path: str):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    Image.fromarray(arr, "RGBA").save(path)


def add_pixel_outline(arr: np.ndarray, col=(16, 12, 30, 255)) -> np.ndarray:
    """Add a crisp 1px 4-neighbor outline around any RGBA sprite."""
    out = arr.copy()
    m = arr[..., 3] > 0
    p = np.pad(m, 1)
    ring = (~m) & (p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:])
    out[ring] = col
    return out


def draw_pattern(rows: list[str], palette: dict[str, tuple[int, int, int, int]]) -> np.ndarray:
    """Convert an ASCII pixel-art grid into an RGBA numpy array. '.' or ' ' is transparent."""
    h = len(rows)
    w = len(rows[0])
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in palette:
                arr[y, x] = palette[ch]
    return arr


def make_dithered_shadow(
    rx: int,
    ry: int,
    rgb: tuple[int, int, int] = (28, 36, 58),
    core_alpha: int = 92,
    edge_alpha: int = 72,
) -> np.ndarray:
    """Generate a crisp pixel checkerboard-dithered contact shadow (replaces ctx.ellipse)."""
    w, h = rx * 2 + 2, ry * 2 + 2
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    cx, cy = w // 2, h // 2
    for y in range(h):
        for x in range(w):
            d = ((x - cx) / max(1, rx)) ** 2 + ((y - cy) / max(1, ry)) ** 2
            if d <= 0.72:
                arr[y, x] = (*rgb, core_alpha)
            elif d <= 1.0 and ((x + y) % 2 == 0):
                arr[y, x] = (*rgb, edge_alpha)
    return arr


def make_stepped_ring(
    size: int = 96,
    radius: float = 45.0,
    main_rgb=(56, 189, 248),
    hi_rgb=(186, 230, 253),
    fill_rgba=(56, 189, 248, 28),
) -> np.ndarray:
    """Generate a stepped-pixel ground ring with subtle stippled interior fill (replaces ctx.arc)."""
    arr = np.zeros((size, size, 4), dtype=np.uint8)
    cx = cy = size / 2.0 - 0.5
    for y in range(size):
        for x in range(size):
            d = math.hypot(x - cx, y - cy)
            if d <= radius - 2.5:
                if fill_rgba is not None and (x % 3 == 0) and (y % 3 == 0):
                    arr[y, x] = fill_rgba
            elif d <= radius - 0.8:
                arr[y, x] = (*main_rgb, 200)
            elif d <= radius + 0.8:
                arr[y, x] = (*hi_rgb, 240) if ((x ^ y) & 2) else (*main_rgb, 225)
    return arr


def make_slash_frames(
    width: int = 72,
    height: int = 36,
    core_rgb=(255, 241, 242),
    mid_rgb=(244, 63, 94),
    out_rgb=(136, 19, 55),
    count: int = 4,
) -> list[np.ndarray]:
    """Generate multi-frame expanding crescent pixel slash arcs facing +X."""
    frames = []
    cx, cy = width * 0.34, height * 0.5
    for f in range(count):
        arr = np.zeros((height, width, 4), dtype=np.uint8)
        outer_r = 20 + f * 6
        inner_r = 12 + f * 7.5
        for y in range(height):
            for x in range(width):
                dx = (x - cx) * 0.72
                dy = (y - cy) * 1.12
                d = math.hypot(dx, dy)
                ang = math.atan2(dy, dx)
                if abs(ang) < 1.25 - f * 0.08 and inner_r <= d <= outer_r:
                    t = (d - inner_r) / max(1.0, outer_r - inner_r)
                    if t > 0.70:
                        arr[y, x] = (*core_rgb, 255)
                    elif t > 0.25:
                        arr[y, x] = (*mid_rgb, 245)
                    elif (x + y) % 2 == 0:
                        arr[y, x] = (*out_rgb, 215)
        frames.append(add_pixel_outline(arr, (*out_rgb, 220)))
    return frames


def make_jagged_bolt_frames(
    width: int = 36,
    height: int = 128,
    core_rgb=(255, 255, 255),
    glow_rgb=(250, 204, 21),
    edge_rgb=(180, 83, 9),
    count: int = 3,
    seed: int = 100,
) -> list[np.ndarray]:
    """Generate animated vertical jagged pixel lightning/beam frames anchored at (W/2, H-6)."""
    rng = np.random.default_rng(seed)
    frames = []
    for f in range(count):
        arr = np.zeros((height, width, 4), dtype=np.uint8)
        x = width // 2
        for y in range(height):
            if y % 9 == 0:
                x = int(np.clip(width // 2 + rng.integers(-6, 7), 6, width - 7))
            thick = 2 if f == 0 else 1
            for dx in range(-thick - 2, thick + 3):
                xx = x + dx
                if 0 <= xx < width:
                    if abs(dx) <= thick - 1:
                        arr[y, xx] = (*core_rgb, 255)
                    elif abs(dx) <= thick + 1:
                        arr[y, xx] = (*glow_rgb, 240)
                    elif (y + dx) % 2 == 0:
                        arr[y, xx] = (*edge_rgb, 190)
        for y in range(height - 14, height):
            for x2 in range(width):
                d = math.hypot((x2 - width // 2) * 0.8, (y - (height - 6)) * 1.4)
                if 5 <= d <= 10:
                    arr[y, x2] = (*glow_rgb, 235)
                elif d < 5:
                    arr[y, x2] = (*core_rgb, 255)
        frames.append(arr)
    return frames


def make_spark_frames(core_rgb=(255, 255, 255), glow_rgb=(253, 224, 71)) -> list[np.ndarray]:
    """Generate 2-frame 12x12 pixel hit-spark burst sprites."""
    pal = {"W": (*core_rgb, 255), "Y": (*glow_rgb, 255)}
    patterns = [
        [
            ".....WW.....", ".....WW.....", "....WYYW....", "..W.WYYW.W..",
            "..WWYYYYWW..", "WWYYYYYYYYWW", "WWYYYYYYYYWW", "..WWYYYYWW..",
            "..W.WYYW.W..", "....WYYW....", ".....WW.....", ".....WW.....",
        ],
        [
            ".....YY.....", "............", "..Y......Y..", "....Y..Y....",
            "............", "Y..........Y", "Y..........Y", "............",
            "....Y..Y....", "..Y......Y..", "............", ".....YY.....",
        ],
    ]
    return [draw_pattern(rows, pal) for rows in patterns]


# 5x7 Pixel Bitmap Font Glyphs (zero browser fillText on canvas!)
DEFAULT_GLYPHS_5X7 = {
    "0": ["01110","10001","10011","10101","11001","10001","01110"],
    "1": ["00100","01100","00100","00100","00100","00100","01110"],
    "2": ["01110","10001","00001","00110","01000","10000","11111"],
    "3": ["11110","00001","00001","01110","00001","00001","11110"],
    "4": ["00010","00110","01010","10010","11111","00010","00010"],
    "5": ["11111","10000","11110","00001","00001","10001","01110"],
    "6": ["01110","10000","11110","10001","10001","10001","01110"],
    "7": ["11111","00001","00010","00100","01000","01000","01000"],
    "8": ["01110","10001","10001","01110","10001","10001","01110"],
    "9": ["01110","10001","10001","01111","00001","00010","01100"],
    "!": ["00100","00100","00100","00100","00100","00000","00100"],
    "+": ["00000","00100","00100","11111","00100","00100","00000"],
    "-": ["00000","00000","00000","11111","00000","00000","00000"],
    ":": ["00000","00100","00100","00000","00100","00100","00000"],
    ".": ["00000","00000","00000","00000","00000","00100","00100"],
    "%": ["11001","11010","00100","00100","01011","10011","00000"],
    "A": ["01110","10001","10001","11111","10001","10001","10001"],
    "B": ["11110","10001","10001","11110","10001","10001","11110"],
    "C": ["01110","10001","10000","10000","10000","10001","01110"],
    "D": ["11100","10010","10001","10001","10001","10010","11100"],
    "E": ["11111","10000","10000","11110","10000","10000","11111"],
    "F": ["11111","10000","10000","11110","10000","10000","10000"],
    "G": ["01110","10001","10000","10111","10001","10001","01110"],
    "H": ["10001","10001","10001","11111","10001","10001","10001"],
    "I": ["01110","00100","00100","00100","00100","00100","01110"],
    "K": ["10001","10010","10100","11000","10100","10010","10001"],
    "L": ["10000","10000","10000","10000","10000","10000","11111"],
    "M": ["10001","11011","10101","10101","10001","10001","10001"],
    "N": ["10001","11001","10101","10011","10001","10001","10001"],
    "O": ["01110","10001","10001","10001","10001","10001","01110"],
    "P": ["11110","10001","10001","11110","10000","10000","10000"],
    "R": ["11110","10001","10001","11110","10100","10010","10001"],
    "S": ["01111","10000","10000","01110","00001","00001","11110"],
    "T": ["11111","00100","00100","00100","00100","00100","00100"],
    "U": ["10001","10001","10001","10001","10001","10001","01110"],
    "V": ["10001","10001","10001","10001","10001","01010","00100"],
    "W": ["10001","10001","10001","10101","10101","11011","10001"],
    "X": ["10001","10001","01010","00100","01010","10001","10001"],
    "Y": ["10001","01010","00100","00100","00100","00100","00100"],
    "Z": ["11111","00001","00010","00100","01000","10000","11111"],
}


def make_bitmap_font_strip(
    chars: str = "0123456789!+-:.",
    fill_rgb=(255, 255, 255),
    outline_rgb=(16, 12, 30),
    glyph_map: dict | None = None,
) -> np.ndarray:
    """Build a crisp 7x9-per-glyph outlined horizontal bitmap font strip PNG."""
    gmap = glyph_map or DEFAULT_GLYPHS_5X7
    gw, gh = 7, 9
    strip = np.zeros((gh, gw * len(chars), 4), dtype=np.uint8)
    for idx, ch in enumerate(chars):
        cell = np.zeros((gh, gw, 4), dtype=np.uint8)
        rows = gmap.get(ch)
        if rows:
            for r_i, row in enumerate(rows):
                for c_i, bit in enumerate(row):
                    if bit == "1":
                        cell[r_i + 1, c_i + 1] = (*fill_rgb, 255)
            cell = add_pixel_outline(cell, (*outline_rgb, 255))
        strip[:, idx * gw:(idx + 1) * gw] = cell
    return strip
