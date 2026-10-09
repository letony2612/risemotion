// Chromium text renderer for tools/retext.py: node tools/retext_render.mjs jobs.json
// jobs.json: [{out, width, height, background (png path or null), fonts: [{family, weight, style, file}],
//              items: [{html, style}]}] -> one PNG per job, transparent where there is no background.
// Playwright is taken from $PLAYWRIGHT, else from the usual global install.
import { createRequire } from "module";
import fs from "fs";
import path from "path";

const require = createRequire(import.meta.url);
const pw = require(process.env.PLAYWRIGHT || "/opt/node-tools/node_modules/playwright");

const jobs = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const browser = await pw.chromium.launch({ args: ["--allow-file-access-from-files", "--font-render-hinting=none"] });
const page = await browser.newPage({ deviceScaleFactor: 1 });
const fonts = {};
const dataUri = (f) => (fonts[f] ??= `data:font/woff2;base64,${fs.readFileSync(f).toString("base64")}`);
for (const job of jobs) {
  await page.setViewportSize({ width: job.width, height: job.height });
  const faces = (job.fonts || []).map((f) =>
    `@font-face{font-family:"${f.family}";font-weight:${f.weight};font-style:${f.style};src:url(${dataUri(f.file)}) format("woff2");}`).join("");
  const bg = job.background ? `<img src="file://${path.resolve(job.background)}" style="position:absolute;left:0;top:0">` : "";
  const items = job.items.map((it) => `<div style="position:absolute;white-space:pre-wrap;${it.style}">${it.html}</div>`).join("");
  const html = `<!doctype html><html><head><meta charset="utf-8"><style>${faces}html,body{margin:0;background:transparent;` +
    `overflow:hidden;-webkit-font-smoothing:antialiased;text-rendering:geometricPrecision}</style></head><body>${bg}${items}</body></html>`;
  const tmp = path.resolve(job.out + ".html");
  fs.writeFileSync(tmp, html);
  await page.goto("file://" + tmp);
  await page.evaluate(() => document.fonts.ready);
  await page.waitForFunction(() => [...document.images].every((i) => i.complete));
  await page.screenshot({ path: job.out, omitBackground: true, clip: { x: 0, y: 0, width: job.width, height: job.height } });
  fs.unlinkSync(tmp);
}
await browser.close();
