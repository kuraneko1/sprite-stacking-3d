"""Hierarchical 3D Voxel Bone-Rigging & Animation Toolkit for Sprite Stacking.

Provides:
  - Volume-preserving 3D squash & stretch compensation (`volume_preserving_sx`)
  - Smooth multi-segment curved bone chains (`sd_bone_chain`) for ears, limbs, tails, antennae
  - Head-bone-locked tilted face projection (`face_plane`) that resists top-down squash
  - Procedural cyclic gait & dash pose parameter generators (`stride_rig_params`)
  - Automatic bounding-box clipping detector (`assert_no_border_clipping`)
  - Multi-frame, multi-angle 3D animation QA sheet renderer (`render_animation_sheet`)
"""
import math
import os
import numpy as np
from PIL import Image

from sdf_primitives import sd_capsule, smin, project_tilted_face
from render_turntable import render_stack_angle


def pack_vol(occ: np.ndarray, colors: np.ndarray) -> np.ndarray:
    """Pack boolean occupancy (H, L, W) and RGB uint8 array (H, L, W, 3) into RGBA voxel volume."""
    vol = np.zeros((*occ.shape, 4), dtype=np.uint8)
    vol[occ, :3] = colors[occ]
    vol[occ, 3] = 255
    return vol


def volume_preserving_sx(stretch_y: float, squash_z: float, min_prod: float = 0.65) -> float:
    """Lateral X scale that preserves 3D body volume when stretching along Y and squashing along Z."""
    return 1.0 / math.sqrt(max(min_prod, stretch_y * squash_z))


def sd_bone_chain(
    X: np.ndarray,
    Y: np.ndarray,
    Z: np.ndarray,
    joints: list[tuple[float, float, float]],
    radii: list[float],
    smooth_k: float = 2.0,
    y_flatten: float = 1.0,
    y_pivot: float | None = None,
) -> np.ndarray:
    """Build an organic curved appendage (ear, tail, tentacle, curved arm) from joint waypoints.

    Args:
        joints: Ordered list of (x, y, z) 3D bone joint positions from root to tip.
        radii: Radius at each joint (same length as `joints`).
        smooth_k: Polynomial smin blend radius between adjacent bone segments.
        y_flatten: >1 flattens the appendage front-to-back (ideal for ears/fins).
        y_pivot: Y center for flattening (defaults to average joint Y).
    """
    if len(joints) < 2 or len(joints) != len(radii):
        raise ValueError("joints and radii must have the same length (>= 2)")

    if abs(y_flatten - 1.0) > 1e-4:
        yp = float(np.mean([j[1] for j in joints])) if y_pivot is None else y_pivot
        Ye = yp + (Y - yp) * y_flatten
    else:
        Ye = Y

    d = np.full_like(X, 999.0, dtype=np.float32)
    for i in range(len(joints) - 1):
        ax, ay, az = joints[i]
        bx, by, bz = joints[i + 1]
        seg = sd_capsule(X, Ye, Z, ax, ay, az, bx, by, bz, radii[i], radii[i + 1])
        d = seg if i == 0 else smin(d, seg, smooth_k)
    return d


def face_plane(
    occ_mask: np.ndarray,
    X: np.ndarray,
    Y: np.ndarray,
    Z: np.ndarray,
    ny: np.ndarray,
    cy: float,
    cz: float,
    y_min: float,
    tilt_deg: float = 14.0,
    ny_min: float = 0.20,
    fwd_min: float = -5.5,
):
    """Project 3D voxel coordinates onto a tilted facial plane locked to a moving head bone.

    Returns (front_mask, u, v):
      - front_mask: boolean mask of valid front-facing head surface voxels
      - u: horizontal face coordinate (+X)
      - v: vertical face coordinate tilted gently upward toward the top-down camera
    """
    u, v, fwd = project_tilted_face(X, Y, Z, cy=cy, cz=cz, tilt_deg=tilt_deg)
    front = occ_mask & (Y > y_min) & (ny > ny_min) & (fwd > fwd_min)
    return front, u, v


def stride_rig_params(frame_idx: int, total_frames: int = 6, style: str = "biped", dash_frame: int = 6) -> dict:
    """Generate expressive cyclic bone-rig parameters (0..total_frames-1) + aerodynamic dash pose.

    Styles:
      - 'biped'       : Energetic upright run/stride with arm/leg alternation, hop bob & squash/stretch
      - 'belly_slide' : Plush prone sliding stride with strong horizontal stretch, paddling arms, kicking feet & floppy ears
      - 'waddle'      : Cute side-to-side waddle with tail wag & gentle vertical bob
      - 'hover'       : Wing/fin flap hover with secondary vertical float
    """
    if frame_idx == dash_frame:
        if style == "belly_slide":
            sy, sz = 1.16, 0.90
            return dict(
                dash=True, phase=0.0, stretch_y=sy, squash_z=sz, sx=volume_preserving_sx(sy, sz),
                head_bob=0.8, head_lean=2.5, ear_lift=-2.2, ear_sweep=6.5, ear_spread=0.88,
                arm_l=4.2, arm_r=4.2, arm_lift=1.8, leg_l=1.8, leg_r=1.8, tail_bob=0.8, sway=0.0, bob=2.2,
            )
        sy, sz = 1.18, 0.92
        return dict(
            dash=True, phase=0.0, stretch_y=sy, squash_z=sz, sx=volume_preserving_sx(sy, sz),
            head_bob=1.0, head_lean=3.0, ear_lift=-2.0, ear_sweep=4.5, ear_spread=0.90,
            arm_l=5.0, arm_r=5.0, arm_lift=2.0, leg_l=-4.5, leg_r=-4.5, tail_bob=0.5, sway=0.0, bob=2.2,
        )

    ph = (frame_idx / float(total_frames)) * math.tau
    s = math.sin(ph)
    c = math.cos(ph)
    # Secondary spring-lag phase (~0.85 rad behind torso vertical bounce!)
    lag_s = math.sin(ph - 0.85)
    lag_c = math.cos(ph - 0.85)

    if style == "belly_slide":
        sy = 1.0 + 0.11 * s
        sz = 1.0 - 0.08 * s
        return dict(
            dash=False, phase=ph, stretch_y=sy, squash_z=sz, sx=volume_preserving_sx(sy, sz),
            head_bob=1.2 * c, head_lean=1.4 * s,
            ear_lift=2.6 * lag_s, ear_sweep=1.4 + 2.2 * s, ear_spread=1.0 + 0.06 * lag_c,
            arm_l=2.8 * math.sin(ph + 0.3), arm_r=2.8 * math.sin(ph + math.pi + 0.3),
            arm_lift=1.3 * c,
            leg_l=2.6 * math.sin(ph + math.pi), leg_r=2.6 * math.sin(ph),
            tail_bob=1.6 * lag_s, sway=1.5 * c, bob=max(0.0, c) * 1.4,
        )

    if style == "waddle":
        sy = 1.0 - 0.04 * math.cos(2 * ph)
        sz = 1.0 + 0.05 * math.cos(2 * ph)
        return dict(
            dash=False, phase=ph, stretch_y=sy, squash_z=sz, sx=volume_preserving_sx(sy, sz),
            head_bob=0.8 * math.sin(2 * ph), head_lean=0.4,
            ear_lift=1.2 * lag_s, ear_sweep=0.4, ear_spread=1.0,
            arm_l=2.4 * s, arm_r=-2.4 * s, arm_lift=0.6 * c,
            leg_l=-2.8 * s, leg_r=2.8 * s,
            tail_bob=0.8 * lag_s, sway=3.2 * c, bob=max(0.0, -math.cos(2 * ph)) * 1.2,
        )

    if style == "hover":
        sy = 1.0 + 0.04 * s
        sz = 1.0 - 0.05 * s
        return dict(
            dash=False, phase=ph, stretch_y=sy, squash_z=sz, sx=volume_preserving_sx(sy, sz),
            head_bob=1.4 * s, head_lean=0.5,
            ear_lift=3.0 * s, ear_sweep=0.8, ear_spread=1.0 + 0.1 * c,
            arm_l=4.0 * s, arm_r=4.0 * s, arm_lift=3.0 * s,
            leg_l=1.0 * lag_s, leg_r=-1.0 * lag_s,
            tail_bob=1.8 * lag_s, sway=1.2 * c, bob=2.2 + 2.0 * s,
        )

    # Default: 'biped' energetic stride
    sy = 1.0 - 0.045 * math.cos(2 * ph)
    sz = 1.0 + 0.055 * math.cos(2 * ph)
    return dict(
        dash=False, phase=ph, stretch_y=sy, squash_z=sz, sx=volume_preserving_sx(sy, sz),
        head_bob=1.0 * math.sin(2 * ph), head_lean=0.6,
        ear_lift=1.8 * lag_s, ear_sweep=0.5 + 0.6 * max(0.0, s), ear_spread=1.0,
        arm_l=3.8 * s, arm_r=-3.8 * s, arm_lift=0.8 * c,
        leg_l=-3.6 * s, leg_r=3.6 * s,
        tail_bob=1.4 * lag_s, sway=2.4 * c, bob=max(0.0, -math.cos(2 * ph)) * 1.6,
    )


def assert_no_border_clipping(vol: np.ndarray, label: str = "volume", check_bottom: bool = False) -> dict:
    """Verify no solid voxels touch outer grid walls (prevents stretched paws/ears clipping!).

    Returns a dict of edge occupancy counts and raises ValueError if any checked wall is clipped.
    """
    occ = vol[..., 3] > 0
    counts = {
        "x_min": int(occ[:, :, 0].sum()),
        "x_max": int(occ[:, :, -1].sum()),
        "y_min": int(occ[:, 0, :].sum()),
        "y_max": int(occ[:, -1, :].sum()),
        "z_max": int(occ[-1, :, :].sum()),
    }
    if check_bottom:
        counts["z_min"] = int(occ[0, :, :].sum())
    bad = {k: v for k, v in counts.items() if v > 0}
    if bad:
        raise ValueError(
            f"[{label}] Voxel clipping detected on grid walls {bad}! "
            f"Increase grid dimensions (W={vol.shape[2]}, L={vol.shape[1]}, H={vol.shape[0]}) or tighten extreme pose."
        )
    return counts


def render_animation_sheet(
    frames: list[np.ndarray],
    out_path: str,
    angles_deg: tuple[float, ...] = (22.0, 90.0, 180.0),
    squash: float = 0.72,
    spacing: float = 1.0,
    outline_color: tuple[int, int, int] | None = None,
    bg_rgb: tuple[int, int, int] = (235, 243, 252),
    scale: int = 3,
    pad: int = 6,
) -> Image.Image:
    """Render a grid of all animation frames (columns) across multiple 3D angles (rows) for visual QA."""
    rows = [
        [
            render_stack_angle(v, math.radians(ang), squash=squash, spacing=spacing, outline_color=outline_color, pad=4)
            for v in frames
        ]
        for ang in angles_deg
    ]
    cw = max(im.width for row in rows for im in row)
    ch = max(im.height for row in rows for im in row)
    ncols = len(frames)
    nrows = len(rows)

    sheet = Image.new("RGBA", (ncols * (cw + pad) + pad, nrows * (ch + pad) + pad), (*bg_rgb, 255))
    for ri, row in enumerate(rows):
        for ci, im in enumerate(row):
            x = pad + ci * (cw + pad) + (cw - im.width) // 2
            y = pad + ri * (ch + pad) + (ch - im.height) // 2
            sheet.alpha_composite(im, (x, y))

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    big = sheet.resize((sheet.width * scale, sheet.height * scale), Image.NEAREST)
    big.save(out_path)
    return big
