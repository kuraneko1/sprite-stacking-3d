# 100% Pixel-Art UI, Zero-Default-Controls, Pixel FX & Mobile Touch Architecture

Never mix crisp pixel-art 3D sprite stacks with blurry SaaS glassmorphism, OS emojis, native browser `<input type="range">` sliders, or smooth Canvas vector primitives (`ctx.arc`, `ctx.ellipse`, `ctx.stroke`, `ctx.fillText`).

---

## 1. Strict Visual Consistency Rules (Enforced via `scripts/audit_pixel_build.py`)

1. **Zero OS Unicode Emojis**: Replace every UI icon with custom 16×16 pixel-art PNGs (`scripts/pixel_atlas_kit.py` `draw_pattern`) hydrated via `<img class="px-ico" data-ico="..." />` with `image-rendering: pixelated`.
2. **Zero Native Browser Form Controls**: Never use `<input type="range">`, `<select>`, `<progress>`, or `accent-color`. Build custom pixel widgets instead.
3. **Zero Blur & Zero Rounded Corners**: Set `* { border-radius: 0; }`, `button { appearance: none; }`, zero `backdrop-filter`, and `0px`-blur hard-edge pixel bevels (`box-shadow: inset 2px 2px 0 hi, inset -2px -2px 0 lo, 0 4px 0 rgba(0,0,0,0.55)`).
4. **Custom Pixel Scrollbars & Focus Rings**: Style `::-webkit-scrollbar` with square beveled thumbs and replace browser focus halos with `outline: 2px solid #facc15; outline-offset: 2px;` on `:focus-visible`.
5. **Zero Smooth Vector Canvas Primitives**:
   - Contact shadows → blit dithered PNGs (`make_dithered_shadow`)
   - Ground rings / auras → blit stepped pixel rings (`make_stepped_ring`)
   - Arcs / slashes / beams → blit multi-frame pixel FX (`make_slash_frames`, `make_jagged_bolt_frames`)
   - Canvas numbers / HUD text → blit 5×7 outlined bitmap font strips (`make_bitmap_font_strip`) via `drawPixelText`!

---

## 2. Custom Pixel-Art Segmented Slider & 4-Column Aligned Settings Grid

Keep every setting row aligned to the exact same vertical ruler across desktop & 390px smartphones by using a **4-column CSS Grid** (`Label | Pixel Slider | Right-aligned Value | Fixed-width Action Button or empty spacer`):

```css
.slider-row {
  display: grid;
  grid-template-columns: 112px 1fr 56px 70px;
  align-items: center;
  gap: 10px;
  padding: 11px 0;
  border-bottom: 2px solid #2b224d;
  font-size: 14px; font-weight: 900;
}
.slider-val { text-align: right; font-variant-numeric: tabular-nums; color: #facc15; }
.slider-action { width: 70px; min-height: 36px; padding: 6px 0; }

.px-slider {
  position: relative; width: 100%; height: 26px;
  display: flex; align-items: center; cursor: pointer; touch-action: none;
}
.px-slider-track {
  position: relative; width: 100%; height: 14px;
  background: #0c0918; border: 2px solid #070510;
  box-shadow: inset 2px 2px 0 #05030a, inset -1px -1px 0 #352b5c;
  overflow: hidden;
}
.px-slider-fill {
  height: 100%; background: #9333ea;
  box-shadow: inset 0 2px 0 #e9d5ff, inset 0 -2px 0 #581c87;
}
.px-slider-ticks {
  position: absolute; inset: 0; pointer-events: none;
  background: repeating-linear-gradient(90deg, transparent 0 10px, rgba(7,5,16,0.72) 10px 12px);
}
.px-slider-thumb {
  position: absolute; top: 1px; width: 14px; height: 24px; transform: translateX(-7px);
  background: #e2e8f0; border: 2px solid #070510;
  box-shadow: inset 2px 2px 0 #fff, inset -2px -2px 0 #64748b, 0 2px 0 rgba(0,0,0,0.65);
  pointer-events: none;
}
.px-slider:hover .px-slider-thumb, .px-slider.dragging .px-slider-thumb { background: #facc15; }
```

Rows without an action button place `<span class="slider-empty"></span>` in Column 4 so **all sliders keep identical left X and identical width**!

---

## 3. Smartphone & Touch-First Responsive Architecture

### A. Floating 100% Pixel-Art Virtual Joystick (Rendered on Canvas)
Rather than steering relative to screen center (which forces the thumb over the character), anchor the joystick dynamically wherever the finger touches down:

```js
const stick = { active: false, id: null, ox: 0, oy: 0, cx: 0, cy: 0 };

canvas.addEventListener("pointerdown", (e) => {
  stick.active = true; stick.id = e.pointerId;
  stick.ox = stick.cx = e.clientX;
  stick.oy = stick.cy = e.clientY;
});
window.addEventListener("pointermove", (e) => {
  if (!stick.active || e.pointerId !== stick.id) return;
  stick.cx = e.clientX; stick.cy = e.clientY;
  // Gently follow finger beyond 64px so instant direction reversals feel snappy
  const dx = stick.cx - stick.ox, dy = stick.cy - stick.oy;
  const d = Math.hypot(dx, dy);
  if (d > 64) { const pull = (d - 64) / d; stick.ox += dx * pull; stick.oy += dy * pull; }
});
```

Render the joystick using **only `ctx.fillRect`** (stepped pixel octagonal frame + 45° corner stair pixels + center crosshair + beveled square thumb nub) — zero `ctx.arc`!

### B. Portrait FOV Auto-Scaling & Safe Areas
On narrow portrait phones (`390×844`), clamp the pixel zoom so gameplay maintains enough visible horizon:

```js
let effScale = Math.max(1, viewCfg.zoom * (dpr > 1.3 ? 1.25 : 1));
if (displayCanvas.width / effScale < 260) {
  effScale = Math.max(1, displayCanvas.width / 260);
}
```

Include `viewport-fit=cover` in `<meta name="viewport">` and offset HUD / touch controls using `env(safe-area-inset-top)`, `env(safe-area-inset-bottom)`, `env(safe-area-inset-right)`. Provide compact `<3D` / `3D>` hold-to-rotate buttons alongside the main touch action button on `@media (pointer: coarse), (max-width: 860px)`.

---

## 4. Pixel Bitmap Font Renderer (Canvas 2D)

Pair `make_bitmap_font_strip(chars, fill_rgb, outline_rgb)` (`7×9` px per glyph) with:

```js
const FONT_CHARS = "0123456789!+-:.";
function drawPixelText(ctx, text, cx, cy, fontImg, scale = 1) {
  if (!fontImg) return;
  const s = String(text);
  const step = 6 * scale; // 1px tight kerning overlap on outlines
  let x = Math.round(cx - (s.length * step + scale) * 0.5);
  const y = Math.round(cy - (9 * scale) * 0.5);
  for (let i = 0; i < s.length; i++) {
    const idx = FONT_CHARS.indexOf(s[i]);
    if (idx >= 0) ctx.drawImage(fontImg, idx * 7, 0, 7, 9, x, y, 7 * scale, 9 * scale);
    x += step;
  }
}
```
