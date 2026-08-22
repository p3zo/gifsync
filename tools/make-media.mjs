/*
 * Regenerates site/media/ from the page itself, so the link preview always shows what the
 * tool currently does rather than what it did when someone last took a screenshot.
 *
 * Needs a checkout served over http — WebCodecs is refused on file:// — and a Chromium
 * that has WebCodecs, which the headless shell does not:
 *
 *     python3 -m http.server 8731 --directory site &
 *     npx playwright@1.62 install chromium
 *     npx --yes --package playwright@1.62 node tools/make-media.mjs
 *
 * ffmpeg does the two things the page cannot: scaling the 96x96 example up to a size that
 * reads in a link preview, and flattening the card back down from 2x.
 */

import { execFileSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { chromium } from "playwright";

const BASE = process.env.GIFSYNC_URL ?? "http://localhost:8731";
const OUT = new URL("../site/media/", import.meta.url).pathname;
const TMP = new URL("../.media-tmp/", import.meta.url).pathname;

mkdirSync(OUT, { recursive: true });
mkdirSync(TMP, { recursive: true });

const browser = await chromium.launch({ channel: "chromium" });

async function loaded(page, settings = {}) {
  await page.goto(BASE + "/", { waitUntil: "load" });
  await page.locator("#exampleBtn").click();
  await page.waitForFunction(() => document.getElementById("previewCanvas").width > 1, null, { timeout: 20000 });
  // the tempo estimate arrives seconds after the song and puts the marks on the waveform
  await page.waitForTimeout(4000);
  for (const [id, value] of Object.entries(settings)) {
    // some of these sit under the collapsed "More controls" fold, and a select inside a
    // closed <details> cannot be clicked
    await page.evaluate((id) => document.getElementById(id).closest("details")?.setAttribute("open", ""), id);
    await page.selectOption("#" + id, value);
  }
  await page.evaluate(() => document.querySelectorAll(".toast").forEach((t) => t.remove()));
}

// The eased setting, because a link preview gets a second of someone's attention and the
// snap on the beat is the thing worth spending it on.
const render = await browser.newPage();
await loaded(render, { interpolation: "cubic" });
const download = render.waitForEvent("download", { timeout: 120000 });
await render.locator("#renderBrowserBtn").click();
await (await download).saveAs(TMP + "render.mp4");
await render.close();

// Nearest-neighbour because the example is pixel art and any smoothing turns it to mush
execFileSync("ffmpeg", ["-v", "error", "-y", "-i", TMP + "render.mp4",
  "-vf", "scale=384:384:flags=neighbor", "-c:v", "libx264", "-preset", "slow", "-crf", "23",
  "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", OUT + "demo.mp4"]);
console.log("demo.mp4");

// The card is composed rather than screenshotted whole: a screenshot of the page is
// unreadable at the size a link preview is actually shown at. The pixels in it are still
// the real thing, the gif as the page draws it and the song's own marked waveform.
const shots = await browser.newPage({ viewport: { width: 1250, height: 1000 }, deviceScaleFactor: 3, colorScheme: "dark" });
await loaded(shots);
await shots.locator("#previewCanvas").screenshot({ path: TMP + "gif.png" });
await shots.locator("#wave").screenshot({ path: TMP + "wave.png" });
await shots.close();

writeFileSync(TMP + "card.html", `<!doctype html><meta charset="utf-8"><style>
  html,body{margin:0}
  body{width:1200px;height:630px;background:#131316;color:#ececf0;overflow:hidden;
    font:400 15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;
    display:flex;flex-direction:column;justify-content:space-between;padding:56px 60px;box-sizing:border-box}
  .mark{font-size:22px;font-weight:700;letter-spacing:.02em;color:#f06595}
  h1{font-size:60px;line-height:1.05;letter-spacing:-.025em;margin:22px 0 0;max-width:20ch}
  p{font-size:24px;color:#9a9aa6;margin:18px 0 0}
  .art{display:flex;align-items:flex-end;gap:26px}
  .art img.gif{width:170px;height:170px;border-radius:12px;flex:none;object-fit:cover}
  .art img.wave{flex:1;min-width:0;height:170px;object-fit:cover;object-position:left center;
    border-radius:12px;background:#1c1c21}
</style>
<div>
  <div class="mark">Gifsync</div>
  <h1>Sync a GIF to the beat of a song</h1>
  <p>Free, in your browser. Nothing is uploaded.</p>
</div>
<div class="art"><img class="gif" src="gif.png"><img class="wave" src="wave.png"></div>`);

const card = await browser.newPage({ viewport: { width: 1200, height: 630 }, deviceScaleFactor: 2 });
await card.goto("file://" + TMP + "card.html", { waitUntil: "load" });
await card.screenshot({ path: TMP + "card.png" });
await card.close();
await browser.close();

execFileSync("ffmpeg", ["-v", "error", "-y", "-i", TMP + "card.png",
  "-vf", "scale=1200:630:flags=lanczos", OUT + "social-card.png"]);
console.log("social-card.png");
