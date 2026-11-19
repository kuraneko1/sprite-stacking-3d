"""True 3D SDF Voxel Sculptor for Sprite Stacking (HD Edition).

Replaces noisy 4-view visual-hull approximations with smooth, overhang-safe,
cel-shaded 3D voxel volumes matched to the uploaded purple bunny character
and Nano Banana winter park concept sheets — eliminating face squashing,
double eyes, hat/ear overhang bleeding, and moire artifacts.
"""
import math
import os
import numpy as np
from PIL import Image


def smin(a, b, k):
    """Polynomial smooth minimum for plush organic blending."""
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1.0 - h) + a * h - k * h * (1.0 - h)


def sd_ellipsoid(X, Y, Z, cx, cy, cz, rx, ry, rz):
    px = (X - cx) / rx
    py = (Y - cy) / ry
    pz = (Z - cz) / rz
    k0 = np.sqrt(px * px + py * py + pz * pz) + 1e-8
    k1 = np.sqrt((px / rx) ** 2 + (py / ry) ** 2 + (pz / rz) ** 2) + 1e-8
    return k0 * (k0 - 1.0) / k1


def sd_capsule(X, Y, Z, ax, ay, az, bx, by, bz, r0, r1=None):
    """3D capsule (or tapered capsule if r1 != r0) from point A to point B."""
    pax, pay, paz = X - ax, Y - ay, Z - az
    bax, bay, baz = bx - ax, by - ay, bz - az
    ba_len2 = bax * bax + bay * bay + baz * baz + 1e-8
    h = np.clip((pax * bax + pay * bay + paz * baz) / ba_len2, 0.0, 1.0)
    dx = pax - bax * h
    dy = pay - bay * h
    dz = paz - baz * h
    r = r0 if r1 is None else (r0 + (r1 - r0) * h)
    return np.sqrt(dx * dx + dy * dy + dz * dz) - r


def sd_cylinder_z(X, Y, Z, cx, cy, z0, z1, r0, r1=None):
    """Vertical (Z-axis) tapered cylinder/cone."""
    h_frac = np.clip((Z - z0) / max(z1 - z0, 1e-6), 0.0, 1.0)
    r = r0 if r1 is None else (r0 + (r1 - r0) * h_frac)
    d_rad = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2) - r
    d_z = np.maximum(z0 - Z, Z - z1)
    return np.maximum(d_rad, d_z)


def compute_normals(sdf):
    """Central-difference unit surface normals from 3D scalar field (H, L, W)."""
    gz = np.gradient(sdf, axis=0)
    gy = np.gradient(sdf, axis=1)
    gx = np.gradient(sdf, axis=2)
    nlen = np.sqrt(gx * gx + gy * gy + gz * gz) + 1e-8
    return gx / nlen, gy / nlen, gz / nlen


def shade_cel_3step(base_rgb, hi_rgb, sh_rgb, deep_rgb, nx, ny, nz, ao=0.0):
    """Crisp 3-step anime/cel lighting from upper-front-left key light."""
    # Key light from top-front-slight-left so front/top pop brightly from all game angles
    lx, ly, lz = -0.22, 0.35, 0.91
    ndotl = nx * lx + ny * ly + nz * lz - ao * 0.45
    out = np.empty((*ndotl.shape, 3), dtype=np.uint8)
    out[...] = base_rgb
    out[ndotl > 0.52] = hi_rgb
    out[ndotl < 0.06] = sh_rgb
    out[ndotl < -0.38] = deep_rgb
    return out


# =============================================================================
# 1. PURPLE BELLY-SLIDING BUNNY (Faithful to uploaded character right-side pose!)
# =============================================================================
def sculpt_bunny_hd():
    W, L, H = 58, 66, 44
    # Coordinate grid: X centered at 0, Y centered at 0 (+Y = forward/nose), Z from 0..H-1 (0 = ground)
    zz, yy, xx = np.mgrid[0:H, 0:L, 0:W].astype(np.float32)
    X = xx - (W - 1) / 2.0
    Y = yy - (L - 1) / 2.0
    Z = zz + 0.5
    AX = np.abs(X)

    # --- Plump round belly (resting on ground z=0, cute seal/bowl curve) ---
    d_belly = sd_ellipsoid(X, Y, Z, 0.0, -1.5, 11.8, 14.4, 15.8, 11.8)

    # --- Raised smooth chest/neck + rounded head ---
    d_neck = sd_capsule(X, Y, Z, 0.0, 2.2, 14.5, 0.0, 6.0, 24.5, 11.6, 10.2)
    d_head = sd_ellipsoid(X, Y, Z, 0.0, 6.6, 25.0, 10.8, 10.2, 10.4)
    d_torso = smin(d_belly, smin(d_neck, d_head, 3.2), 4.2)

    # --- Two big chunky plush floppy outward-curving bunny ears (symmetrical in |X|) ---
    ear_pts = [
        (3.6, 5.2, 32.5, 4.4),
        (8.2, 5.0, 38.0, 5.2),
        (14.5, 4.7, 39.0, 5.8),
        (20.5, 4.4, 37.2, 5.6),
        (24.2, 4.2, 35.0, 4.6),
    ]
    Y_ear = 4.8 + (Y - 4.8) * 1.38
    d_ears = np.full_like(X, 999.0)
    for i in range(len(ear_pts) - 1):
        ax, ay, az, r0 = ear_pts[i]
        bx, by, bz, r1 = ear_pts[i + 1]
        seg = sd_capsule(AX, Y_ear, Z, ax, ay, az, bx, by, bz, r0, r1)
        d_ears = smin(d_ears, seg, 2.4)

    # --- Two chunky mitten arms stretched forward together at belly/chest height ---
    d_arm_main = sd_capsule(AX, Y, Z, 10.6, 4.5, 13.6, 7.0, 22.8, 14.0, 5.4, 5.8)
    d_paw = sd_ellipsoid(AX, Y, Z, 6.8, 24.2, 14.0, 5.6, 5.6, 4.7)
    d_thumb = sd_capsule(AX, Y, Z, 5.2, 18.8, 11.8, 3.0, 21.2, 12.2, 2.8, 2.5)
    d_arms = smin(smin(d_arm_main, d_paw, 2.0), d_thumb, 1.4)

    # --- Two stubby round legs kicked straight BACK behind the belly ---
    d_leg = sd_capsule(AX, Y, Z, 6.8, -13.8, 10.0, 7.4, -23.0, 11.2, 5.0, 4.8)
    d_foot = sd_ellipsoid(AX, Y, Z, 7.6, -24.8, 11.0, 4.7, 4.8, 4.4)
    d_legs = smin(d_leg, d_foot, 1.6)

    # --- Cute small round pom-pom bunny tail on the upper rump ---
    d_tail = sd_ellipsoid(X, Y, Z, 0.0, -16.2, 19.6, 4.0, 4.0, 3.8)

    # Combine all body parts cleanly with plush smooth-blending
    d_body = smin(d_torso, d_ears, 2.0)
    d_body = smin(d_body, d_arms, 2.4)
    d_body = smin(d_body, d_legs, 2.2)
    d_body = smin(d_body, d_tail, 1.0)

    # Flat contact floor clip at z >= 0.4 so belly sits solidly grounded
    occ = (d_body <= 0.0) & (Z >= 0.4)

    # Compute smooth 3D normals & subtle crease AO (where parts meet)
    nx, ny, nz = compute_normals(d_body)
    # Crease AO where arms/ears/tail/legs join torso
    ao = np.zeros_like(X)
    ao += np.clip(1.0 - np.abs(d_torso - d_arms) / 3.5, 0.0, 1.0) * 0.55
    ao += np.clip(1.0 - np.abs(d_torso - d_ears) / 3.0, 0.0, 1.0) * 0.45
    ao += np.clip(1.0 - np.abs(d_torso - d_tail) / 2.2, 0.0, 1.0) * 0.70
    ao += np.clip(1.0 - np.abs(d_torso - d_legs) / 3.2, 0.0, 1.0) * 0.45
    # Slight ground contact bounce shadow under lowest belly
    ao += np.clip((4.0 - Z) / 4.0, 0.0, 1.0) * 0.35

    # Exact character palette sampled from uploaded reference image!
    purple_hi = np.array([174, 98, 255], dtype=np.uint8)
    purple_base = np.array([154, 64, 245], dtype=np.uint8)
    purple_sh = np.array([130, 44, 224], dtype=np.uint8)
    purple_deep = np.array([105, 30, 194], dtype=np.uint8)

    colors = shade_cel_3step(purple_base, purple_hi, purple_sh, purple_deep, nx, ny, nz, ao=ao)

    # Subtle cute dark-purple crease highlight around the pom-pom tail base so tail pops cleanly!
    tail_ring = (np.abs(d_tail) < 1.3) & (d_torso < 1.5) & (Y < -12.0)
    colors[tail_ring] = purple_deep

    # =========================================================================
    # ULTRA-CRISP WHITE HEART FACE MASK + BLACK EYES + NOSE + WIDE SMILE
    # Projected onto the front face dome with a gentle ~14° upward camera tilt
    # AND embedded 2.8 voxels deep so diagonal rotations NEVER drop pixels!
    # =========================================================================
    face_cy = 14.5
    face_cz = 25.4
    tilt = math.radians(14.0)  # Tilted gently upward toward the top-down camera!
    # Local face coordinates: u = right (+X), v = up along tilted face plane, fwd = outward depth
    dy_f = Y - face_cy
    dz_f = Z - face_cz
    u = X
    v = dz_f * math.cos(tilt) - dy_f * math.sin(tilt)
    fwd = dy_f * math.cos(tilt) + dz_f * math.sin(tilt)

    # Only project on the front surface shell of the head (depth <= 2.8 voxels from surface, facing +Y)
    on_head_front = occ & (d_body >= -2.9) & (Y > 10.5) & (ny > 0.25) & (fwd > -5.5)

    # Cute wide heart/bean white mask (~12% bolder so it shines brightly at gameplay zoom!)
    lobe_l = ((u + 3.1) / 4.9) ** 2 + ((v - 1.6) / 3.6) ** 2 <= 1.0
    lobe_r = ((u - 3.1) / 4.9) ** 2 + ((v - 1.6) / 3.6) ** 2 <= 1.0
    chin = (u / 7.0) ** 2 + ((v + 0.8) / 5.3) ** 2 <= 1.0
    top_notch = (np.abs(u) < 1.7) & (v > 3.5)
    white_mask = on_head_front & (lobe_l | lobe_r | chin) & (~top_notch)

    lobe_l_out = ((u + 3.1) / 5.7) ** 2 + ((v - 1.6) / 4.3) ** 2 <= 1.0
    lobe_r_out = ((u - 3.1) / 5.7) ** 2 + ((v - 1.6) / 4.3) ** 2 <= 1.0
    chin_out = (u / 7.9) ** 2 + ((v + 0.8) / 6.0) ** 2 <= 1.0
    face_rim = on_head_front & (lobe_l_out | lobe_r_out | chin_out) & (~white_mask)
    colors[face_rim] = purple_deep

    colors[white_mask] = np.array([255, 255, 255], dtype=np.uint8)

    ink = np.array([15, 10, 24], dtype=np.uint8)
    eye_l = ((u + 4.3) / 1.6) ** 2 + ((v - 1.9) / 1.6) ** 2 <= 1.0
    eye_r = ((u - 4.3) / 1.6) ** 2 + ((v - 1.9) / 1.6) ** 2 <= 1.0
    nose = (u / 1.8) ** 2 + ((v - 0.9) / 1.0) ** 2 <= 1.0
    smile_outer = (u / 4.8) ** 2 + ((v + 1.0) / 3.4) ** 2 <= 1.0
    smile_cut = v > (-1.15 - 0.038 * u * u)
    smile = smile_outer & (~smile_cut) & (np.abs(u) <= 4.85)

    features = white_mask & (eye_l | eye_r | nose | smile)
    colors[features] = ink

    vol = np.zeros((H, L, W, 4), dtype=np.uint8)
    vol[occ, :3] = colors[occ]
    vol[occ, 3] = 255
    return vol


# =============================================================================
# 2. CHEERFUL 3D SNOWMAN (Smooth spheres, protruding carrot, clean scarf & hat!)
# =============================================================================
def sculpt_snowman_hd():
    W, L, H = 38, 44, 56
    zz, yy, xx = np.mgrid[0:H, 0:L, 0:W].astype(np.float32)
    X = xx - (W - 1) / 2.0
    Y = yy - (L - 1) / 2.0 + 1.5  # Slight back shift so forward carrot fits comfortably inside L!
    Z = zz + 0.5

    # --- Two smooth round snowballs ---
    d_bot = sd_ellipsoid(X, Y, Z, 0.0, 0.0, 12.8, 13.8, 13.8, 12.8)
    d_head = sd_ellipsoid(X, Y, Z, 0.0, 0.0, 31.8, 10.4, 10.4, 10.2)
    d_snow = smin(d_bot, d_head, 1.8)

    # --- Cozy 3D Red Scarf wrapped cleanly around neck + fluttering scarf tail in back ---
    r_xy = np.sqrt(X * X + Y * Y)
    d_scarf_ring = np.sqrt((r_xy - 9.8) ** 2 + ((Z - 22.8) * 0.95) ** 2) - 2.7
    # Cute trailing scarf tail draping down the back-right!
    d_scarf_tail = sd_capsule(X, Y, Z, 2.5, -9.8, 22.2, 4.5, -16.5, 13.5, 2.5, 2.1)
    # Flatten scarf tail slightly like fabric
    d_scarf = smin(d_scarf_ring, d_scarf_tail, 1.0)

    # --- 3D Tapered Coral-Orange Carrot Nose pointing straight forward (+Y) ---
    d_carrot = sd_capsule(X, Y, Z, 0.0, 9.2, 31.6, 0.0, 19.6, 31.3, 2.45, 0.55)

    # --- Two Glossy Round Coal Eyes (ONLY on front of head — NEVER doubled on cheeks!) ---
    d_eye_l = sd_ellipsoid(X, Y, Z, -4.0, 9.0, 35.0, 1.75, 1.6, 1.85)
    d_eye_r = sd_ellipsoid(X, Y, Z, +4.0, 9.0, 35.0, 1.75, 1.6, 1.85)
    d_eyes = np.minimum(d_eye_l, d_eye_r)

    # --- Two cute little coal buttons on front of belly ---
    d_btn1 = sd_ellipsoid(X, Y, Z, 0.0, 13.2, 16.0, 1.5, 1.3, 1.5)
    d_btn2 = sd_ellipsoid(X, Y, Z, 0.0, 13.1, 10.2, 1.5, 1.3, 1.5)
    d_btns = np.minimum(d_btn1, d_btn2)

    # --- Crisp Cylindrical Dark-Navy Top Hat with Red Ribbon Band ---
    d_brim = sd_cylinder_z(X, Y, Z, 0.0, 0.0, 40.5, 42.6, 12.2, 12.2)
    d_crown = sd_cylinder_z(X, Y, Z, 0.0, 0.0, 42.2, 54.0, 8.0, 8.7)
    d_hat = np.minimum(d_brim, d_crown)

    # Combined occupancy (ground flat at Z >= 0.4)
    d_all = np.minimum.reduce([d_snow, d_scarf, d_carrot, d_eyes, d_btns, d_hat])
    occ = (d_all <= 0.0) & (Z >= 0.4)

    # Assign exact material ID cleanly (zero color bleeding between hat, scarf, face, carrot!)
    # Priority order: eyes/buttons > carrot > scarf > hat > snow
    mat = np.zeros(occ.shape, dtype=np.uint8)
    mat[d_snow <= 0.0] = 1        # Snow
    mat[d_hat <= 0.0] = 2         # Dark hat
    mat[(d_crown <= 0.15) & (Z >= 42.6) & (Z <= 46.2)] = 3  # Red hatband!
    mat[d_scarf <= 0.0] = 4       # Red scarf
    mat[d_carrot <= 0.0] = 5      # Orange carrot
    mat[(d_eyes <= 0.0) | (d_btns <= 0.0)] = 6  # Coal eyes & buttons

    # Per-part clean normals so each shape gets crisp smooth lighting!
    nx, ny, nz = compute_normals(d_all)

    # Snow shading (bright crisp snow + soft icy blue lower shadow + gentle AO under hat & scarf)
    ao_snow = np.zeros_like(X)
    ao_snow += np.clip(1.0 - np.abs(d_hat) / 3.5, 0.0, 1.0) * 0.45
    ao_snow += np.clip(1.0 - np.abs(d_scarf) / 3.0, 0.0, 1.0) * 0.45
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
    m1 = occ & (mat == 1)
    m2 = occ & (mat == 2)
    m3 = occ & ((mat == 3) | (mat == 4))
    m5 = occ & (mat == 5)
    m6 = occ & (mat == 6)

    vol[m1, :3] = col_snow[m1]
    vol[m2, :3] = col_hat[m2]
    vol[m3, :3] = col_red[m3]
    vol[m5, :3] = col_carrot[m5]
    vol[m6, :3] = np.array([20, 22, 34], dtype=np.uint8)

    # Tiny cute white eye specular highlight on upper-left of each coal eye!
    glint_l = m6 & (np.abs(X + 4.5) < 0.9) & (np.abs(Z - 35.8) < 0.9) & (Y > 9.3)
    glint_r = m6 & (np.abs(X - 3.5) < 0.9) & (np.abs(Z - 35.8) < 0.9) & (Y > 9.3)
    vol[glint_l | glint_r, :3] = np.array([255, 255, 255], dtype=np.uint8)

    vol[occ, 3] = 255
    return vol


# =============================================================================
# 3. SNOWY PINE TREE (Lush scalloped 3D tiers + puffy snow caps, zero moire!)
# =============================================================================
def sculpt_tree_hd():
    W, L, H = 54, 54, 64
    zz, yy, xx = np.mgrid[0:H, 0:L, 0:W].astype(np.float32)
    X = xx - (W - 1) / 2.0
    Y = yy - (L - 1) / 2.0
    Z = zz + 0.5
    R = np.sqrt(X * X + Y * Y)
    ANG = np.arctan2(Y, X)

    # Warm brown trunk clearly peeking underneath the lowest snow-dusted boughs!
    d_trunk = sd_cylinder_z(X, Y, Z, 0.0, 0.0, 0.4, 17.0, 6.4, 4.8)

    # 4 scalloped conical evergreen bough tiers (with playful phase offsets between tiers!)
    tiers = [
        # (z_bot, z_top, r_bot, r_top, petals, phase, wave_amp)
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

        # Organic puffy snow patches sitting cleanly on upper tips of select branches (more lush green showing!)
        if idx == 3:
            snow_h = zb + (zt - zb) * (0.34 + 0.12 * np.cos(n_petals * ANG + phase))
            is_snow_cap |= (d_t <= 0.0) & (Z >= snow_h)
        else:
            lobe_wave = np.cos(n_petals * ANG + phase)
            patch_mod = np.sin(3.0 * ANG + idx * 1.9)
            snow_band = (
                (d_t <= 0.0)
                & (d_rad > -4.5)
                & (t > 0.20)
                & (t < 0.62)
                & (lobe_wave > 0.12)
                & (patch_mod > -0.35)
            )
            is_snow_cap |= snow_band

    d_all = np.minimum(d_trunk, d_foliage)
    occ = (d_all <= 0.0) & (Z >= 0.4)
    nx, ny, nz = compute_normals(d_all)

    # Soft AO under each overhanging bough tier
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


def save_slice_sheet(vol, path):
    Image.fromarray(np.concatenate(list(vol), axis=1), "RGBA").save(path)
    print(f"Saved {len(vol)} slices of {vol.shape[2]} x {vol.shape[1]} px -> {path}")


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    repo_scripts = os.path.abspath(os.path.join(here, "..", "..", "scripts"))
    out_dir = os.path.join(here, "out_hd")
    os.makedirs(out_dir, exist_ok=True)

    bunny = sculpt_bunny_hd()
    snowman = sculpt_snowman_hd()
    tree = sculpt_tree_hd()

    save_slice_sheet(bunny, os.path.join(out_dir, "bunny_slices_hd.png"))
    save_slice_sheet(snowman, os.path.join(out_dir, "snowman_slices_hd.png"))
    save_slice_sheet(tree, os.path.join(out_dir, "tree_slices_hd.png"))

    import sys
    sys.path.insert(0, repo_scripts)
    from render_turntable import render_stack_angle

    def make_closeup(name, vol, rgb, angles_deg, scale=4):
        ims = [
            render_stack_angle(vol, math.radians(a), squash=0.72, spacing=1.0, outline_color=rgb, pad=4)
            for a in angles_deg
        ]
        w = max(i.width for i in ims)
        h = max(i.height for i in ims)
        pad = 6
        c = Image.new("RGBA", (len(ims) * (w + pad) + pad, h + pad * 2), (235, 243, 252, 255))
        for k, im in enumerate(ims):
            c.alpha_composite(im, (pad + k * (w + pad) + (w - im.width) // 2, pad + (h - im.height) // 2))
        out = os.path.join(out_dir, f"preview_3d_{name}.png")
        c.resize((c.width * scale, c.height * scale), Image.NEAREST).save(out)
        print(f"Preview -> {out}")

    make_closeup("bunny", bunny, (82, 24, 152), [0, 30, 60, 90, 135, 180], scale=4)
    make_closeup("snowman", snowman, (24, 30, 52), [0, 35, 75, 135, 180, 270], scale=4)
    make_closeup("tree", tree, (14, 56, 60), [0, 45, 90, 135], scale=3)


if __name__ == "__main__":
    main()
