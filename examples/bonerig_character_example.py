#!/usr/bin/env python3
"""Minimal Genre-Agnostic Example: 7-Frame Hierarchical 3D Voxel Bone Rig + QA Sheet.

Demonstrates how to use `sdf_primitives.py`, `voxel_rig.py`, and `pixel_atlas_kit.py`
to sculpt a living 7-frame animated 3D character (6 cyclic stride frames + 1 dash stretch),
verify zero border clipping, and render a multi-angle 3D motion QA contact sheet.

Usage:
  python3 examples/bonerig_character_example.py /tmp/bonerig_qa.png
"""
import math
import os
import sys
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from sdf_primitives import make_grid, smin, sd_ellipsoid, sd_capsule, compute_normals, shade_cel_3step
from voxel_rig import (
    pack_vol,
    sd_bone_chain,
    face_plane,
    stride_rig_params,
    assert_no_border_clipping,
    render_animation_sheet,
)
from pixel_atlas_kit import make_dithered_shadow, make_bitmap_font_strip


def sculpt_rigged_mascot(frame_idx: int) -> np.ndarray:
    """Example 7-frame plush mascot using hierarchical bones & secondary spring lag."""
    p = stride_rig_params(frame_idx, total_frames=6, style="belly_slide", dash_frame=6)
    W, L, H = 42, 52, 30
    X, Y, Z = make_grid(W, L, H, scale=0.68)

    sy, sz, sx = p["stretch_y"], p["squash_z"], p["sx"]

    # 1. Root bone: volume-preserving squash-and-stretch torso + head bone
    d_belly = sd_ellipsoid(X, Y, Z, 0.0, -1.5 * sy, 11.4 * sz, 14.0 * sx, 15.2 * sy, 11.2 * sz)
    head_y = (6.5 + p["head_lean"]) * sy
    head_z = 24.2 * sz + p["head_bob"]
    d_neck = sd_capsule(X, Y, Z, 0.0, 2.0 * sy, 14.0 * sz, 0.0, head_y, head_z, 11.0 * sx, 9.8 * sx)
    d_head = sd_ellipsoid(X, Y, Z, 0.0, head_y + 0.5, head_z + 0.4, 10.4 * sx, 9.8, 10.0 * sz)
    d_torso = smin(d_belly, smin(d_neck, d_head, 3.2), 4.0)

    # 2. Secondary spring-lag curved floppy ears built via sd_bone_chain
    def ear(side: float, lift: float):
        es, sw = p["ear_spread"], p["ear_sweep"]
        joints = [
            (side * 3.5 * sx,  head_y - 1.2,             head_z + 7.2),
            (side * 9.0 * es,  head_y - 1.6 - sw * 0.40, head_z + 12.2 + lift * 0.5),
            (side * 16.5 * es, head_y - 2.1 - sw * 0.85, head_z + 12.4 + lift * 0.9),
            (side * 22.5 * es, head_y - 2.6 - sw * 1.25, head_z + 9.6 + lift * 1.2),
        ]
        return sd_bone_chain(X, Y, Z, joints, [4.2, 5.0, 5.2, 4.0], smooth_k=2.2, y_flatten=1.3)

    d_ears = np.minimum(ear(-1.0, p["ear_lift"]), ear(+1.0, p["ear_lift"] * 0.85))

    # 3. Alternating paddling arms & rear kicking legs
    def arm(side: float, fwd: float):
        return sd_capsule(
            X, Y, Z,
            side * 10.2 * sx, 4.0 * sy, 13.0 * sz,
            side * 7.2 * sx, (21.5 + fwd) * sy, 13.5 * sz + p["arm_lift"],
            5.0, 4.8,
        )

    def leg(side: float, kick: float):
        return sd_capsule(
            X, Y, Z,
            side * 7.2 * sx, -10.0 * sy, 8.8 * sz,
            side * 8.6 * sx, -21.0 * sy, 9.8 * sz + kick,
            4.8, 4.2,
        )

    d_arms = np.minimum(arm(-1.0, p["arm_l"]), arm(+1.0, p["arm_r"]))
    d_legs = np.minimum(leg(-1.0, p["leg_l"]), leg(+1.0, p["leg_r"]))
    d_tail = sd_ellipsoid(X, Y, Z, 0.0, -16.2 * sy, 17.5 * sz + p["tail_bob"], 3.8, 3.8, 3.6)

    d_all = smin(smin(smin(d_torso, d_ears, 2.0), d_arms, 2.0), smin(d_legs, d_tail, 2.2), 2.0)
    occ = (d_all <= 0.0) & (Z >= 0.4)
    nx, ny, nz = compute_normals(d_all)

    # 4. Cel shading + head-locked tilted face projection
    colors = shade_cel_3step([154, 64, 245], [178, 106, 255], [128, 44, 220], [98, 28, 186], nx, ny, nz)
    front, u, v = face_plane(occ, X, Y, Z, ny, cy=head_y + 7.8, cz=head_z + 0.6, y_min=head_y + 3.4, tilt_deg=14.0)
    mask = front & ((u / 6.8) ** 2 + ((v + 0.3) / 5.2) ** 2 <= 1.0)
    eyes = mask & (((np.abs(u) - 3.6) / 1.55) ** 2 + ((v - 1.5) / 1.55) ** 2 <= 1.0)
    smile = mask & (np.abs(u) < 4.2) & (v < -0.8) & (v > -3.1 + 0.12 * u * u)
    colors[mask] = [255, 255, 255]
    colors[eyes | smile] = [18, 12, 28]

    return pack_vol(occ, colors)


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/bonerig_example_qa.png"
    frames = [sculpt_rigged_mascot(i) for i in range(7)]
    for i, vol in enumerate(frames):
        assert_no_border_clipping(vol, label=f"mascot_frame_{i}")

    img = render_animation_sheet(
        frames,
        out_path=out_path,
        angles_deg=(22.0, 90.0, 180.0),
        squash=0.72,
        outline_color=(82, 24, 152),
        scale=3,
    )
    # Smoke-test pixel_atlas_kit helpers as well
    sh = make_dithered_shadow(16, 10)
    fnt = make_bitmap_font_strip("0123456789!+-")
    print(f"PASS: 7 bone-rigged frames zero-clip verified -> {out_path} ({img.width}x{img.height})")
    print(f"PASS: pixel_atlas_kit shadow={sh.shape}, bitmap_font={fnt.shape}")


if __name__ == "__main__":
    main()
