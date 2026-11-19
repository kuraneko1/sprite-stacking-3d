"""True 3D SDF Voxel Sculptor for Sprite Stacking (Retro Pixel-Art Edition).

Creates slightly lower-resolution chunky pixel-art slices (~0.62x of HD)
with the same overhang-safe, cel-shaded 3D voxel quality and bold crisp facial features.
"""
import math
import os
import sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_SCRIPTS = os.path.abspath(os.path.join(HERE, "..", "..", "scripts"))
sys.path.insert(0, HERE)
sys.path.insert(0, REPO_SCRIPTS)

from sdf_primitives import (
    smin,
    sd_ellipsoid,
    sd_capsule,
    sd_cylinder_z,
    compute_normals,
    shade_cel_3step,
    save_slice_sheet,
)
from render_turntable import render_stack_angle


def sculpt_bunny_retro():
    """Chunky cozy retro pixel-art purple bunny (36 x 42 px x 28 slices)."""
    W, L, H = 36, 42, 28
    # Evaluate in canonical HD coordinate units (scaled by s = 1 / 0.635) so proportions match HD 1:1!
    scale = 0.635
    zz, yy, xx = np.mgrid[0:H, 0:L, 0:W].astype(np.float32)
    X = (xx - (W - 1) / 2.0) / scale
    Y = (yy - (L - 1) / 2.0) / scale
    Z = (zz + 0.5) / scale
    AX = np.abs(X)

    # Identical sculptural proportions to HD v2 bunny
    d_belly = sd_ellipsoid(X, Y, Z, 0.0, -1.5, 11.8, 14.4, 15.8, 11.8)
    d_neck = sd_capsule(X, Y, Z, 0.0, 2.2, 14.5, 0.0, 6.0, 24.5, 11.6, 10.2)
    d_head = sd_ellipsoid(X, Y, Z, 0.0, 6.6, 25.0, 10.8, 10.2, 10.4)
    d_torso = smin(d_belly, smin(d_neck, d_head, 3.2), 4.2)

    ear_pts = [
        (3.6, 5.2, 32.5, 4.5),
        (8.2, 5.0, 38.0, 5.3),
        (14.5, 4.7, 39.0, 5.9),
        (20.5, 4.4, 37.2, 5.7),
        (24.2, 4.2, 35.0, 4.7),
    ]
    Y_ear = 4.8 + (Y - 4.8) * 1.35
    d_ears = np.full_like(X, 999.0)
    for i in range(len(ear_pts) - 1):
        ax, ay, az, r0 = ear_pts[i]
        bx, by, bz, r1 = ear_pts[i + 1]
        d_ears = smin(d_ears, sd_capsule(AX, Y_ear, Z, ax, ay, az, bx, by, bz, r0, r1), 2.4)

    d_arm_main = sd_capsule(AX, Y, Z, 10.6, 4.5, 13.6, 7.0, 22.8, 14.0, 5.4, 5.8)
    d_paw = sd_ellipsoid(AX, Y, Z, 6.8, 24.2, 14.0, 5.6, 5.6, 4.7)
    d_thumb = sd_capsule(AX, Y, Z, 5.2, 18.8, 11.8, 3.0, 21.2, 12.2, 2.9, 2.6)
    d_arms = smin(smin(d_arm_main, d_paw, 2.0), d_thumb, 1.4)

    d_leg = sd_capsule(AX, Y, Z, 6.8, -13.8, 10.0, 7.4, -23.0, 11.2, 5.0, 4.8)
    d_foot = sd_ellipsoid(AX, Y, Z, 7.6, -24.8, 11.0, 4.7, 4.8, 4.4)
    d_legs = smin(d_leg, d_foot, 1.6)

    d_tail = sd_ellipsoid(X, Y, Z, 0.0, -16.2, 19.6, 4.2, 4.2, 4.0)

    d_body = smin(d_torso, d_ears, 2.0)
    d_body = smin(d_body, d_arms, 2.4)
    d_body = smin(d_body, d_legs, 2.2)
    d_body = smin(d_body, d_tail, 1.0)

    occ = (d_body <= 0.0) & (Z >= 0.5)
    nx, ny, nz = compute_normals(d_body)

    ao = np.zeros_like(X)
    ao += np.clip(1.0 - np.abs(d_torso - d_arms) / 3.8, 0.0, 1.0) * 0.55
    ao += np.clip(1.0 - np.abs(d_torso - d_ears) / 3.2, 0.0, 1.0) * 0.45
    ao += np.clip(1.0 - np.abs(d_torso - d_tail) / 2.5, 0.0, 1.0) * 0.70
    ao += np.clip(1.0 - np.abs(d_torso - d_legs) / 3.5, 0.0, 1.0) * 0.45
    ao += np.clip((4.5 - Z) / 4.5, 0.0, 1.0) * 0.35

    purple_hi = np.array([174, 98, 255], dtype=np.uint8)
    purple_base = np.array([154, 64, 245], dtype=np.uint8)
    purple_sh = np.array([130, 44, 224], dtype=np.uint8)
    purple_deep = np.array([105, 30, 194], dtype=np.uint8)

    colors = shade_cel_3step(purple_base, purple_hi, purple_sh, purple_deep, nx, ny, nz, ao=ao)
    tail_ring = (np.abs(d_tail) < 1.6) & (d_torso < 1.8) & (Y < -12.0)
    colors[tail_ring] = purple_deep

    # Bold retro-tuned white heart face mask (extra-clear at 28 slices!)
    face_cy = 14.5
    face_cz = 25.4
    tilt = math.radians(15.0)
    dy_f = Y - face_cy
    dz_f = Z - face_cz
    u = X
    v = dz_f * math.cos(tilt) - dy_f * math.sin(tilt)
    fwd = dy_f * math.cos(tilt) + dz_f * math.sin(tilt)

    # Deeper embed in canonical units (~3.6 units ≈ 2.3 retro voxels) so zero purple peeks through on diagonals!
    on_head_front = occ & (d_body >= -3.8) & (Y > 10.2) & (ny > 0.22) & (fwd > -5.5)

    lobe_l = ((u + 3.3) / 5.2) ** 2 + ((v - 1.7) / 3.9) ** 2 <= 1.0
    lobe_r = ((u - 3.3) / 5.2) ** 2 + ((v - 1.7) / 3.9) ** 2 <= 1.0
    chin = (u / 7.4) ** 2 + ((v + 0.9) / 5.6) ** 2 <= 1.0
    top_notch = (np.abs(u) < 1.6) & (v > 3.9)
    white_mask = on_head_front & (lobe_l | lobe_r | chin) & (~top_notch)

    colors[white_mask] = np.array([255, 255, 255], dtype=np.uint8)

    ink = np.array([15, 10, 24], dtype=np.uint8)
    # Slightly bolder dot eyes, clean separated nose, & crisp wide smile at 28-slice resolution!
    eye_l = ((u + 4.5) / 1.75) ** 2 + ((v - 2.35) / 1.65) ** 2 <= 1.0
    eye_r = ((u - 4.5) / 1.75) ** 2 + ((v - 2.35) / 1.65) ** 2 <= 1.0
    nose = (u / 1.75) ** 2 + ((v - 1.45) / 0.82) ** 2 <= 1.0
    smile_outer = (u / 5.3) ** 2 + ((v + 1.35) / 3.4) ** 2 <= 1.0
    smile_cut = v > (-1.55 - 0.032 * u * u)
    smile = smile_outer & (~smile_cut) & (np.abs(u) <= 5.25)

    colors[white_mask & (eye_l | eye_r | nose | smile)] = ink

    vol = np.zeros((H, L, W, 4), dtype=np.uint8)
    vol[occ, :3] = colors[occ]
    vol[occ, 3] = 255
    return vol


def sculpt_snowman_retro():
    """Chunky cozy retro pixel-art snowman (24 x 28 px x 36 slices)."""
    W, L, H = 24, 28, 36
    scale = 0.635
    zz, yy, xx = np.mgrid[0:H, 0:L, 0:W].astype(np.float32)
    X = (xx - (W - 1) / 2.0) / scale
    Y = (yy - (L - 1) / 2.0) / scale + 1.5
    Z = (zz + 0.5) / scale

    d_bot = sd_ellipsoid(X, Y, Z, 0.0, 0.0, 12.8, 13.8, 13.8, 12.8)
    d_head = sd_ellipsoid(X, Y, Z, 0.0, 0.0, 31.8, 10.4, 10.4, 10.2)
    d_snow = smin(d_bot, d_head, 1.8)

    r_xy = np.sqrt(X * X + Y * Y)
    d_scarf_ring = np.sqrt((r_xy - 9.8) ** 2 + ((Z - 22.8) * 0.92) ** 2) - 2.9
    d_scarf_tail = sd_capsule(X, Y, Z, 2.5, -9.8, 22.2, 4.5, -16.5, 13.5, 2.7, 2.3)
    d_scarf = smin(d_scarf_ring, d_scarf_tail, 1.0)

    d_carrot = sd_capsule(X, Y, Z, 0.0, 9.2, 31.6, 0.0, 19.6, 31.3, 2.65, 0.85)
    d_eye_l = sd_ellipsoid(X, Y, Z, -4.1, 9.0, 35.2, 2.0, 1.8, 2.1)
    d_eye_r = sd_ellipsoid(X, Y, Z, +4.1, 9.0, 35.2, 2.0, 1.8, 2.1)
    d_eyes = np.minimum(d_eye_l, d_eye_r)

    d_btn1 = sd_ellipsoid(X, Y, Z, 0.0, 13.2, 16.0, 1.75, 1.5, 1.75)
    d_btn2 = sd_ellipsoid(X, Y, Z, 0.0, 13.1, 10.0, 1.75, 1.5, 1.75)
    d_btns = np.minimum(d_btn1, d_btn2)

    d_brim = sd_cylinder_z(X, Y, Z, 0.0, 0.0, 40.2, 42.8, 12.2, 12.2)
    d_crown = sd_cylinder_z(X, Y, Z, 0.0, 0.0, 42.2, 54.5, 8.0, 8.7)
    d_hat = np.minimum(d_brim, d_crown)

    d_all = np.minimum.reduce([d_snow, d_scarf, d_carrot, d_eyes, d_btns, d_hat])
    occ = (d_all <= 0.0) & (Z >= 0.5)

    mat = np.zeros(occ.shape, dtype=np.uint8)
    mat[d_snow <= 0.0] = 1
    mat[d_hat <= 0.0] = 2
    mat[(d_crown <= 0.2) & (Z >= 42.6) & (Z <= 46.6)] = 3
    mat[d_scarf <= 0.0] = 4
    mat[d_carrot <= 0.0] = 5
    mat[(d_eyes <= 0.0) | (d_btns <= 0.0)] = 6

    nx, ny, nz = compute_normals(d_all)
    ao_snow = (
        np.clip(1.0 - np.abs(d_hat) / 3.5, 0.0, 1.0) * 0.45
        + np.clip(1.0 - np.abs(d_scarf) / 3.0, 0.0, 1.0) * 0.45
    )

    col_snow = shade_cel_3step(
        np.array([240, 248, 255], np.uint8),
        np.array([255, 255, 255], np.uint8),
        np.array([208, 229, 250], np.uint8),
        np.array([175, 206, 238], np.uint8),
        nx, ny, nz, ao=ao_snow,
    )
    col_hat = shade_cel_3step(
        np.array([48, 56, 82], np.uint8),
        np.array([70, 80, 112], np.uint8),
        np.array([34, 40, 62], np.uint8),
        np.array([22, 26, 44], np.uint8),
        nx, ny, nz,
    )
    col_red = shade_cel_3step(
        np.array([220, 42, 48], np.uint8),
        np.array([242, 72, 72], np.uint8),
        np.array([180, 28, 38], np.uint8),
        np.array([138, 18, 28], np.uint8),
        nx, ny, nz,
    )
    col_carrot = shade_cel_3step(
        np.array([249, 118, 28], np.uint8),
        np.array([255, 158, 66], np.uint8),
        np.array([218, 86, 18], np.uint8),
        np.array([180, 64, 12], np.uint8),
        nx, ny, nz,
    )

    vol = np.zeros((H, L, W, 4), dtype=np.uint8)
    for mid, col in ((1, col_snow), (2, col_hat), (3, col_red), (4, col_red), (5, col_carrot)):
        m = occ & (mat == mid)
        vol[m, :3] = col[m]
    vol[occ & (mat == 6), :3] = np.array([20, 22, 34], dtype=np.uint8)
    vol[occ, 3] = 255
    return vol


def sculpt_tree_retro():
    """Chunky cozy retro pixel-art snowy pine tree (34 x 34 px x 40 slices)."""
    W, L, H = 34, 34, 40
    scale = 0.63
    zz, yy, xx = np.mgrid[0:H, 0:L, 0:W].astype(np.float32)
    X = (xx - (W - 1) / 2.0) / scale
    Y = (yy - (L - 1) / 2.0) / scale
    Z = (zz + 0.5) / scale
    R = np.sqrt(X * X + Y * Y)
    ANG = np.arctan2(Y, X)

    d_trunk = sd_cylinder_z(X, Y, Z, 0.0, 0.0, 0.5, 17.0, 6.4, 4.8)
    tiers = [
        (13.5, 30.0, 22.8, 12.2, 8, 0.0, 0.19),
        (24.5, 42.0, 19.2, 8.8,  7, 0.45, 0.20),
        (36.0, 52.5, 14.8, 5.2,  6, 0.95, 0.20),
        (46.5, 62.5, 9.8,  0.4,  5, 0.25, 0.16),
    ]

    d_foliage = np.full_like(X, 999.0)
    is_snow_cap = np.zeros_like(X, dtype=bool)
    for idx, (zb, zt, rb, rt, n_petals, phase, amp) in enumerate(tiers):
        t = (Z - zb) / (zt - zb)
        t_clamped = np.clip(t, 0.0, 1.0)
        r_base = rb * (1.0 - t_clamped) + rt * t_clamped
        scallop = 1.0 + amp * (1.0 - 0.55 * t_clamped) * np.cos(n_petals * ANG + phase)
        r_tier = r_base * scallop
        d_rad = R - r_tier
        d_z = np.maximum(zb - Z, Z - zt)
        d_t = np.maximum(d_rad, d_z)
        d_foliage = np.minimum(d_foliage, d_t)

        if idx == 3:
            snow_h = zb + (zt - zb) * (0.34 + 0.12 * np.cos(n_petals * ANG + phase))
            is_snow_cap |= (d_t <= 0.0) & (Z >= snow_h)
        else:
            lobe_wave = np.cos(n_petals * ANG + phase)
            patch_mod = np.sin(3.0 * ANG + idx * 1.9)
            is_snow_cap |= (
                (d_t <= 0.0) & (d_rad > -4.8) & (t > 0.20) & (t < 0.62)
                & (lobe_wave > 0.12) & (patch_mod > -0.35)
            )

    d_all = np.minimum(d_trunk, d_foliage)
    occ = (d_all <= 0.0) & (Z >= 0.5)
    nx, ny, nz = compute_normals(d_all)
    ao = np.clip((14.0 - Z) / 14.0, 0.0, 1.0) * 0.45

    col_green = shade_cel_3step(
        np.array([22, 168, 128], np.uint8),
        np.array([56, 206, 158], np.uint8),
        np.array([15, 134, 108], np.uint8),
        np.array([12, 98, 86], np.uint8),
        nx, ny, nz, ao=ao,
    )
    col_snow = shade_cel_3step(
        np.array([226, 245, 255], np.uint8),
        np.array([250, 254, 255], np.uint8),
        np.array([184, 224, 248], np.uint8),
        np.array([152, 200, 234], np.uint8),
        nx, ny, nz,
    )
    col_wood = shade_cel_3step(
        np.array([144, 82, 46], np.uint8),
        np.array([168, 102, 60], np.uint8),
        np.array([112, 58, 30], np.uint8),
        np.array([84, 40, 20], np.uint8),
        nx, ny, nz, ao=0.25,
    )

    is_trunk = occ & (d_trunk <= d_foliage)
    is_snow = occ & (~is_trunk) & is_snow_cap
    is_leaf = occ & (~is_trunk) & (~is_snow)

    vol = np.zeros((H, L, W, 4), dtype=np.uint8)
    vol[is_leaf, :3] = col_green[is_leaf]
    vol[is_snow, :3] = col_snow[is_snow]
    vol[is_trunk, :3] = col_wood[is_trunk]
    vol[occ, 3] = 255
    return vol


def main():
    out_dir = os.path.join(HERE, "out_retro")
    os.makedirs(out_dir, exist_ok=True)

    bunny = sculpt_bunny_retro()
    snowman = sculpt_snowman_retro()
    tree = sculpt_tree_retro()

    save_slice_sheet(bunny, os.path.join(out_dir, "bunny_slices.png"))
    save_slice_sheet(snowman, os.path.join(out_dir, "snowman_slices.png"))
    save_slice_sheet(tree, os.path.join(out_dir, "tree_slices.png"))

    def preview(name, vol, rgb, angs, scale=5):
        ims = [render_stack_angle(vol, math.radians(a), squash=0.72, spacing=1.0, outline_color=rgb, pad=4) for a in angs]
        w = max(i.width for i in ims)
        h = max(i.height for i in ims)
        pad = 6
        c = Image.new("RGBA", (len(ims)*(w+pad)+pad, h+pad*2), (235, 243, 252, 255))
        for k, im in enumerate(ims):
            c.alpha_composite(im, (pad + k*(w+pad) + (w-im.width)//2, pad + (h-im.height)//2))
        out = os.path.join(out_dir, f"preview_3d_{name}.png")
        c.resize((c.width*scale, c.height*scale), Image.NEAREST).save(out)
        print("Preview ->", out)

    preview("bunny", bunny, (82, 24, 152), [0, 30, 60, 90, 135, 180], scale=5)
    preview("snowman", snowman, (24, 30, 52), [0, 35, 75, 135, 180, 270], scale=5)
    preview("tree", tree, (14, 56, 60), [0, 45, 90, 135], scale=4)


if __name__ == "__main__":
    main()
