---
name: sprite-stacking-3d
description: >-
  Build pseudo-3D pixel-art / voxel-art sprite-stacking assets and interactive
  browser demos (including zero-dependency single-HTML builds). Use when the user
  asks for sprite stacking, fake 3D pixel art rotatable to 360 degrees, turning
  2D character art or 4-view orthographic sheets into stacked slices, diagnosing
  3D slice quality (squashed faces, overhangs, double eyes), or building a fast
  top-down pseudo-3D HTML5 Canvas demo.
---

# Sprite Stacking 3D Skill

Build crisp, 360°-rotatable pseudo-3D pixel-art objects and interactive demos using horizontal slice sheets stacked layer by layer.

> **Credit / Inspiration**: Core sprite-stacking method and 4-view carving workflow inspired by
> [SpriteCook — Sprite stacking for fake 3D pixel art cars and props](https://www.spritecook.ai/blog/sprite-stacking-pixel-art).

## 1. Choose the Right Slice-Creation Method

Always pick the right voxelization method for the subject before writing code:

| Subject Type | Recommended Method | Script | Why |
| :--- | :--- | :--- | :--- |
| **Boxy / convex objects** (cars, trucks, tanks, crates, buildings) | 2×2 orthographic 4-view sheet (`TOP`, `SIDE`, `FRONT`, `BACK`) → visual-hull carving | [views_to_slices.py](./scripts/views_to_slices.py) | Fast from a single AI image generation; convex shapes carve cleanly. |
| **Organic characters, round props, overhangs** (characters with ears/faces, snowmen with hat brims/scarves/carrot noses, scalloped trees) | **True 3D SDF voxel sculpting** guided by the user's character art / generated concept | [sdf_primitives.py](./scripts/sdf_primitives.py) | Avoids visual-hull bugs: overhang color bleeding, doubled side-view eyes on cheeks, boxy spheres, and thin 1px face dropout. |

### Key Quality Rules for Organic Characters & Faces
1. **Tilt facial planes gently upward (`12°–15°`)** toward the angled top-down camera (`project_tilted_face` in [sdf_primitives.py](./scripts/sdf_primitives.py)) so faces do not vertically squash at `squash = 0.72–0.75`.
2. **Embed facial features `2.5–3` voxels deep** into the front surface shell so nearest-neighbor rotation at diagonal angles (`25°–60°`) never drops eye/mouth pixels or exposes interior color.
3. **Never bake outlines into slices** — strip outer & internal dark lines before slicing, then apply a crisp 1px post-stack outline around the finished stacked sprite.
4. **Separate materials cleanly** (e.g. hat, scarf, snow, carrot, coal eyes) and apply 3-step cel shading from SDF surface normals + crease AO.

## 2. Mandatory Verification Step: Inspect the Actual 3D Stack

Never judge quality from a single flat slice. After generating any slice sheet, **always** render the stacked 3D object from multiple angles and inspect the PNG visually:

```bash
python3 scripts/render_turntable.py <slices.png> \
  --slices <N> \
  --out preview_3d.png \
  --angles 0,30,60,90,135,180 \
  --squash 0.72 \
  --outline 64,18,122 \
  --scale 4 \
  --spread
```

Check for:
- Face readability at `0°`, `30°`, and `60°` (no merged nose/mouth, no pixel dropout)
- Clean overhangs under ears, hats, scarves, and branches (zero black bands or color leaks)
- Silhouette accuracy at `90°` side and `180°` back views

## 3. Resolution Presets

- **Retro Pixel-Art (~28–40 slices)**: Hero ~`36×42×28`, props `24–34 px`, default display zoom `3x` (`2x–6x`). Ultra-fast (`~1.2 ms/frame`).
- **HD Crisp Voxel (~44–64 slices)**: Hero ~`58×66×44`, props `38–54 px`, default display zoom `2x` (`1x–4x`). Smooth curves & expressive faces (`~2.5 ms/frame`).

## 4. High-FPS Rendering & Single-HTML Packaging

1. Read [references/canvas_renderer.md](./references/canvas_renderer.md) for the tight-bounds quantized angle-cache renderer (`24` steps for symmetric props, `48` for detailed props, `120` for player), post-stack `source-in` 1px outline, and camera-space Y-sorting.
2. Keep `spacing` constant during gameplay animation (use integer Y-offset for hops/wobbles instead of mutating `spacing` every frame) to prevent vertical face shimmer and maintain >95% cache hit rate.
3. To deliver a zero-dependency single-file HTML that runs cleanly over `file://` without CORS canvas tainting, run:

```bash
python3 scripts/bundle_standalone.py \
  --html index.html \
  --js demo.js \
  --manifest assets_manifest.json \
  --out demo-standalone.html
```

4. Verify the final HTML in headless Chromium/Playwright for zero `pageerror` / console errors and measure average render ms/frame.
