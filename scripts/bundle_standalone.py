"""Bundle a Sprite Stacking HTML + JS + PNG/JPG asset manifest into a single standalone HTML file.

Works cleanly over direct `file://` opening with zero CORS canvas-tainting issues and zero server setup.

Usage:
  python3 bundle_standalone.py \
      --html index.html \
      --js demo.js \
      --manifest assets_manifest.json \
      --out demo-standalone.html

Where assets_manifest.json maps asset keys to {"file": "path.png", "count": 44}:
  {
    "heroSlices": {"file": "assets/hero_slices.png", "count": 44},
    "groundTile": {"file": "assets/ground.png", "count": 1}
  }
"""
import argparse
import base64
import json
import mimetypes
import os
from PIL import Image


def main():
    p = argparse.ArgumentParser(description="Bundle sprite-stacking HTML, JS, and assets into 1 standalone HTML.")
    p.add_argument("--html", required=True, help="Template HTML file containing <script src=...> placeholders")
    p.add_argument("--js", required=True, help="Main JS file to inline")
    p.add_argument("--manifest", required=True, help="JSON manifest mapping asset keys to {file, count}")
    p.add_argument("--audio-dir", default="", help="Optional directory of .mp3 files to inline into window.SPRITE_AUDIO")
    p.add_argument("--out", required=True, help="Output standalone HTML path")
    p.add_argument("--assets-tag", default='<script src="./assets_data.js"></script>')
    p.add_argument("--js-tag", default='<script src="./demo.js"></script>')
    a = p.parse_args()

    manifest_dir = os.path.dirname(os.path.abspath(a.manifest))
    with open(a.manifest, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    meta = {}
    data_map = {}
    for key, spec in manifest.items():
        fpath = spec["file"]
        if not os.path.isabs(fpath):
            fpath = os.path.join(manifest_dir, fpath)
        mime, _ = mimetypes.guess_type(fpath)
        mime = mime or "image/png"
        with open(fpath, "rb") as bf:
            b64 = base64.b64encode(bf.read()).decode("ascii")
        im = Image.open(fpath)
        data_map[key] = f"data:{mime};base64,{b64}"
        cnt = int(spec.get("count", 1))
        meta[key] = {"w": im.width // cnt if cnt > 1 else im.width, "h": im.height, "count": cnt, "slices": cnt}

    audio_map = {}
    if a.audio_dir and os.path.isdir(a.audio_dir):
        for fname in sorted(os.listdir(a.audio_dir)):
            if fname.lower().endswith(".mp3"):
                stem = os.path.splitext(fname)[0]
                with open(os.path.join(a.audio_dir, fname), "rb") as af:
                    audio_map[stem] = base64.b64encode(af.read()).decode("ascii")

    assets_js = (
        "window.SPRITE_META = " + json.dumps(meta, separators=(",", ":")) + ";\n"
        "window.SPRITE_ASSETS = " + json.dumps(data_map, separators=(",", ":")) + ";\n"
        + ("window.SPRITE_AUDIO = " + json.dumps(audio_map, separators=(",", ":")) + ";\n" if audio_map else "")
    ).replace("</script", "<\\/script")

    with open(a.html, "r", encoding="utf-8") as f:
        html = f.read()
    with open(a.js, "r", encoding="utf-8") as f:
        demo_js = f.read().replace("</script", "<\\/script")

    if a.assets_tag in html:
        html = html.replace(a.assets_tag, f"<script>\n{assets_js}\n</script>", 1)
    else:
        html = html.replace("</body>", f"<script>\n{assets_js}\n</script>\n</body>", 1)

    if a.js_tag in html:
        html = html.replace(a.js_tag, f"<script>\n{demo_js}\n</script>", 1)
    else:
        html = html.replace("</body>", f"<script>\n{demo_js}\n</script>\n</body>", 1)

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Bundled standalone HTML -> {a.out} ({os.path.getsize(a.out):,} bytes)")


if __name__ == "__main__":
    main()
