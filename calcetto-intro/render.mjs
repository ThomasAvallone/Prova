// Renders index.html frame-by-frame with headless Chromium and pipes it to ffmpeg.
//   node render.mjs --cues build/cues.json
//   node render.mjs --shots 1.2,4.5,13 --out build/shots
//   node render.mjs --video calcetto-intro.mp4 --audio build/audio.wav
import { chromium } from 'playwright-core';
import { spawn } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const opt = (k, d) => { const i = args.indexOf('--' + k); return i >= 0 ? args[i + 1] : d; };
const FPS = Number(opt('fps', process.env.FPS || 60));
const W = 1920, H = 1080;

const browser = await chromium.launch({ args: ['--force-device-scale-factor=1', '--hide-scrollbars', '--font-render-hinting=none'] });
const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
page.on('pageerror', e => console.error('PAGE ERROR:', e.message));
page.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') console.error('console.' + m.type() + ':', m.text()); });
await page.goto(pathToFileURL(resolve(here, 'index.html')).href + '?render');
await page.waitForFunction('window.__ready === true', null, { timeout: 30000 });
const duration = await page.evaluate('window.__duration');

const shot = async t => { await page.evaluate(t => window.__seek(t), t); return page.screenshot({ type: 'png' }); };

if (opt('cues')) {
  const cues = await page.evaluate('window.__cues');
  mkdirSync(dirname(resolve(opt('cues'))), { recursive: true });
  writeFileSync(resolve(opt('cues')), JSON.stringify({ duration, cues }, null, 1));
  console.log(`cues: ${cues.length}, duration ${duration}s -> ${opt('cues')}`);
}

if (opt('shots')) {
  const out = resolve(opt('out', 'build/shots'));
  mkdirSync(out, { recursive: true });
  for (const t of opt('shots').split(',').map(Number)) {
    writeFileSync(`${out}/t${t.toFixed(2).padStart(5, '0')}.png`, await shot(t));
  }
  console.log('shots ->', out);
}

if (opt('video')) {
  const outFile = resolve(opt('video'));
  const audio = opt('audio');
  const ff = spawn('ffmpeg', [
    '-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'png', '-i', '-',
    ...(audio ? ['-i', resolve(audio)] : []),
    '-vf', 'scale=out_color_matrix=bt709:out_range=tv,format=yuv420p',
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '15', '-r', String(FPS),
    '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709',
    ...(audio ? ['-c:a', 'aac', '-b:a', '256k', '-shortest'] : ['-an']),
    '-movflags', '+faststart', outFile,
  ], { stdio: ['pipe', 'inherit', 'inherit'] });
  const done = new Promise((res, rej) => { ff.on('close', c => c === 0 ? res() : rej(new Error('ffmpeg exited ' + c))); });
  const total = Math.round(duration * FPS);
  const t0 = Date.now();
  for (let i = 0; i < total; i++) {
    const buf = await shot(i / FPS);
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    if (i % 60 === 0) console.log(`frame ${i}/${total}  (${((Date.now() - t0) / 1000).toFixed(0)}s)`);
  }
  ff.stdin.end();
  await done;
  console.log(`video -> ${outFile}  (${total} frames @ ${FPS}fps, ${((Date.now() - t0) / 1000).toFixed(0)}s)`);
}
await browser.close();
