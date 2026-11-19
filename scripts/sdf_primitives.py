"""Reusable 3D SDF Voxel Sculpting Toolkit for Sprite Stacking.

Provides smooth organic blending (smin), 3D primitive signed distance functions,
gradient normals, 3-step cel shading, tilted facial projection helpers, and
horizontal slice-sheet export/import for Sprite Stacking engines.
"""
import math
import os
import numpy as np
from PIL import Image


def make_grid(w: int, l: int, h: int, scale: float = 1.0, y_offset: float = 0.0):
    """Create centered 3D coordinate grids (X, Y, Z) with Z=0 on ground and +Y facing forward."""
    zz, yy, xx = np.mgrid[0:h, 0:l, 0:w].astype(np.float32)
    X = (xx - (w - 1) / 2.0) / scale
    Y = (yy - (l - 1) / 2.0) / scale + y_offset
    Z = (zz + 0.5) / scale
    return X, Y, Z


def smin(a, b, k: float):
    """Polynomial smooth minimum for organic/plush blending."""
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1.0 - h) + a * h - k * h * (1.0 - h)


def smax(a, b, k: float):
    """Polynomial smooth maximum (smooth intersection)."""
    return -smin(-a, -b, k)


def sd_sphere(X, Y, Z, cx: float, cy: float, cz: float, r: float):
    return np.sqrt((X - cx) ** 2 + (Y - cy) ** 2 + (Z - cz) ** 2) - r


def sd_ellipsoid(X, Y, Z, cx: float, cy: float, cz: float, rx: float, ry: float, rz: float):
    px = (X - cx) / rx
    py = (Y - cy) / ry
    pz = (Z - cz) / rz
    k0 = np.sqrt(px * px + py * py + pz * pz) + 1e-8
    k1 = np.sqrt((px / rx) ** 2 + (py / ry) ** 2 + (pz / rz) ** 2) + 1e-8
    return k0 * (k0 - 1.0) / k1


def sd_capsule(X, Y, Z, ax: float, ay: float, az: float, bx: float, by: float, bz: float,
               r0: float, r1: float | None = None):
    """3D capsule (or tapered capsule when r1 != r0) from A to B."""
    pax, pay, paz = X - ax, Y - ay, Z - az
    bax, bay, baz = bx - ax, by - ay, bz - az
    ba_len2 = bax * bax + bay * bay + baz * baz + 1e-8
    h = np.clip((pax * bax + pay * bay + paz * baz) / ba_len2, 0.0, 1.0)
    dx = pax - bax * h
    dy = pay - bay * h
    dz = paz - baz * h
    r = r0 if r1 is None else (r0 + (r1 - r0) * h)
    return np.sqrt(dx * dx + dy * dy + dz * dz) - r


def sd_cylinder_z(X, Y, Z, cx: float, cy: float, z0: float, z1: float,
                  r0: float, r1: float | None = None):
    """Vertical (Z-axis) tapered cylinder/cone."""
    h_frac = np.clip((Z - z0) / max(z1 - z0, 1e-6), 0.0, 1.0)
    r = r0 if r1 is None else (r0 + (r1 - r0) * h_frac)
    d_rad = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2) - r
    d_z = np.maximum(z0 - Z, Z - z1)
    return np.maximum(d_rad, d_z)


def sd_torus_z(X, Y, Z, cx: float, cy: float, cz: float, major_r: float, minor_r: float,
               z_squash: float = 1.0):
    """Horizontal torus lying in XY plane around (cx, cy, cz)."""
    r_xy = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)
    return np.sqrt((r_xy - major_r) ** 2 + ((Z - cz) * z_squash) ** 2) - minor_r


def sd_box(X, Y, Z, cx: float, cy: float, cz: float, hx: float, hy: float, hz: float, round_r: float = 0.0):
    """Axis-aligned rounded 3D box centered at (cx, cy, cz) with half-extents (hx, hy, hz)."""
    qx = np.abs(X - cx) - (hx - round_r)
    qy = np.abs(Y - cy) - (hy - round_r)
    qz = np.abs(Z - cz) - (hz - round_r)
    outside = np.sqrt(np.maximum(qx, 0.0) ** 2 + np.maximum(qy, 0.0) ** 2 + np.maximum(qz, 0.0) ** 2)
    inside = np.minimum(np.maximum(qx, np.maximum(qy, qz)), 0.0)
    return outside + inside - round_r


def compute_normals(sdf: np.ndarray):
    """Central-difference unit surface normals from 3D SDF array (H, L, W)."""
    gz = np.gradient(sdf, axis=0)
    gy = np.gradient(sdf, axis=1)
    gx = np.gradient(sdf, axis=2)
    nlen = np.sqrt(gx * gx + gy * gy + gz * gz) + 1e-8
    return gx / nlen, gy / nlen, gz / nlen


def shade_cel_3step(base_rgb, hi_rgb, sh_rgb, deep_rgb, nx, ny, nz, ao=0.0,
                    light_dir=(-0.22, 0.35, 0.91)):
    """Crisp 3-step anime/cel lighting suited for top-down sprite stacking."""
    lx, ly, lz = light_dir
    ndotl = nx * lx + ny * ly + nz * lz - ao * 0.45
    out = np.empty((*ndotl.shape, 3), dtype=np.uint8)
    out[...] = np.asarray(base_rgb, dtype=np.uint8)
    out[ndotl > 0.52] = np.asarray(hi_rgb, dtype=np.uint8)
    out[ndotl < 0.06] = np.asarray(sh_rgb, dtype=np.uint8)
    out[ndotl < -0.38] = np.asarray(deep_rgb, dtype=np.uint8)
    return out


def project_tilted_face(X, Y, Z, cy: float, cz: float, tilt_deg: float = 14.0):
    """Project 3D coordinates onto a front-facing facial plane tilted slightly upward
    toward an angled top-down camera so eyes & smiles never squash vertically.
    Returns (u, v, fwd) where u=+X, v=up along tilted face, fwd=forward depth."""
    rad = math.radians(tilt_deg)
    dy = Y - cy
    dz = Z - cz
    u = X
    v = dz * math.cos(rad) - dy * math.sin(rad)
    fwd = dy * math.cos(rad) + dz * math.sin(rad)
    return u, v, fwd


def save_slice_sheet(vol: np.ndarray, path: str):
    """Save [H, L, W, 4] RGBA voxel volume as a single horizontal slice strip PNG (ground slice on left)."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    strip = np.concatenate(list(vol), axis=1)
    Image.fromarray(strip, "RGBA").save(path)
    return len(vol), vol.shape[2], vol.shape[1]


def load_slice_sheet(path: str, count: int) -> np.ndarray:
    """Load a horizontal slice strip PNG with `count` equal slices into [H, L, W, 4] RGBA numpy array."""
    im = np.array(Image.open(path).convert("RGBA"))
    h, total_w, _ = im.shape
    if total_w % count != 0:
        raise ValueError(f"Sheet width {total_w} is not divisible by slice count {count}")
    w = total_w // count
    return np.stack([im[:, z * w:(z + 1) * w] for z in range(count)], axis=0)
