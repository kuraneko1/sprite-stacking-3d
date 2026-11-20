# Real Multi-Sampled SoundFont2 Studio Audio Pipeline

Avoid harsh, cheap-sounding bare Web Audio API oscillators (`createOscillator`) for BGM and fanfares. Instead, render **real multi-sampled studio instruments** offline via SoundFont2 (`.sf2`) + Spotify `pedalboard` mastering → compact stereo MP3s played natively via HTML5 `<audio>`.

---

## 1. One-Time Tool Setup

```bash
# Python MIDI + mastering dependencies
pip3 install --user mido pedalboard scipy numpy

# Node pure-JS SoundFont2 synthesizer (zero native C++ build required!)
npm install spessasynth_core

# Download a free studio-grade GM SoundFont (~31 MB, GeneralUser-GS)
curl -L -o GeneralUser-GS.sf2 \
  "https://github.com/mrbumpy409/GeneralUser-GS/raw/main/GeneralUser-GS.sf2"
```

---

## 2. Seamless 2-Pass Loop Rendering Trick

Rendering a looping track once causes reverb and chorus tails to start dry at `t = 0` and cut off abruptly at the end.

`scripts/render_sf2.mjs` solves this automatically when `loop_sec > 0`:
1. Configures `seq.loopCount = 2` and renders **2 full cycles** (`0 .. 2 * loop_sec`).
2. Slices **Cycle 2** (`[loop_sec, 2 * loop_sec]`) so the natural reverb/instrument tail from the end of Cycle 1 wraps seamlessly into the start of the loop.
3. Applies a tiny 4ms boundary cross-blend (`160–180` samples) both before and after `pedalboard` mastering (`scripts/sf2_audio_kit.py` `master_to_mp3`) for 100% click-free looping!

```python
from sf2_audio_kit import MultiTrackComposer, render_midi_with_sf2, master_to_mp3

c = MultiTrackComposer(bpm=134.0)
c.set_program(0, 4,  vol=96,  pan=44, rev=38)  # Electric Piano (Rhodes)
c.set_program(1, 36, vol=110, pan=64, rev=14)  # Slap Bass
c.set_program(9, 0,  vol=112, pan=64, rev=24)  # Acoustic Drum Kit
# ... compose 16 bars (64 beats) ...
loop_sec = c.save("track.mid", total_beats=64.0)

render_midi_with_sf2("GeneralUser-GS.sf2", "track.mid", "track.wav", loop_sec=loop_sec)
master_to_mp3("track.wav", "bgm_main.mp3", is_bgm=True, bitrate="64k")
```

### Great General MIDI Instrument Combinations (`GeneralUser-GS.sf2`)
- **Upbeat City-Arcade**: Electric Piano (4) + Slap Bass (36) + Clean Guitar (27) + Brass Section (61) + Saw Lead (81) + Acoustic Drums (Ch 9)
- **High-Energy Action Rock**: Distortion Guitar (30) + Picked Bass (34) + Overdrive Guitar (29) + String Ensemble (48) + Rock Organ (18)
- **Epic Orchestral / Gothic**: Harpsichord (6) + Church Organ (19) + String Ensemble (48) + Choir Aahs (52) + Brass (61) + Timpani (47)
- **Crystalline Fanfare / Chime SFX**: Orchestral Harp (46) ascending glissando + Glockenspiel (9) + Celesta (8) + Warm Strings (48) / Tubular Bells (14)

---

## 3. Native HTML5 `<audio>` Dual-Deck Crossfader & Pooled SFX

Convert embedded base64 MP3s into `Blob` URLs once on first user gesture — works seamlessly over `file://` standalone HTML with zero Web Audio API:

```js
function b64ToBlobUrl(b64) {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return URL.createObjectURL(new Blob([bytes], { type: "audio/mpeg" }));
}

// Smooth crossfade between adaptive BGM tracks in update(dt):
for (const [tier, deck] of Object.entries(bgmPlayers)) {
  const goal = (tier === targetTier) ? masterBgm : 0;
  deck.curVol += Math.sign(goal - deck.curVol) * Math.min(Math.abs(goal - deck.curVol), 1.6 * dt);
  deck.el.volume = Math.max(0, Math.min(1, deck.curVol));
  if (deck.curVol > 0.005) { if (deck.el.paused) deck.el.play().catch(() => {}); }
  else if (!deck.el.paused) { deck.el.pause(); if (tier !== targetTier) deck.el.currentTime = 0; }
}
```

For rapid SFX (footsteps, hits, pickups), maintain a round-robin pool of 2–4 `HTMLAudioElement` instances per sound with cooldown throttling (`30–60ms`), independent `sfxVol`, and subtle `playbackRate` variation (`0.94..1.06`) to keep repeated impacts organic. Always expose **separate BGM and SE volume sliders** persisted to `localStorage`.
