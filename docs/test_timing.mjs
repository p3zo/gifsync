// Checks the retiming in docs/index.html against the one in sync.py. The browser path
// reimplements get_durations, so the two have to be diffed or they will drift apart.
//
//   node docs/test_timing.mjs

import { readFileSync, writeFileSync, mkdtempSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repo = join(here, "..");
const python = process.env.PYTHON || "python3";

// Pull the shared region out of the page so the test runs against the shipped bytes
const page = readFileSync(join(here, "index.html"), "utf8");
const start = page.indexOf("/* --- timing:start");
const end = page.indexOf("/* --- timing:end");
if (start < 0 || end < 0) throw new Error("timing sentinels not found in index.html");

const scratch = mkdtempSync(join(tmpdir(), "gifsync-timing-"));
const modulePath = join(scratch, "timing.mjs");
writeFileSync(modulePath, page.slice(start, end));
const { getDurations, getFrameOrder } = await import(modulePath);

const CASES = [];
for (const interpolation of ["linear", "quadratic", "cubic"]) {
  for (const beats of [[0], [7], [0, 5, 10], [2, 6], [3, 8, 13], [1, 4, 9, 14], [0, 1, 15]]) {
    for (const msPerBeat of [500, 333.3333333333333, 1234.5]) {
      CASES.push({ interpolation, beats, msPerBeat, nFrames: 16 });
    }
  }
}
CASES.push({ interpolation: "linear", beats: [0, 9, 17, 28, 36, 45, 54, 63, 72, 81], msPerBeat: 500, nFrames: 91 });
CASES.push({ interpolation: "cubic", beats: [9, 17, 28, 36, 45, 54, 63, 72, 81], msPerBeat: 517.24, nFrames: 91 });

// sync.py imports essentia at module scope, so run get_durations from its source instead
const driver = `
import contextlib, json, sys, types
essentia = types.ModuleType("essentia")
essentia.standard = types.ModuleType("essentia.standard")
sys.modules["essentia"], sys.modules["essentia.standard"] = essentia, essentia.standard
sys.path.insert(0, ${JSON.stringify(repo)})
from sync import get_durations, get_frame_order

out = []
# get_durations warns on stdout, which would land in the middle of the JSON
with contextlib.redirect_stdout(sys.stderr):
    for case in json.load(sys.stdin):
        out.append({
            "durations": [float(d) for d in get_durations(
                case["beats"], case["msPerBeat"], case["nFrames"], case["interpolation"])],
            "order": get_frame_order(case["beats"][0], case["nFrames"]),
        })
json.dump(out, sys.stdout)
`;

const expected = JSON.parse(execFileSync(python, ["-c", driver], {
  input: JSON.stringify(CASES), encoding: "utf8", maxBuffer: 1 << 26,
}));

let failures = 0;
CASES.forEach((c, i) => {
  const durations = getDurations(c.beats, c.msPerBeat, c.nFrames, c.interpolation);
  const order = getFrameOrder(c.beats[0], c.nFrames);
  const want = expected[i];

  const worst = Math.max(...durations.map((d, j) => Math.abs(d - want.durations[j])));
  const orderMatches = order.length === want.order.length && order.every((f, j) => f === want.order[j]);
  const ok = durations.length === want.durations.length && worst < 1e-9 && orderMatches;

  if (!ok) {
    failures++;
    console.log(`FAIL ${c.interpolation} beats=[${c.beats}] msPerBeat=${c.msPerBeat} nFrames=${c.nFrames}`);
    console.log(`  js  ${durations.slice(0, 8).map((d) => d.toFixed(6))}`);
    console.log(`  py  ${want.durations.slice(0, 8).map((d) => d.toFixed(6))}`);
    console.log(`  worst delta ${worst}, order matches: ${orderMatches}`);
  }
});

// The rejections have to line up too, or the browser accepts input the CLI refuses
const BAD = [[], [0, 4, 4, 8], [8, 2, 12], [0, 5, 20], [-1, 3]];
for (const beats of BAD) {
  let threw = false;
  try { getDurations(beats, 500, 16, "linear"); } catch { threw = true; }
  if (!threw) { failures++; console.log(`FAIL [${beats}] was accepted by the JS but not by sync.py`); }
}

console.log(`${CASES.length} timing cases + ${BAD.length} rejection cases, ${failures} failures`);
process.exit(failures ? 1 : 0);
