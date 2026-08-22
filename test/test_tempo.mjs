// Checks the tempo front end in site/index.html against test/tempo_cases.json.
//
// The model only gives the right answer if it is fed the features it was trained on, and
// those are essentia's TensorflowInputTempoCNN. The expected values were recorded from
// essentia while it was still in the tree, so a change to the windowing, the FFT or the
// mel filterbank fails here rather than quietly returning a plausible wrong tempo.
//
//   node test/test_tempo.mjs

import { readFileSync, writeFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));

const page = readFileSync(join(here, "..", "site", "index.html"), "utf8");
const start = page.indexOf("/* --- tempo:start");
const end = page.indexOf("/* --- tempo:end");
if (start < 0 || end < 0) throw new Error("tempo sentinels not found in index.html");

const scratch = mkdtempSync(join(tmpdir(), "gifsync-tempo-"));
const modulePath = join(scratch, "tempo.mjs");
writeFileSync(modulePath, page.slice(start, end));
const { melSpectrogram, TEMPO_BANDS, TEMPO_SR } = await import(modulePath);

const expected = JSON.parse(readFileSync(join(here, "tempo_cases.json"), "utf8"));

if (TEMPO_SR !== expected.input.sampleRate) {
  console.log(`FAIL sample rate is ${TEMPO_SR}, the reference was taken at ${expected.input.sampleRate}`);
  process.exit(1);
}

// Same signal essentia was given; only its output needed recording
const signal = Float64Array.from({ length: expected.input.samples }, (_, i) =>
  0.5 * Math.sin((2 * Math.PI * (220 * i + 0.005 * i * i)) / TEMPO_SR) +
  0.25 * Math.sin((2 * Math.PI * 1300 * i) / TEMPO_SR) +
  0.1 * Math.sin((2 * Math.PI * 3700 * i) / TEMPO_SR));

const mel = melSpectrogram(signal);

let failures = 0;
if (mel.length !== expected.melFrames) {
  failures++;
  console.log(`FAIL produced ${mel.length} mel frames, expected ${expected.melFrames}`);
}

// essentia computes in float32, so the two agree to about a part in ten million rather
// than exactly. Errors are measured against the largest value in the matrix: the quiet
// bands sit near 1e-7, where a relative error says nothing useful.
const TOLERANCE = 1e-5;
let worst = 0, worstAt = null;
for (let f = 0; f < Math.min(mel.length, expected.melFrames); f++) {
  if (mel[f].length !== TEMPO_BANDS) {
    failures++;
    console.log(`FAIL frame ${f} has ${mel[f].length} bands, expected ${TEMPO_BANDS}`);
    continue;
  }
  for (let b = 0; b < TEMPO_BANDS; b++) {
    const want = expected.mel[f][b];
    const err = Math.abs(mel[f][b] - want) / expected.melMax;
    if (err > worst) { worst = err; worstAt = { f, b, got: mel[f][b], want }; }
  }
}

if (worst > TOLERANCE) {
  failures++;
  console.log(`FAIL worst error ${worst.toExponential(3)} of full scale exceeds ${TOLERANCE.toExponential(0)}`);
  console.log(`  frame ${worstAt.f} band ${worstAt.b}: got ${worstAt.got}, want ${worstAt.want}`);
}

console.log(`${expected.melFrames} mel frames x ${TEMPO_BANDS} bands vs essentia, ` +
  `worst error ${worst.toExponential(2)} of full scale, ${failures} failures`);
process.exit(failures ? 1 : 0);
