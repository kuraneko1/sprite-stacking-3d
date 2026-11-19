"""Standalone multi-angle 3D diagnostic renderer for Sprite Stacking slice sheets.

Renders the ACTUAL stacked 3D object (not flat slices) from multiple rotation angles,
camera squashes, and an optional spread-apart layer view so you can inspect face
clarity, overhangs, silhouettes, and outline cleanliness before wiring into a game.

Usage:
  python3 render_turntable.py bunny_slices.png --slices 44 --out preview.png \
      --angles 0,30,60,90,135,180 --squash 0.72 --outline 82,24,152 --scale 4 --spread
"""
import argparse
import math
import os
import numpy as np
from PIL import Image


def load_slice_sheet(path: str, count: int) -> np.ndarray:
    im = np.array(Image.open(path).convert("RGBA"))
    _, total_w, _ = im.shape
    if total_w % count != 0:
        raise ValueError(f"Sheet width {total_w} is not divisible by slice count {count}")
    w = total_w // count
    return np.stack([im[:, z * w:(z + 1) * w] for z in range(count)], axis=0)


def render_stack_angle(
    vol: np.ndarray,
    turn_rad: float,
    squash: float = 0.72,
    spacing: float = 1.0,
    outline_color: tuple[int, int, int] | None = None,
    pad: int = 8,
) -> Image.Image:
    """Render a 3D sprite stack at `turn_rad` using nearest-neighbor sampling and optional 1px post-outline."""
    H, L, W, _ = vol.shape
    diag = int(math.ceil(math.hypot(W, L))) + pad * 2
    canvas_w = diag
    canvas_h = int(math.ceil(diag * squash)) + int(math.ceil(H * spacing)) + pad * 2
    cx = canvas_w // 2
    cy = canvas_h - int(math.ceil(diag * squash * 0.5)) - pad

    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    deg = -math.degrees(turn_rad)

    for z in range(H):
        sl = Image.fromarray(vol[z], "RGBA")
        rot = sl.rotate(deg, resample=Image.NEAREST, expand=True)
        rw, rh = rot.size
        sq_h = max(1, int(round(rh * squash)))
        sq = rot.resize((rw, sq_h), Image.NEAREST)
        dx = cx - rw // 2
        dy = cy - sq_h // 2 - int(round(z * spacing))
        canvas.alpha_composite(sq, (dx, dy))

    if outline_color is not None:
        arr = np.array(canvas)
        m = arr[..., 3] > 0
        p = np.pad(m, 1)
        ring = (~m) & (p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:])
        arr[ring] = (*outline_color, 255)
        canvas = Image.fromarray(arr, "RGBA")
    return canvas


def main():
    p = argparse.ArgumentParser(description="Render multi-angle 3D turnaround sheet from a slice sheet PNG.")
    p.add_argument("sheet", help="Input horizontal slice sheet PNG")
    p.add_argument("--slices", type=int, required=True, help="Number of slices in the horizontal sheet")
    p.add_argument("--out", required=True, help="Output diagnostic PNG path")
    p.add_argument("--angles", default="0,30,60,90,135,180,225,270,315", help="Comma-separated angles in degrees")
    p.add_argument("--squash", type=float, default=0.72, help="Vertical squash factor (1.0 = straight down)")
    p.add_argument("--spacing", type=float, default=1.0, help="Vertical lift px per slice")
    p.add_argument("--outline", default="", help="Optional post-stack outline RGB e.g. '64,18,122'")
    p.add_argument("--bg", default="235,243,252", help="Background RGB")
    p.add_argument("--scale", type=int, default=4, help="Nearest-neighbor output magnification")
    p.add_argument("--spread", action="store_true", help="Include a 2.5x spread-apart layer view on a second row")
    a = p.parse_args()

    vol = load_slice_sheet(a.sheet, a.slices)
    outline_rgb = tuple(int(x) for x in a.outline.split(",")) if a.outline else None
    bg_rgb = tuple(int(x) for x in a.bg.split(","))
    angles = [float(x) for x in a.angles.split(",")]

    renders = [
        render_stack_angle(vol, math.radians(ang), squash=a.squash, spacing=a.spacing, outline_color=outline_rgb)
        for ang in angles
    ]

    pad = 8
    rw = max(r.width for r in renders)
    rh = max(r.height for r in renders)
    total_w = len(renders) * (rw + pad) + pad
    spread_img = None
    total_h = rh + pad * 2
    if a.spread:
        spread_img = render_stack_angle(vol, math.radians(35), squash=a.squash, spacing=2.5, outline_color=outline_rgb)
        total_w = max(total_w, spread_img.width + pad * 2)
        total_h += spread_img.height + pad

    sheet = Image.new("RGBA", (total_w, total_h), (*bg_rgb, 255))
    for i, r in enumerate(renders):
        x = pad + i * (rw + pad) + (rw - r.width) // 2
        y = pad + (rh - r.height) // 2
        sheet.alpha_composite(r, (x, y))

    if spread_img is not None:
        sheet.alpha_composite(spread_img, ((total_w - spread_img.width) // 2, rh + pad * 2))

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    big = sheet.resize((sheet.width * a.scale, sheet.height * a.scale), Image.NEAREST)
    big.save(a.out)
    print(f"Rendered {len(renders)} 3D angles ({a.slices} slices) -> {a.out} ({big.width}x{big.height})")


if __name__ == "__main__":
    main()
