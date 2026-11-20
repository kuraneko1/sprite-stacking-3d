---
name: sprite-stacking-3d
description: >-
  Build animated, bone-rigged pseudo-3D pixel-art / voxel-art sprite-stacking assets,
  pure pixel-art UI/FX/mobile touch controls, and SoundFont2 studio audio for interactive
  browser apps and games (including zero-dependency single-HTML builds). Use when the user
  asks for sprite stacking, fake 3D pixel art rotatable to 360 degrees, 3D voxel bone rigging
  and squash-and-stretch animation (floppy ears, tails, limbs, dash poses), turning 2D character
  art or 4-view sheets into stacked slices, diagnosing 3D slice quality, building 100% pixel-art
  UI without default browser sliders/emojis, mobile virtual joysticks, or rich SoundFont2 BGM/SFX.
---

# Sprite Stacking 3D Skill (v2.0)

Build crisp, 360°-rotatable, **bone-rigged and squash-and-stretch animated** pseudo-3D pixel-art characters, props, pure pixel-art UI/FX, and studio-mastered SoundFont2 audio — packaged cleanly into fast HTML5 Canvas apps or zero-dependency single-file HTML.

> **Credit / Inspiration**: Core sprite-stacking method and 4-view carving workflow inspired by
> [SpriteCook — Sprite stacking for fake 3D pixel art cars and props](https://www.spritecook.ai/blog/sprite-stacking-pixel-art).

---

## 1. Choose the Right 3D Voxelization & Animation Method

| Subject Type | Recommended Method | Scripts | Why |
| :--- | :--- | :--- | :--- |
| **Boxy / convex static objects** (cars, trucks, crates, buildings) | 2×2 orthographic 4-view sheet (`TOP`, `SIDE`, `FRONT`, `BACK`) → visual-hull carving | [views_to_slices.py](./scripts/views_to_slices.py) | Fast from a single 4-view image; convex volumes carve cleanly. |
| **Static organic props / characters** (round silhouettes, hats, overhangs, faces) | **True 3D SDF voxel sculpting** with 3-step cel shading & tilted facial projection | [sdf_primitives.py](./scripts/sdf_primitives.py) | Eliminates visual-hull overhang color bleeding, doubled cheek eyes, and 1px face dropout. |
| **Living animated characters** (stride/run/belly-slide/waddle/hover + dash poses, floppy ears, tails, antennae) | **Hierarchical 3D SDF Bone Rigging** (6 cyclic frames + 1 dash stretch frame) + **Runtime Spring-Damper Squash & Stretch** | [voxel_rig.py](./scripts/voxel_rig.py) + [sdf_primitives.py](./scripts/sdf_primitives.py) | Preserves 3D volume (`sx = 1/sqrt(stretch_y * squash_z)`), adds phase-delayed secondary spring lag, and locks faces to moving head bones. |

---

## 2. 3D Voxel Bone Rigging & Living Animation Workflow

Read [references/bone_rigging_and_animation.md](./references/bone_rigging_and_animation.md) before sculpting animated characters. Core principles:

1. **Parent → Child Bone Hierarchy**: Drive Torso/Pelvis (`stretch_y`, `squash_z`, `sx = volume_preserving_sx(...)`, `bob`) → Head Bone (`head_y`, `head_z`) → Secondary Appendages (`sd_bone_chain` with phase-delayed spring lag `phase - 0.85 rad`) + alternating Arms/Legs.
2. **Head-Locked Tilted Face Projection**: Use `face_plane(...)` anchored to the moving `(head_y, head_z)` bone with `12°–15°` upward tilt and `2.5–3` voxel shell depth so faces never squash or drop pixels at diagonal angles.
3. **Never Bake Outlines into Slices**: Keep slice interiors clean, then apply a crisp 1px post-stack silhouette outline in the renderer.
4. **Prevent Extreme-Pose Clipping**: Size `(W, L, H)` from the most extended frame (typically Frame 6 Dash/Leap) and call `assert_no_border_clipping(vol)` on every generated frame.
5. **Layer Runtime Spring-Damper Elasticity (JS)**: Combine the baked 7-frame 3D bone rig with a 2nd-order spring oscillator (`sqX`, `sqY`) anchored at ground pivot `(b.cx * sxMul, b.cy * syMul)` for juicy launch/landing/recoil impulses without invalidating the 3D angle cache.
6. **Separate `hurtBlink` from Action `invuln`**: Only flash white on damage — never white-out colorful dash/action poses!

---

## 3. Mandatory Visual QA: Always Inspect the Stacked 3D Output

Never judge quality from a single flat slice. Render and visually inspect the **actual 3D stack** across multiple angles and frames:

- **Single static asset (multi-angle + spread layers)**:
  ```bash
  python3 scripts/render_turntable.py <slices.png> \
    --slices <N> --out preview_3d.png \
    --angles 0,30,60,90,135,180 --squash 0.72 --outline 64,18,122 --scale 4 --spread
  ```
- **Animated bone-rigged character (all frames × Front-3/4, Side, Back)**:
  Use `render_animation_sheet(frames, out_path, angles_deg=(22, 90, 180), ...)` from [voxel_rig.py](./scripts/voxel_rig.py) (see runnable example in [examples/bonerig_character_example.py](./examples/bonerig_character_example.py)).

Verify face readability at `0°–60°`, clean overhangs, zero edge-voxel clipping, and smooth silhouette transitions across all frames.

---

## 4. 100% Pure Pixel-Art UI, FX & Mobile Touch Controls

Read [references/pixel_ui_and_fx.md](./references/pixel_ui_and_fx.md) when building browser interfaces around 3D sprite stacks:

- **Zero Default Browser UI & Zero OS Emojis**: Replace native `<input type="range">` with custom pixel segmented sliders (`.px-slider`) aligned in a strict 4-column settings grid (`Label | Slider | Value | Button`), style square pixel scrollbars and square `:focus-visible` outlines, set `border-radius: 0`, and generate 16×16 pixel icons via [pixel_atlas_kit.py](./scripts/pixel_atlas_kit.py).
- **Zero Smooth Vector Canvas Primitives**: Use [pixel_atlas_kit.py](./scripts/pixel_atlas_kit.py) for dithered shadows (`make_dithered_shadow`), stepped ground rings (`make_stepped_ring`), multi-frame pixel slashes/beams (`make_slash_frames`, `make_jagged_bolt_frames`), sparks, and 5×7 outlined bitmap font strips (`make_bitmap_font_strip`).
- **Smartphone / Touch-Ready**: Render a floating 100% pixel-art octagonal virtual joystick directly in Canvas on `pointerdown` (with gentle origin-follow), add `<3D` / `3D>` touch rotate buttons + safe-area offsets, and auto-cap zoom on portrait viewports so `sceneW >= 260`.

Run the automated purity check before shipping:
```bash
python3 scripts/audit_pixel_build.py --html index.html --js app.js
```

---

## 5. Rich Studio Audio (SoundFont2 + Pedalboard, Zero Cheap Oscillators)

Read [references/soundfont_audio_pipeline.md](./references/soundfont_audio_pipeline.md) whenever adding BGM or SFX:

- Compose multi-track MIDI with `MultiTrackComposer` ([sf2_audio_kit.py](./scripts/sf2_audio_kit.py)), render real multi-sampled instruments offline with [render_sf2.mjs](./scripts/render_sf2.mjs) (`spessasynth_core` + `GeneralUser-GS.sf2`) using **2-cycle seamless reverb-tail slicing**, and master to stereo MP3 with Spotify `pedalboard` + `ffmpeg`.
- Play BGM via native HTML5 `<audio>` dual-deck crossfading and SFX via pooled `<audio>` elements with independent persisted BGM & SE volume sliders.

---

## 6. High-FPS Rendering, Packaging & Verification

1. Follow [references/canvas_renderer.md](./references/canvas_renderer.md) for the tight-bounds quantized angle cache (`assetKey|outlineColor|steps|bucket`), lazy null-safe hit-flash canvas creation, camera-space Y-sorting, and live 3D showcase previews.
2. Bundle into a zero-dependency single-HTML file (works over `file://` with zero CORS issues):
   ```bash
   python3 scripts/bundle_standalone.py \
     --html index.html --js app.js --manifest assets_manifest.json \
     --audio-dir assets/audio --out app-standalone.html
   ```
3. Verify in headless Chromium/Playwright on **both Desktop (`1280×800`) and Smartphone (`390×844`, `has_touch=True`)** for zero `pageerror`/console errors, pixel-exact UI alignment, and smooth 60 FPS frame times.
