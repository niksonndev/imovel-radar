/**
 * Records the landing TelegramDemo (same chrome as the site) via Playwright,
 * tight-cropped with no letterboxing, then encodes site-resolution MP4 + GIF
 * to assets/ (GIF for README; MP4 optional for local/social use).
 *
 * Usage (from apps/frontend):
 *   pnpm record:demo
 *
 * Requires: Playwright browsers + ffmpeg on PATH.
 */
import { spawn } from "node:child_process";
import { mkdir, readdir, rename, rm } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND_ROOT = path.resolve(__dirname, "..");
const REPO_ROOT = path.resolve(FRONTEND_ROOT, "../..");
const TMP_DIR = path.join(FRONTEND_ROOT, ".tmp-demo-record");
const ASSETS_DIR = path.join(REPO_ROOT, "assets");
const MP4_PATH = path.join(ASSETS_DIR, "imovel-radar-demo.mp4");
const GIF_PATH = path.join(ASSETS_DIR, "imovel-radar-demo.gif");

/** Keep 1:1 with the site phone shell (no upscale — quality for GIF). */
const OUTPUT_SCALE = 1;
const PORT = 4173;
const BASE_URL = `http://127.0.0.1:${PORT}`;

function run(command, args, opts = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      stdio: "inherit",
      cwd: FRONTEND_ROOT,
      ...opts,
    });
    child.on("error", reject);
    child.on("exit", (code) => {
      if (code === 0) resolve();
      else reject(new Error(`${command} ${args.join(" ")} exited with ${code}`));
    });
  });
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForServer(url, attempts = 60) {
  for (let i = 0; i < attempts; i++) {
    try {
      const res = await fetch(url);
      if (res.ok || res.status === 404) return;
    } catch {
      // retry
    }
    await sleep(500);
  }
  throw new Error(`Server did not become ready at ${url}`);
}

async function ensureBuild() {
  console.log("→ Building static export (out/)…");
  await run("pnpm", ["exec", "next", "build"]);
}

function startStaticServer() {
  const child = spawn(
    "pnpm",
    ["exec", "serve", "out", "-p", String(PORT), "-L"],
    {
      cwd: FRONTEND_ROOT,
      stdio: ["ignore", "pipe", "pipe"],
    },
  );
  child.stdout.on("data", (chunk) => process.stdout.write(chunk));
  child.stderr.on("data", (chunk) => process.stderr.write(chunk));
  return child;
}

async function findWebm(dir) {
  const entries = await readdir(dir);
  const webm = entries.find((name) => name.endsWith(".webm"));
  if (!webm) throw new Error(`No .webm found in ${dir}`);
  return path.join(dir, webm);
}

async function measureShellSize(browser) {
  const page = await browser.newPage({
    viewport: { width: 1280, height: 900 },
    colorScheme: "dark",
    reducedMotion: "no-preference",
  });
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.goto(`${BASE_URL}/demo-record`, { waitUntil: "networkidle" });
  const box = await page.locator("[data-demo-shell]").boundingBox();
  await page.close();
  if (!box) throw new Error("Could not measure [data-demo-shell]");
  return {
    width: Math.ceil(box.width),
    height: Math.ceil(box.height),
  };
}

async function record() {
  await rm(TMP_DIR, { recursive: true, force: true });
  await mkdir(TMP_DIR, { recursive: true });
  await mkdir(ASSETS_DIR, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const { width, height } = await measureShellSize(browser);
  const outW = width * OUTPUT_SCALE;
  const outH = height * OUTPUT_SCALE;
  console.log(
    `→ Phone shell ${width}×${height} → MP4 ${outW}×${outH} (ffmpeg ×${OUTPUT_SCALE})`,
  );

  const context = await browser.newContext({
    viewport: { width, height },
    deviceScaleFactor: 1,
    colorScheme: "dark",
    reducedMotion: "no-preference",
    recordVideo: {
      dir: TMP_DIR,
      size: { width, height },
    },
  });

  const page = await context.newPage();
  await page.emulateMedia({ reducedMotion: "no-preference" });

  console.log(`→ Opening ${BASE_URL}/demo-record …`);
  await page.goto(`${BASE_URL}/demo-record`, { waitUntil: "networkidle" });
  await page.waitForSelector("[data-demo-root][data-demo-state='playing']", {
    timeout: 15_000,
  });
  console.log("→ Recording until demo completes…");
  await page.waitForSelector("[data-demo-root][data-demo-state='complete']", {
    timeout: 90_000,
  });
  await sleep(600);

  await context.close();
  await browser.close();

  const webmPath = await findWebm(TMP_DIR);
  const stagedWebm = path.join(TMP_DIR, "demo.webm");
  await rename(webmPath, stagedWebm);

  console.log("→ Encoding MP4 (H.264, site resolution)…");
  const mp4Args = ["-y", "-i", stagedWebm];
  if (OUTPUT_SCALE !== 1) {
    mp4Args.push("-vf", `scale=${outW}:${outH}:flags=lanczos`);
  }
  mp4Args.push(
    "-c:v",
    "libx264",
    "-pix_fmt",
    "yuv420p",
    "-movflags",
    "+faststart",
    "-an",
    MP4_PATH,
  );
  await run("ffmpeg", mp4Args);

  console.log("→ Encoding GIF (palette, site resolution)…");
  const palettePath = path.join(TMP_DIR, "palette.png");
  await run("ffmpeg", [
    "-y",
    "-i",
    MP4_PATH,
    "-vf",
    "fps=10,palettegen=stats_mode=diff",
    palettePath,
  ]);
  await run("ffmpeg", [
    "-y",
    "-i",
    MP4_PATH,
    "-i",
    palettePath,
    "-lavfi",
    "fps=10,paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle",
    "-loop",
    "0",
    GIF_PATH,
  ]);

  await rm(TMP_DIR, { recursive: true, force: true });
  console.log(`✓ Wrote ${path.relative(REPO_ROOT, MP4_PATH)}`);
  console.log(`✓ Wrote ${path.relative(REPO_ROOT, GIF_PATH)}`);
}

async function main() {
  await ensureBuild();
  const server = startStaticServer();
  try {
    await waitForServer(`${BASE_URL}/demo-record`);
    await record();
  } finally {
    server.kill("SIGTERM");
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
