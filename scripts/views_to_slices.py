"""Turn four orthographic flat views (top, side, front, back) into sprite stacking slices.

Adapted and extended from SpriteCook's views_to_slices.py
(https://www.spritecook.ai/blog/sprite-stacking-pixel-art) with:
- Outer flood-fill background removal (preserves interior white faces/snow)
- Crisp art-pixel downsampling from high-res AI generations
- Outer outline removal + optional internal dark crease removal
- Overhang-safe direct-above voxel check (occ[z+1]) preventing black holes under arches/brims
- Optional superellipse rounding (--round-carve)
- Multi-angle 3D turnaround diagnostic preview (--diag)
"""
import argparse
from collections import deque
import math
import os

import numpy as np
from PIL import Image

from render_turntable import render_stack_angle


def remove_outer_bg(img_rgba: np.ndarray, tol: int = 38) -> np.ndarray:
    """Flood-fill background from image borders based on similarity to border color."""
    h, w, _ = img_rgba.shape
    out = img_rgba.copy()
    rgb = img_rgba[..., :3].astype(np.int16)

    corners = np.array([
        rgb[0, 0], rgb[0, w - 1], rgb[h - 1, 0], rgb[h - 1, w - 1],
        rgb[2, 2], rgb[2, w - 3], rgb[h - 3, 2], rgb[h - 3, w - 3],
    ])
    bg = np.median(corners, axis=0)
    diff = np.abs(rgb - bg).max(axis=-1)
    is_bg_cand = (diff <= tol) | (img_rgba[..., 3] < 128)

    visited = np.zeros((h, w), dtype=bool)
    q = deque()
    for x in range(w):
        for y in (0, h - 1):
            if is_bg_cand[y, x] and not visited[y, x]:
                visited[y, x] = True
                q.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if is_bg_cand[y, x] and not visited[y, x]:
                visited[y, x] = True
                q.append((y, x))

    while q:
        y, x = q.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            yy, xx = y + dy, x + dx
            if 0 <= yy < h and 0 <= xx < w and not visited[yy, xx] and is_bg_cand[yy, xx]:
                visited[yy, xx] = True
                q.append((yy, xx))

    out[visited, 3] = 0
    if tol < 70:
        pad = np.pad(visited, 1, constant_values=True)
        adj = pad[:-2, 1:-1] | pad[2:, 1:-1] | pad[1:-1, :-2] | pad[1:-1, 2:]
        fringe = adj & (~visited) & (diff <= tol + 35)
        out[fringe, 3] = 0
    return out


def crop_largest_component(quad: np.ndarray, bridge: int = 4) -> np.ndarray:
    solid = quad[..., 3] >= 128
    if not solid.any():
        raise ValueError("Empty quadrant found — no foreground pixels!")
    grown = solid.copy()
    for _ in range(bridge):
        g = grown.copy()
        g[1:] |= grown[:-1]
        g[:-1] |= grown[1:]
        g[:, 1:] |= grown[:, :-1]
        g[:, :-1] |= grown[:, 1:]
        grown = g

    h, w = solid.shape
    seen = np.zeros((h, w), dtype=bool)
    comps = []
    for y0, x0 in zip(*np.nonzero(grown)):
        if seen[y0, x0]:
            continue
        stack = [(y0, x0)]
        seen[y0, x0] = True
        pts_y, pts_x = [], []
        while stack:
            y, x = stack.pop()
            pts_y.append(y)
            pts_x.append(x)
            for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= yy < h and 0 <= xx < w and grown[yy, xx] and not seen[yy, xx]:
                    seen[yy, xx] = True
                    stack.append((yy, xx))
        comps.append((len(pts_y), pts_y, pts_x))

    comps.sort(key=lambda c: c[0], reverse=True)
    main_area = comps[0][0]
    keep_mask = np.zeros((h, w), dtype=bool)
    for c in comps:
        if c[0] >= 0.15 * main_area:
            keep_mask[c[1], c[2]] = True

    final_solid = solid & keep_mask
    ys, xs = np.nonzero(final_solid)
    cropped = quad[ys.min():ys.max() + 1, xs.min():xs.max() + 1].copy()
    cropped_mask = final_solid[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    cropped[..., 3] = np.where(cropped_mask, 255, 0)
    return cropped


def extract_views_grid(sheet: np.ndarray, bg_tol: int = 38) -> list[np.ndarray]:
    """Split a 2x2 orthographic sheet into [top, side, front, back] by quadrant."""
    clean = remove_outer_bg(sheet, tol=bg_tol)
    h, w = clean.shape[:2]
    my, mx = h // 2, w // 2
    quads = [clean[:my, :mx], clean[:my, mx:], clean[my:, :mx], clean[my:, mx:]]
    return [crop_largest_component(q) for q in quads]


def downsample_crisp(v: np.ndarray, new_w: int, new_h: int, alpha_thresh: float = 0.45) -> np.ndarray:
    h, w = v.shape[:2]
    out = np.zeros((new_h, new_w, 4), dtype=np.uint8)
    for oy in range(new_h):
        y0 = int(round(oy * h / new_h))
        y1 = max(y0 + 1, int(round((oy + 1) * h / new_h)))
        for ox in range(new_w):
            x0 = int(round(ox * w / new_w))
            x1 = max(x0 + 1, int(round((ox + 1) * w / new_w)))
            cell = v[y0:y1, x0:x1]
            fg = cell[..., 3] >= 128
            if fg.mean() >= alpha_thresh:
                cy, cx = cell.shape[0] // 2, cell.shape[1] // 2
                c = cell[cy, cx, :3] if fg[cy, cx] else np.median(cell[fg][:, :3], axis=0).astype(np.uint8)
                out[oy, ox, :3] = c
                out[oy, ox, 3] = 255
    return out


def strip_outline(v: np.ndarray, dark: int = 95, passes: int = 1) -> np.ndarray:
    out = v.copy()
    for _ in range(passes):
        m = out[..., 3] > 0
        pad = np.pad(m, 1)
        edge = m & ~(pad[:-2, 1:-1] & pad[2:, 1:-1] & pad[1:-1, :-2] & pad[1:-1, 2:])
        lum = out[..., :3].astype(float).mean(axis=-1)
        line = edge & (lum < dark)
        if not line.any():
            break
        nxt = out.copy()
        for y, x in zip(*np.nonzero(line)):
            found = False
            for r in (1, 2):
                for dy in range(-r, r + 1):
                    for dx in range(-r, r + 1):
                        if dy == 0 and dx == 0:
                            continue
                        yy, xx = y + dy, x + dx
                        if 0 <= yy < m.shape[0] and 0 <= xx < m.shape[1] and m[yy, xx] and not line[yy, xx]:
                            if lum[yy, xx] >= dark or r == 2:
                                nxt[y, x] = out[yy, xx]
                                found = True
                                break
                    if found:
                        break
                if found:
                    break
        out = nxt
    return out


def strip_internal_dark_lines(v: np.ndarray, dark: int = 75, keep_white_adj: bool = False) -> np.ndarray:
    out = v.copy()
    m = out[..., 3] > 0
    is_white = m & (out[..., :3].min(axis=-1) > 195)
    protected = np.zeros_like(m)
    if keep_white_adj:
        wp = np.pad(is_white, 2)
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                protected |= wp[2 + dy:2 + dy + m.shape[0], 2 + dx:2 + dx + m.shape[1]]

    for _ in range(2):
        lum = out[..., :3].astype(float).mean(axis=-1)
        is_dark = m & (lum < dark) & (~protected)
        if not is_dark.any():
            break
        nxt = out.copy()
        changed = False
        for y, x in zip(*np.nonzero(is_dark)):
            bright_nbrs = []
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dy == 0 and dx == 0:
                        continue
                    yy, xx = y + dy, x + dx
                    if 0 <= yy < m.shape[0] and 0 <= xx < m.shape[1] and m[yy, xx] and lum[yy, xx] >= dark:
                        bright_nbrs.append(out[yy, xx, :3])
            if len(bright_nbrs) >= 2:
                nxt[y, x, :3] = np.median(bright_nbrs, axis=0).astype(np.uint8)
                changed = True
        out = nxt
        if not changed:
            break
    return out


def one_palette(views: list[np.ndarray], n: int) -> list[np.ndarray]:
    if n <= 0:
        return views
    px = np.concatenate([v[v[..., 3] > 0][:, :3] for v in views])
    px = np.unique(px // 6 * 6 + 3, axis=0).astype(np.uint8)
    pal_img = Image.fromarray(px.reshape(1, -1, 3), "RGB").quantize(n, method=Image.MEDIANCUT, dither=Image.NONE)
    pal = np.array(pal_img.getpalette()[:n * 3]).reshape(-1, 3)
    out = []
    for v in views:
        q = v.copy()
        diff = ((v[..., None, :3].astype(int) - pal[None, None]) ** 2).sum(-1)
        q[..., :3] = pal[diff.argmin(-1)]
        out.append(q)
    return out


def fit(v: np.ndarray, w: int, h: int) -> np.ndarray:
    return np.array(Image.fromarray(v).resize((w, h), Image.NEAREST))


def edge_colour(view: np.ndarray, row: int, i: int):
    xs = np.nonzero(view[row, :, 3])[0]
    return None if len(xs) == 0 else view[row, min(max(i, xs[0]), xs[-1]), :3]


def _contiguous_runs(mask_1d: np.ndarray) -> list[tuple[int, int]]:
    runs, in_run, start = [], False, 0
    for i, val in enumerate(mask_1d):
        if val and not in_run:
            start, in_run = i, True
        elif not val and in_run:
            runs.append((start, i - 1))
            in_run = False
    if in_run:
        runs.append((start, len(mask_1d) - 1))
    return runs


def carve(top: np.ndarray, side: np.ndarray, front: np.ndarray, back: np.ndarray,
          shade: float = 0.16, round_carve: float = 0.0) -> np.ndarray:
    """Overhang-safe visual-hull voxel carving from 4 orthographic views.
    Best suited for boxy props, vehicles, crates, buildings, and symmetric objects."""
    L, W = top.shape[:2]
    H = side.shape[0]
    occ = np.zeros((H, L, W), bool)
    yy_grid, xx_grid = np.mgrid[0:L, 0:W]

    for z in range(H):
        r = H - 1 - z
        along = side[r, :, 3] > 0
        across = (front[r, :, 3] > 0) | (back[r, :, 3] > 0)
        if not along.any() or not across.any():
            continue
        if round_carve > 0:
            mask = np.zeros((L, W), dtype=bool)
            for y0, y1 in _contiguous_runs(along):
                cy, ry = 0.5 * (y0 + y1), max(0.7, 0.5 * (y1 - y0) + 0.45)
                for x0, x1 in _contiguous_runs(across):
                    cx, rx = 0.5 * (x0 + x1), max(0.7, 0.5 * (x1 - x0) + 0.45)
                    mask |= (np.abs((xx_grid - cx) / rx) ** round_carve + np.abs((yy_grid - cy) / ry) ** round_carve) <= 1.05
            occ[z] = (top[..., 3] > 0) & mask
        else:
            occ[z] = (top[..., 3] > 0) & along[:, None] & across[None, :]

    vol = np.zeros((H, L, W, 4), np.uint8)
    for z in range(H - 1, -1, -1):
        r = H - 1 - z
        o = occ[z]
        if not o.any():
            continue
        above_direct = occ[z + 1] if (z + 1 < H) else np.zeros((L, W), bool)
        ix = np.arange(W)[None, :].repeat(L, 0)
        iy = np.arange(L)[:, None].repeat(W, 1)
        d = np.stack([
            ix - np.maximum.accumulate(np.where(~o, ix, -1), axis=1),
            np.minimum.accumulate(np.where(~o, ix, W)[:, ::-1], axis=1)[:, ::-1] - ix,
            iy - np.maximum.accumulate(np.where(~o, iy, -1), axis=0),
            np.minimum.accumulate(np.where(~o, iy, L)[::-1], axis=0)[::-1] - iy,
        ])
        face, depth = d.argmin(0), d.min(0)
        for y, x in zip(*np.nonzero(o)):
            if not above_direct[y, x]:
                c = top[y, x, :3]
            elif depth[y, x] > 2:
                c = vol[z + 1, y, x, :3]
            else:
                f = face[y, x]
                c = (edge_colour(side, r, y) if f < 2 else edge_colour(back, r, x) if f == 2
                     else edge_colour(front, r, x))
                if c is None:
                    c = top[y, x, :3]
            if above_direct[y, x] and depth[y, x] <= 2 and shade:
                c = (np.asarray(c, float) * (1 - shade * (1 - z / max(H - 1, 1)) - shade * 0.35)).clip(0, 255)
            vol[z, y, x] = (*np.asarray(c, np.uint8), 255)
    return vol


def main():
    p = argparse.ArgumentParser(description="Carve 4-view orthographic 2x2 sheet into sprite stacking slices.")
    p.add_argument("sheet", help="Input 2x2 orthographic model sheet (TL=top, TR=side, BL=front, BR=back)")
    p.add_argument("out", help="Output horizontal slice sheet PNG")
    p.add_argument("--target-size", type=int, default=40, help="Target longest dimension of TOP view in art pixels")
    p.add_argument("--side-nose", choices=["left", "right"], default="left")
    p.add_argument("--top-nose", choices=["down", "up"], default="down")
    p.add_argument("--bg-tol", type=int, default=38)
    p.add_argument("--outline-dark", type=int, default=95)
    p.add_argument("--outline-passes", type=int, default=1)
    p.add_argument("--strip-internal-dark", type=int, default=0)
    p.add_argument("--keep-white-adj", action="store_true")
    p.add_argument("--round-carve", type=float, default=0.0)
    p.add_argument("--colours", type=int, default=24)
    p.add_argument("--shade", type=float, default=0.18)
    p.add_argument("--diag", default="", help="Optional multi-angle 3D diagnostic preview PNG path")
    p.add_argument("--outline-rgb", default="30,30,45")
    a = p.parse_args()

    sheet = np.array(Image.open(a.sheet).convert("RGBA"))
    raw_views = extract_views_grid(sheet, bg_tol=a.bg_tol)
    scale_factor = a.target_size / max(raw_views[0].shape[0], raw_views[0].shape[1])

    ds_views = [
        downsample_crisp(v, max(4, int(round(v.shape[1] * scale_factor))), max(4, int(round(v.shape[0] * scale_factor))))
        for v in raw_views
    ]
    stripped = [strip_outline(v, dark=a.outline_dark, passes=a.outline_passes) for v in ds_views]
    if a.strip_internal_dark > 0:
        stripped = [strip_internal_dark_lines(v, dark=a.strip_internal_dark, keep_white_adj=a.keep_white_adj) for v in stripped]

    top, side, front, back = one_palette(stripped, a.colours)
    if a.side_nose == "left":
        side = side[:, ::-1]
    if a.top_nose == "up":
        top = top[::-1]

    L, W = top.shape[:2]
    H = max(4, round(side.shape[0] * L / side.shape[1]))
    vol = carve(top, fit(side, L, H), fit(front, W, H), fit(back, W, H), shade=a.shade, round_carve=a.round_carve)

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    Image.fromarray(np.concatenate(list(vol), axis=1), "RGBA").save(a.out)
    print(f"{len(vol)} slices of {vol.shape[2]} x {vol.shape[1]} px -> {a.out}")

    if a.diag:
        rgb = tuple(int(x) for x in a.outline_rgb.split(","))
        renders = [render_stack_angle(vol, math.radians(deg), squash=0.72, spacing=1.0, outline_color=rgb) for deg in range(0, 360, 45)]
        rw, rh = max(r.width for r in renders), max(r.height for r in renders)
        pad = 6
        out_im = Image.new("RGBA", (4 * (rw + pad) + pad, 2 * (rh + pad) + pad), (235, 243, 252, 255))
        for i, r in enumerate(renders):
            out_im.alpha_composite(r, (pad + (i % 4) * (rw + pad) + (rw - r.width) // 2, pad + (i // 4) * (rh + pad) + (rh - r.height) // 2))
        out_im.resize((out_im.width * 3, out_im.height * 3), Image.NEAREST).save(a.diag)
        print(f"Saved diagnostic preview -> {a.diag}")


if __name__ == "__main__":
    main()
