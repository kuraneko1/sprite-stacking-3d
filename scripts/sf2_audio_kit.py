"""Reusable Multi-Sampled SoundFont2 + Spotify Pedalboard Audio Mastering Kit.

Pipeline:
  1. Compose multi-track MIDI with `MultiTrackComposer` (requires `mido`)
  2. Render via `render_sf2.mjs` + `spessasynth_core` + a GM SoundFont (e.g. GeneralUser-GS.sf2)
  3. Master stereo audio with Spotify `pedalboard` (HPF, Shelf EQ, Compressor, Peak Limiter)
  4. Encode compact stereo MP3 via `ffmpeg` for native HTML5 `<audio>` playback
"""
import subprocess
from pathlib import Path
import numpy as np

TPB = 480


class MultiTrackComposer:
    """Clean beat-based multi-channel MIDI composer."""

    def __init__(self, bpm: float):
        self.bpm = bpm
        self.events = []

    def set_program(self, ch: int, prog: int, vol: int = 100, pan: int = 64, rev: int = 40, cho: int = 20):
        from mido import Message
        self.events.append((0, 0, Message("program_change", channel=ch, program=prog, time=0)))
        self.events.append((0, 1, Message("control_change", channel=ch, control=7, value=vol, time=0)))
        self.events.append((0, 2, Message("control_change", channel=ch, control=10, value=pan, time=0)))
        self.events.append((0, 3, Message("control_change", channel=ch, control=91, value=rev, time=0)))
        self.events.append((0, 4, Message("control_change", channel=ch, control=93, value=cho, time=0)))

    def note(self, ch: int, pitch: int, start_beat: float, dur_beat: float, vel: int = 96):
        from mido import Message
        t0 = max(0, int(round(start_beat * TPB)))
        t1 = max(t0 + 10, int(round((start_beat + dur_beat) * TPB)))
        v = int(np.clip(vel, 1, 127))
        p = int(np.clip(pitch, 0, 127))
        self.events.append((t0, 20, Message("note_on", channel=ch, note=p, velocity=v, time=0)))
        self.events.append((t1, 10, Message("note_off", channel=ch, note=p, velocity=0, time=0)))

    def chord(self, ch: int, pitches, start_beat: float, dur_beat: float, vel: int = 86, strum: float = 0.0):
        for idx, p in enumerate(pitches):
            self.note(ch, p, start_beat + idx * strum, max(0.08, dur_beat - idx * strum), vel)

    def save(self, path: str | Path, total_beats: float | None = None) -> float:
        import mido
        from mido import MidiFile, MidiTrack, MetaMessage
        mid = MidiFile(ticks_per_beat=TPB)
        tr = MidiTrack()
        mid.tracks.append(tr)
        tr.append(MetaMessage("set_tempo", tempo=mido.bpm2tempo(self.bpm), time=0))

        self.events.sort(key=lambda x: (x[0], x[1]))
        last_tick = 0
        for tick, _, msg in self.events:
            tr.append(msg.copy(time=tick - last_tick))
            last_tick = tick

        if total_beats is not None:
            end_tick = int(round(total_beats * TPB))
            tr.append(MetaMessage("end_of_track", time=max(0, end_tick - last_tick)))
        else:
            tr.append(MetaMessage("end_of_track", time=0))

        mid.save(str(path))
        return (total_beats or (last_tick / TPB)) * 60.0 / self.bpm


def render_midi_with_sf2(
    sf2_path: str | Path,
    midi_path: str | Path,
    wav_out: str | Path,
    loop_sec: float = 0.0,
    tail_sec: float = 0.7,
    render_script: str | Path | None = None,
):
    """Render a MIDI file to stereo 44.1kHz WAV via render_sf2.mjs + spessasynth_core."""
    script = Path(render_script) if render_script else (Path(__file__).parent / "render_sf2.mjs")
    cmd = ["node", str(script), str(sf2_path), str(midi_path), str(wav_out), str(loop_sec), str(tail_sec)]
    subprocess.run(cmd, check=True)


def master_to_mp3(
    wav_in: str | Path,
    mp3_out: str | Path,
    is_bgm: bool = True,
    bitrate: str = "64k",
):
    """Master a stereo WAV through Spotify Pedalboard EQ/Compressor/Limiter and encode MP3 via ffmpeg."""
    from scipy.io import wavfile
    from pedalboard import Pedalboard, Compressor, HighpassFilter, HighShelfFilter, LowShelfFilter, Limiter, Gain

    wav_in = Path(wav_in)
    mp3_out = Path(mp3_out)
    mp3_out.parent.mkdir(parents=True, exist_ok=True)

    sr, data = wavfile.read(str(wav_in))
    if data.dtype == np.int16:
        audio = data.astype(np.float32) / 32768.0
    elif data.dtype == np.int32:
        audio = data.astype(np.float32) / 2147483648.0
    else:
        audio = data.astype(np.float32)
    if audio.ndim == 1:
        audio = np.stack([audio, audio], axis=1)

    ch_first = audio.T.copy()
    if is_bgm:
        board = Pedalboard([
            HighpassFilter(cutoff_frequency_hz=32.0),
            LowShelfFilter(cutoff_frequency_hz=110.0, gain_db=2.2),
            HighShelfFilter(cutoff_frequency_hz=6800.0, gain_db=2.0),
            Compressor(threshold_db=-16.0, ratio=3.0, attack_ms=8.0, release_ms=90.0),
            Gain(gain_db=3.2),
            Limiter(threshold_db=-1.2, release_ms=60.0),
        ])
    else:
        board = Pedalboard([
            HighpassFilter(cutoff_frequency_hz=50.0),
            HighShelfFilter(cutoff_frequency_hz=5500.0, gain_db=2.5),
            Compressor(threshold_db=-14.0, ratio=2.6, attack_ms=4.0, release_ms=60.0),
            Gain(gain_db=3.5),
            Limiter(threshold_db=-1.0, release_ms=40.0),
        ])

    mastered = board(ch_first, sr)
    peak = float(np.max(np.abs(mastered))) + 1e-9
    mastered = np.clip(mastered * ((0.89 if is_bgm else 0.92) / peak), -1.0, 1.0)

    if is_bgm:
        fade_n = min(160, mastered.shape[1] // 8)
        t = np.linspace(0.0, 1.0, fade_n, dtype=np.float32)
        mastered[:, :fade_n] = mastered[:, :fade_n] * t + mastered[:, -fade_n:] * (1.0 - t)

    mastered_wav = wav_in.with_suffix(".master.wav")
    wavfile.write(str(mastered_wav), sr, (mastered.T * 32767.0).astype(np.int16))

    subprocess.run([
        "ffmpeg", "-y", "-v", "error",
        "-i", str(mastered_wav),
        "-c:a", "libmp3lame", "-b:a", bitrate, "-ar", "44100", "-ac", "2",
        str(mp3_out),
    ], check=True)
