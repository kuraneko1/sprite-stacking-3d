# High-FPS Sprite Stacking Renderer Reference

> Based on SpriteCook's Sprite Stacking guide:
> <https://www.spritecook.ai/blog/sprite-stacking-pixel-art>

## Core Transform Order

Every slice sheet is one horizontal row of `count` equal slices (`sw x sh` px), ground slice (`z = 0`) on the left and top slice (`z = count - 1`) on the right. The object faces **down (`+y`)** in the slice sheet.

For an object facing world angle `heading` under camera rotation `camAngle`:

```js
const screenTurn = heading + camAngle - Math.PI * 0.5;
```

Per slice `z = 0 .. count - 1`:

```js
ctx.translate(cx, cy - Math.round(z * spacing)); // 1. Lift vertically by whole px
ctx.scale(1, squash);                            // 2. Camera tilt (0.70–0.75 recommended)
ctx.rotate(screenTurn);                          // 3. Same rotation for every slice
ctx.drawImage(sheet, z * sw, 0, sw, sh, -Math.floor(sw / 2), -Math.floor(sh / 2), sw, sh);
```

## Fast Tight-Bounds Baking + Post-Stack 1px Outline + Angle Cache (HTML5 Canvas 2D)

Never redraw 40–60 slices + `source-in` outline on giant buffers every frame for dozens of objects. Instead:

1. Compute tight per-object bounding dimensions `(bw, bh)` from `diag = ceil(hypot(sw, sh))` and `liftH = ceil(count * spacing)`.
2. Draw all slices into a reusable scratch canvas (`stackBuf`).
3. Create a 1px silhouette mask once via `globalCompositeOperation = "source-in"` on `tintBuf`, then stamp it at `(-1,0), (+1,0), (0,-1), (0,+1)` behind the finished stack (eliminates internal dark speckles on diagonals).
4. **Bug-Proof Cache Keys & Lazy Flash Variants**:
   - Always include `outlineColor` and `steps` in the cache key (`${assetKey}|${outlineColor}|${steps}|${bucket}`) — never omit `outlineColor` or outlined variants (e.g. gold highlights) will collide with normal sprites!
   - If using white hit-flash sprites (`makeFlash`), populate `entry.flash` lazily when a caller requests `makeFlash = true` on a previously cached entry whose `flash` was `null`, AND always guard blits with `(useFlash && entry.flash) ? entry.flash : entry.canvas` to prevent `drawImage(null)` crashes!
   - Separate `hurtBlink` from dash/action `invuln` so dashing characters display their colorful 3D dash pose cleanly without flashing solid white.
5. Cache baked canvases by `(assetKey, outlineColor, steps, angleBucket)` with LRU eviction (`~960–1100` entries for multi-frame animated casts):
   - Static/symmetric props: `24` angle steps (15°)
   - Animated NPCs (2 frames): `16` steps × 2 frames = `32` max per type
   - Animated Bosses (2 frames): `24` steps × 2 frames = `48` max per type
   - Bone-rigged Hero (7 frames): `48` steps × 7 frames = `336` max — layer runtime spring squash-and-stretch on `drawImage` rather than baking extra spacing variants!

```js
const bakedCache = new Map();
let cacheSig = "";

function getCachedStack(type, sheet, count, turnRad, steps, outlineColor, squash, spacing, outlineOn) {
  const sig = `${squash.toFixed(2)}_${spacing.toFixed(2)}_${outlineOn ? 1 : 0}`;
  if (sig !== cacheSig) {
    bakedCache.clear();
    cacheSig = sig;
  }
  const TWO_PI = Math.PI * 2;
  const norm = ((turnRad % TWO_PI) + TWO_PI) % TWO_PI;
  const bucket = Math.round((norm / TWO_PI) * steps) % steps;
  const key = `${type}_${bucket}`;
  if (bakedCache.has(key)) return bakedCache.get(key);

  const sw = sheet.width / count;
  const sh = sheet.height;
  const diag = Math.ceil(Math.hypot(sw, sh));
  const bw = diag + 12;
  const bh = Math.ceil(diag * squash) + Math.ceil(count * spacing) + 12;
  const cx = Math.floor(bw / 2);
  const cy = bh - Math.ceil(diag * squash * 0.5) - 6;

  // Render slices into offscreen canvas
  const raw = document.createElement("canvas");
  raw.width = bw;
  raw.height = bh;
  const rctx = raw.getContext("2d");
  rctx.imageSmoothingEnabled = false;
  const snapped = (bucket / steps) * TWO_PI;
  const ox = -Math.floor(sw / 2);
  const oy = -Math.floor(sh / 2);

  for (let z = 0; z < count; z++) {
    rctx.save();
    rctx.translate(cx, cy - Math.round(z * spacing));
    rctx.scale(1, squash);
    rctx.rotate(snapped);
    rctx.drawImage(sheet, z * sw, 0, sw, sh, ox, oy, sw, sh);
    rctx.restore();
  }

  const out = document.createElement("canvas");
  out.width = bw;
  out.height = bh;
  const octx = out.getContext("2d");
  octx.imageSmoothingEnabled = false;

  if (outlineOn && outlineColor) {
    const tint = document.createElement("canvas");
    tint.width = bw;
    tint.height = bh;
    const tctx = tint.getContext("2d");
    tctx.imageSmoothingEnabled = false;
    tctx.drawImage(raw, 0, 0);
    tctx.globalCompositeOperation = "source-in";
    tctx.fillStyle = outlineColor;
    tctx.fillRect(0, 0, bw, bh);
    octx.drawImage(tint, -1, 0);
    octx.drawImage(tint, 1, 0);
    octx.drawImage(tint, 0, -1);
    octx.drawImage(tint, 0, 1);
  }
  octx.drawImage(raw, 0, 0);

  const entry = { canvas: out, cx, cy };
  if (bakedCache.size > 260) bakedCache.delete(bakedCache.keys().next().value);
  bakedCache.set(key, entry);
  return entry;
}
```

## Camera-Space Ground Projection & Y-Sorting

To support 360° camera rotation (`camAngle`) while keeping ground trails locked and objects properly sorted:

```js
// Rotate world offset by camAngle, then apply squash vertically
const dx = wx - camX, dy = wy - camY;
const rx = dx * Math.cos(camAngle) - dy * Math.sin(camAngle);
const ry = dx * Math.sin(camAngle) + dy * Math.cos(camAngle);
const sx = Math.round(screenCenterX + rx);
const sy = Math.round(screenCenterY + ry * squash);
// Sort all whole stacks back-to-front by `ry` (never slice-by-slice!)
```

## Godot 4 Reference (from SpriteCook)

```gdscript
extends Node2D

@export var sheet: Texture2D
@export var slices := 30
@export var turn := 0.0
@export_range(0.1, 1.0) var squash := 0.72
@export var spacing := 1.0

func _process(_delta: float) -> void:
	queue_redraw()

func _draw() -> void:
	if sheet == null:
		return
	var w := float(sheet.get_width()) / slices
	var h := float(sheet.get_height())
	var rect := Rect2(-floorf(w / 2.0), -floorf(h / 2.0), w, h)
	var spin := Transform2D(turn, Vector2.ZERO)
	for z in slices:
		var lift := Transform2D(Vector2(1, 0), Vector2(0, squash), Vector2(0, -roundf(z * spacing)))
		draw_set_transform_matrix(lift * spin)
		draw_texture_rect_region(sheet, rect, Rect2(z * w, 0, w, h))
```
