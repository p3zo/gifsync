/*
 * Draws site/example/bouncing-ball.gif.
 *
 *     node tools/make-example-gif.mjs
 *
 * Needs ffmpeg on the path and nothing else. The example exists to show what retiming
 * does, and how clearly it shows it depends on how many frames sit between one beat and
 * the next: with only a handful, every easing looks much like every other. Two bounces of
 * sixteen gives the curve enough frames to be seen without the loop getting long.
 *
 * The ball hits the ground on frames 0 and 16, which is what site/index.html marks.
 */

import { execFileSync } from "node:child_process";

const SIZE = 96;
const FRAMES_PER_BOUNCE = 16;
const BOUNCES = 2;
const DELAY_CS = 3; // hundredths of a second, which is all a GIF can express

const BG = [0x1e, 0x1b, 0x4b];
const GROUND = [0x4c, 0x1d, 0x95];
const SHADOW = [0x31, 0x2e, 0x81];
const BALL = [0xf4, 0x72, 0xb6];

const GROUND_TOP = 82, GROUND_BOTTOM = 84;
const RADIUS = 15.5;
const REST_Y = GROUND_TOP - RADIUS;   // centre of a round ball just touching the ground
const APEX_Y = RADIUS;                // apex puts the top of the ball at the top of the frame
const SQUASH = { rx: 21.5, ry: 9.5 };

// Averaged down from this many samples a side, which is where the soft edges come from
const SS = 4;

function frame(index) {
  const step = index % FRAMES_PER_BOUNCE;
  const t = step / FRAMES_PER_BOUNCE;
  const height = 4 * t * (1 - t); // 0 on the ground, 1 at the apex

  const impact = step === 0;
  const ball = impact
    ? { cx: SIZE / 2, cy: GROUND_TOP - SQUASH.ry, rx: SQUASH.rx, ry: SQUASH.ry }
    : { cx: SIZE / 2, cy: REST_Y - (REST_Y - APEX_Y) * height, rx: RADIUS, ry: RADIUS };

  // The shadow narrows as the ball climbs, which is the only cue for how high it is
  const shadow = { cx: SIZE / 2, cy: 83, rx: RADIUS - 7 * height, ry: 3.5 };

  const pixels = Buffer.alloc(SIZE * SIZE * 3);
  const inside = (e, x, y) => ((x - e.cx) / e.rx) ** 2 + ((y - e.cy) / e.ry) ** 2 <= 1;

  for (let y = 0; y < SIZE; y++) {
    for (let x = 0; x < SIZE; x++) {
      let r = 0, g = 0, b = 0;
      for (let sy = 0; sy < SS; sy++) {
        for (let sx = 0; sx < SS; sx++) {
          const px = x + (sx + 0.5) / SS;
          const py = y + (sy + 0.5) / SS;
          // painted back to front: the shadow sits on the ground line, the ball over both
          let colour = BG;
          if (py >= GROUND_TOP && py <= GROUND_BOTTOM + 1) colour = GROUND;
          if (inside(shadow, px, py)) colour = SHADOW;
          if (inside(ball, px, py)) colour = BALL;
          r += colour[0]; g += colour[1]; b += colour[2];
        }
      }
      const o = (y * SIZE + x) * 3, n = SS * SS;
      pixels[o] = Math.round(r / n);
      pixels[o + 1] = Math.round(g / n);
      pixels[o + 2] = Math.round(b / n);
    }
  }
  return pixels;
}

const total = FRAMES_PER_BOUNCE * BOUNCES;
const raw = Buffer.concat(Array.from({ length: total }, (_, i) => frame(i)));
const out = new URL("../site/example/bouncing-ball.gif", import.meta.url).pathname;

execFileSync("ffmpeg", [
  "-v", "error", "-y",
  "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", `${SIZE}x${SIZE}`,
  "-r", String(100 / DELAY_CS), "-i", "pipe:0",
  "-filter_complex", "[0:v]split[a][b];[a]palettegen=max_colors=64[p];[b][p]paletteuse=dither=none",
  "-loop", "0", out,
], { input: raw });

console.log(`${out} — ${total} frames, ${SIZE}x${SIZE}, ground on frames 0 and ${FRAMES_PER_BOUNCE}`);
