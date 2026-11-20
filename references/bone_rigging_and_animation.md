# 3D Voxel Bone Rigging & Living Squash-and-Stretch Animation

This reference captures the exact 2-layer animation architecture that makes pseudo-3D sprite-stacked characters feel rubbery, weightful, and alive — without ever breaking pixel crispness or 60 FPS performance:

1. **Baked 3D SDF Bone Rig (7 frames per hero / 2 frames per NPC)**: True 3D voxel pose deformation in Python (`scripts/voxel_rig.py` + `scripts/sdf_primitives.py`).
2. **Runtime Spring-Damper Squash & Stretch (JS Canvas)**: Elastic 2nd-order spring impulses anchored at the character's ground pivot `(cx, cy)` on top of the 3D bone frames.

---

## 1. Hierarchical 3D Voxel Bone Architecture

Construct every organic character as a **parent → child bone hierarchy** rather than fixed coordinates:

```text
Root (Torso / Pelvis)  [stretch_y, squash_z, sx = 1/sqrt(stretch_y * squash_z), bob]
 ├── Head Bone         [head_y, head_z = root + head_bob + head_lean]
 │    ├── Tilted Face  [face_plane locked to (head_y, head_z) — never slides or squashes!]
 │    └── Secondary Appendages (Ears / Antennae / Hat)
 │         └── Driven by phase-delayed spring lag (phase - 0.85 rad) + wind sweep (ear_sweep)
 ├── Left / Right Arm Bones  [alternating phase (ph) vs (ph + pi), reaching forward in dash]
 ├── Left / Right Leg Bones  [opposite phase to arms for natural stride / flutter kick]
 └── Tail / Carried Prop     [secondary spring lag sway & vertical bounce]
```

### Volume-Preserving 3D Squash & Stretch Formula
Never scale just one axis (that looks flat or inflated). Always preserve 3D volume:

```python
from voxel_rig import volume_preserving_sx

sx = volume_preserving_sx(stretch_y, squash_z)  # = 1.0 / sqrt(stretch_y * squash_z)
d_torso = sd_ellipsoid(X, Y, Z, 0.0, y0 * stretch_y, z0 * squash_z, rx * sx, ry * stretch_y, rz * squash_z)
```

- When elongating forward (`stretch_y = 1.16`, `squash_z = 0.90`), `sx` shrinks automatically (~`0.98`), giving a crisp aerodynamic stretch!
- When compressing on contact (`stretch_y = 0.89`, `squash_z = 1.08`), `sx` widens plumply (~`1.02`)!

### Secondary Spring Motion (Follow-Through & Drag)
Real animation comes alive when flexible parts (long ears, bushy tails, antennae, pouch accessories) **lag slightly behind** torso motion:

```python
lag_s = math.sin(phase - 0.85)  # ~50 degrees behind torso bounce
ear_lift = 2.6 * lag_s          # ear tips lift as torso drops, dip as torso rises
ear_sweep = 6.5 if is_dash else (1.4 + 2.2 * math.sin(phase))
```

Build curved flexible appendages with `sd_bone_chain(X, Y, Z, joints, radii, smooth_k=2.2, y_flatten=1.3)` so 4–5 joint waypoints blend smoothly from root to tip and bend dynamically each frame.

### Head-Locked Tilted Face Projection
Always tie the facial projection center `(cy, cz)` directly to the moving **head bone** coordinates `(head_y, head_z)` so eyes, noses, and smiles track head bob and lean cleanly with zero smearing:

```python
from voxel_rig import face_plane

front, u, v = face_plane(
    occ & (d_head <= 0.6), X, Y, Z, ny,
    cy=head_y + head_ry * 0.8,
    cz=head_z - 0.4,
    y_min=head_y + head_ry * 0.4,
    tilt_deg=14.0,
)
```

---

## 2. Standard Frame Budgets & Gait Archetypes

| Entity Tier | Frames | Pose Layout | Recommended Angle Cache Steps |
| :--- | :--- | :--- | :--- |
| **Hero / Playable Character** | **7 frames** (`_0`..`_5` + `_6`) | 6-frame cyclic stride (`0..5`) + Frame `6` aerodynamic Dash / Leap stretch pose | `48` steps (7.5°) |
| **Animated NPC / Creature / Boss** | **2 frames** (`_0`, `_1`) | Wing flap, flipper wave, waddle alternation, blinking beacon/visor | `16` (mobs) / `24` (bosses) |
| **Static Prop** | **1 frame** | Rotate or bob with integer screen Y offset | `24` steps |

Built-in procedural rig generators in `scripts/voxel_rig.py` (`stride_rig_params(idx, style=...)`):
- **`belly_slide`**: Prone plush glide — strong horizontal stretch (`±11%`), alternating forward-paddling mitten arms, alternating rear flutter-kick feet, floppy spring ears. Frame 6 sweeps ears back and elongates `+16%`.
- **`biped`**: Energetic upright run — opposite arm/leg swing, hop bounce, vertical squash-and-stretch, wagging tail/antenna. Frame 6 leans forward into a full leap.
- **`waddle`**: Plump side-to-side waddle — exaggerated horizontal tail sway (`sway`), short flipper flap, gentle hop. Frame 6 transitions cleanly into a belly-slide dive!
- **`hover`**: Wing/fin flap + vertical float (`bob = 2.2 + 2.0 * sin(ph)`).

---

## 3. Preventing Edge Clipping & Mandatory 3D Motion QA

Stretched dash frames (`frame 6`) extend limbs and ears far further than idle poses. **Always**:
1. Size `(W, L, H)` from the **most extreme frame** (usually `frame 6` dash stretch or wide arm swing).
2. Run `assert_no_border_clipping(vol, label=f"{name}_{idx}")` on every sculpted frame — it catches 1-voxel paw/ear/tail clipping immediately.
3. Render and visually inspect the **multi-frame × multi-angle 3D contact sheet** before wiring into the browser:

```python
from voxel_rig import assert_no_border_clipping, render_animation_sheet

for idx, vol in enumerate(frames):
    assert_no_border_clipping(vol, label=f"hero_{idx}")

render_animation_sheet(
    frames,
    out_path="preview_bonerig.png",
    angles_deg=(22, 90, 180),  # Front-3/4, Side, Back across all 7 frames!
    squash=0.72,
    outline_color=(82, 24, 152),
    scale=3,
)
```

---

## 4. Runtime Spring-Damper Squash & Stretch (HTML5 Canvas)

Layer a lightweight 2nd-order damped spring on top of the 3D baked stack for instant tactile feedback on jumps, dashes, landings, and impacts — **without invalidating the 3D angle cache**:

```js
// State on entity:
// sqX: 1, sqY: 1, sqVx: 0, sqVy: 0, stridePhase: 0, hopZ: 0, hopVz: 0

function impulseSquash(ent, sx, sy) {
  ent.sqX = sx; ent.sqY = sy;
  ent.sqVx = 0; ent.sqVy = 0;
}

// Recommended elastic impulses:
// - Dash / Jump launch: impulseSquash(pl, 0.84, 1.22);
// - Landing contact:    impulseSquash(pl, 1.20, 0.84);
// - Impact / Recoil:    impulseSquash(pl, 1.24, 0.80);
// - Celebratory pop:    impulseSquash(pl, 0.86, 1.20);

function stepSpringAndStride(ent, dt) {
  const kSpring = 150, kDamp = 15;
  ent.sqVx += ((1 - ent.sqX) * kSpring - ent.sqVx * kDamp) * dt;
  ent.sqVy += ((1 - ent.sqY) * kSpring - ent.sqVy * kDamp) * dt;
  ent.sqX = Math.max(0.75, Math.min(1.30, ent.sqX + ent.sqVx * dt));
  ent.sqY = Math.max(0.75, Math.min(1.30, ent.sqY + ent.sqVy * dt));

  const spd = Math.hypot(ent.vx, ent.vy);
  // Advance 6-frame bone stride proportional to velocity; gentle breathing when idle!
  ent.stridePhase += dt * (spd > 6 ? (4.5 + spd * 0.085) : 2.2);
}

// Render anchored at ground pivot (b.cx, b.cy) so feet stay planted while body stretches!
function drawRiggedEntity(ctx, ent, sx, sy, camAngle, framePrefix, outline) {
  const fIdx = ent.dashTimer > 0 ? 6 : (Math.floor(ent.stridePhase) % 6);
  const b = getCached3D(`${framePrefix}_${fIdx}`, ent.heading + camAngle - Math.PI * 0.5, 48, outline, true);

  const moving = Math.hypot(ent.vx, ent.vy) > 16;
  const strideBob = moving ? Math.sin(ent.stridePhase * 2) : Math.sin(ent.stridePhase) * 0.35;
  const lift = Math.round(ent.hopZ) + (moving ? Math.round(Math.max(0, strideBob) * 2.0) : 0);

  // Combine runtime spring with subtle cyclic stride elasticity
  const cyc = 1 + strideBob * (moving ? 0.045 : 0.025);
  const sxMul = ent.sqX * (1 / cyc);
  const syMul = ent.sqY * cyc;

  const dw = Math.round(b.canvas.width * sxMul);
  const dh = Math.round(b.canvas.height * syMul);
  const dcx = Math.round(b.cx * sxMul);
  const dcy = Math.round(b.cy * syMul);

  // IMPORTANT: Separate hurtBlink from dash invuln so dash pose stays colorful & clear!
  const blink = ent.hurtBlink > 0 && Math.floor(clock * 24) % 2 === 0;
  const img = (blink && b.flash) ? b.flash : b.canvas;
  ctx.drawImage(img, sx - dcx, sy - dcy - lift, dw, dh);
}
```

---

## 5. Interactive Live 3D Showcase / Turntable Preview Widget

Reuse `getCached3D` inside small pixel-art preview canvases (e.g., Character Select, Model Inspector, Encyclopedia) with auto-fit scaling and pose switching:

```js
function render3DPreviewBox(canvasEl, framePrefix, frameCount, altFrame, outline, angleRad, showAlt) {
  const ctx = canvasEl.getContext("2d");
  ctx.imageSmoothingEnabled = false;
  const pw = canvasEl.width, ph = canvasEl.height;
  // Crisp 8x8 pixel checkerboard backdrop
  ctx.fillStyle = "#120d26"; ctx.fillRect(0, 0, pw, ph);
  ctx.fillStyle = "#1a1336";
  for (let y = 0; y < ph; y += 8)
    for (let x = ((y / 8) % 2) * 8; x < pw; x += 16)
      ctx.fillRect(x, y, 8, 8);

  const rate = frameCount <= 2 ? 3.2 : 7.5;
  const fIdx = showAlt ? altFrame : Math.floor(uiClock * rate) % frameCount;
  const b = getCached3D(`${framePrefix}_${fIdx}`, angleRad, 48, outline, false);

  const bob = showAlt ? 3 : Math.round(Math.sin(uiClock * rate) * 1.4);
  const sxMul = showAlt ? 0.89 : (1 + Math.sin(uiClock * rate) * 0.04);
  const syMul = showAlt ? 1.13 : (1 / sxMul);
  const fit = Math.min(1.0, (ph - 12) / Math.max(1, b.canvas.height));

  const pcx = Math.floor(pw / 2), pcy = Math.floor(ph * 0.72);
  ctx.drawImage(
    b.canvas,
    pcx - Math.round(b.cx * sxMul * fit),
    pcy - Math.round(b.cy * syMul * fit) - bob,
    Math.round(b.canvas.width * sxMul * fit),
    Math.round(b.canvas.height * syMul * fit)
  );
}
```
