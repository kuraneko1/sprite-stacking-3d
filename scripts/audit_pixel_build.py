#!/usr/bin/env python3
"""Automated Pixel-Art Purity & Zero-Default-UI Auditor.

Verifies that an HTML5 pixel-art web app/demo contains:
  - ZERO native browser form controls (<input>, <select>, <textarea>, <progress>, <meter>, <details>, accent-color)
  - ZERO non-zero border-radius & ZERO backdrop-filter glassmorphism
  - ZERO default OS Unicode emojis
  - ZERO smooth vector Canvas 2D primitives (.arc(, .ellipse(, .stroke(, .strokeRect(, .fillText()
  - Optionally ZERO bare Web Audio oscillator synthesis (createOscillator / AudioContext)

Usage:
  python3 audit_pixel_build.py --html index.html --js app.js [--allow-web-audio]
"""
import argparse
import re
import sys
from pathlib import Path

NATIVE_UI_PATTERNS = [
    r"<input\b", r"<select\b", r"<textarea\b", r"<progress\b", r"<meter\b", r"<details\b", r"accent-color",
]
CANVAS_VECTOR_TOKENS = [".arc(", ".ellipse(", ".stroke(", ".strokeRect(", ".fillText(", "backdrop-filter"]
WEB_AUDIO_TOKENS = ["AudioContext", "createOscillator"]
EMOJI_RE = re.compile(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]")


def audit_files(html_path: Path | None, js_path: Path | None, allow_web_audio: bool = False) -> list[str]:
    issues: list[str] = []
    targets = []
    if html_path:
        targets.append(("HTML", html_path.read_text(encoding="utf-8")))
    if js_path:
        targets.append(("JS", js_path.read_text(encoding="utf-8")))

    for label, text in targets:
        # Strip HTML/CSS comments only when checking native tags? Keep strict so stray markup is caught
        for pat in NATIVE_UI_PATTERNS:
            if re.search(pat, text, re.I):
                issues.append(f"[{label}] Forbidden native UI control matched: {pat}")

        for r in re.findall(r"border-radius\s*:\s*([^;\}]+)", text):
            if r.strip() not in ("0", "0px"):
                issues.append(f"[{label}] Non-zero border-radius found: {r.strip()}")

        emojis = EMOJI_RE.findall(text)
        if emojis:
            issues.append(f"[{label}] Found OS Unicode emoji(s): {sorted(set(emojis))[:8]}")

        for tok in CANVAS_VECTOR_TOKENS:
            if tok in text:
                issues.append(f"[{label}] Forbidden vector/blur primitive found: '{tok}'")

        if not allow_web_audio:
            for tok in WEB_AUDIO_TOKENS:
                if tok in text:
                    issues.append(f"[{label}] Raw Web Audio API token found (use SoundFont2 MP3 + HTML5 <audio>): '{tok}'")

    return issues


def main():
    p = argparse.ArgumentParser(description="Audit pixel-art HTML/JS for zero default UI, emojis, and vector canvas calls.")
    p.add_argument("--html", type=Path, help="Path to HTML file")
    p.add_argument("--js", type=Path, help="Path to JS file")
    p.add_argument("--allow-web-audio", action="store_true", help="Allow Web Audio API tokens")
    args = p.parse_args()

    if not args.html and not args.js:
        p.error("Provide at least --html or --js")

    issues = audit_files(args.html, args.js, allow_web_audio=args.allow_web_audio)
    if issues:
        print("AUDIT FAILED:")
        for item in issues:
            print("  -", item)
        sys.exit(1)
    print("AUDIT PASSED: 100% pixel-art compliant (zero default UI, zero emojis, zero vector canvas primitives).")


if __name__ == "__main__":
    main()
