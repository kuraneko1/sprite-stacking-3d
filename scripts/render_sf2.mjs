/**
 * Offline Multi-Sampled SoundFont2 (.sf2 / .sf3) MIDI -> WAV Renderer using `spessasynth_core`.
 *
 * Seamless loop mode: when `loop_sec > 0`, renders 2 full cycles and slices [loop_sec, 2*loop_sec]
 * so natural reverb/chorus tails wrap cleanly across the loop boundary with zero click!
 *
 * Setup:
 *   npm install spessasynth_core
 *
 * Usage:
 *   node render_sf2.mjs <soundfont.sf2> <track.mid> <out.wav> [loop_sec] [tail_sec]
 */
import fs from "fs";
import path from "path";
import {
  SoundBankLoader,
  SpessaSynthProcessor,
  SpessaSynthSequencer,
  BasicMIDI,
  audioToWav,
} from "spessasynth_core";

const args = process.argv.slice(2);
if (args.length < 3) {
  console.error("Usage: node render_sf2.mjs <sf2_path> <midi_path> <wav_out> [loop_sec] [tail_sec]");
  process.exit(1);
}

const [sf2Path, midiPath, wavOut] = args;
const loopSec = args[3] ? parseFloat(args[3]) : 0;
const tailSec = args[4] ? parseFloat(args[4]) : 0.8;

const sampleRate = 44100;
const sf2Buf = fs.readFileSync(sf2Path);
const midiBuf = fs.readFileSync(midiPath);

const bank = SoundBankLoader.fromArrayBuffer(
  sf2Buf.buffer.slice(sf2Buf.byteOffset, sf2Buf.byteOffset + sf2Buf.byteLength)
);
const synth = new SpessaSynthProcessor(sampleRate);
await synth.ready;
synth.soundBankManager.addSoundBank(bank, "main");

const midi = BasicMIDI.fromArrayBuffer(
  midiBuf.buffer.slice(midiBuf.byteOffset, midiBuf.byteOffset + midiBuf.byteLength),
  path.basename(midiPath)
);

const seq = new SpessaSynthSequencer(synth);
seq.loadNewSongList([midi]);

let totalSec, sliceStartSec, sliceLenSec;
if (loopSec > 0) {
  seq.loopCount = 2;
  totalSec = loopSec * 2 + 0.25;
  sliceStartSec = loopSec;
  sliceLenSec = loopSec;
} else {
  seq.loopCount = 0;
  totalSec = Math.max(0.25, midi.duration + tailSec);
  sliceStartSec = 0;
  sliceLenSec = totalSec;
}

seq.play();

const totalSamples = Math.ceil(totalSec * sampleRate);
const outL = new Float32Array(totalSamples);
const outR = new Float32Array(totalSamples);
const BLOCK = 128;

let filled = 0;
while (filled < totalSamples) {
  seq.processTick();
  const n = Math.min(BLOCK, totalSamples - filled);
  synth.process(outL, outR, filled, n);
  filled += n;
}

const s0 = Math.floor(sliceStartSec * sampleRate);
const sLen = Math.floor(sliceLenSec * sampleRate);
const finalL = outL.subarray(s0, Math.min(totalSamples, s0 + sLen));
const finalR = outR.subarray(s0, Math.min(totalSamples, s0 + sLen));

if (loopSec > 0) {
  const fadeN = Math.min(180, Math.floor(finalL.length / 4));
  for (let i = 0; i < fadeN; i++) {
    const t = i / fadeN;
    const j = finalL.length - fadeN + i;
    finalL[i] = finalL[i] * t + finalL[j] * (1 - t);
    finalR[i] = finalR[i] * t + finalR[j] * (1 - t);
  }
}

const wavBuf = audioToWav([finalL, finalR], sampleRate, { normalizeAudio: false });
fs.writeFileSync(wavOut, Buffer.from(wavBuf));
console.log(`Rendered ${path.basename(wavOut)} (${(finalL.length / sampleRate).toFixed(2)}s)`);
