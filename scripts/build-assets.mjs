#!/usr/bin/env node
/**
 * Asset build pipeline — esbuild bundling + minification + content hashing.
 *
 * Bundles static/js/app.js (module graph) and the page-level entry points,
 * emits fingerprinted files to static/dist/, and writes a manifest
 * (static/dist/manifest.json) mapping source paths -> hashed output paths.
 *
 * Usage:  npm run build      (or: node scripts/build-assets.mjs)
 * Dev:    node scripts/build-assets.mjs --watch
 */

import { build, context } from 'esbuild';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SRC_JS = path.join(ROOT, 'static', 'js');
const SRC_CSS = path.join(ROOT, 'static', 'css');
const OUT = path.join(ROOT, 'static', 'dist');

const WATCH = process.argv.includes('--watch');

// Entry points: core app module + per-page scripts under js/pages/**.
function collectEntries() {
  const entries = new Set();
  entries.add(path.join(SRC_JS, 'app.js'));

  const walk = (dir) => {
    for (const f of fs.readdirSync(dir, { withFileTypes: true })) {
      const p = path.join(dir, f.name);
      if (f.isDirectory()) walk(p);
      else if (f.name.endsWith('.js')) entries.add(p);
    }
  };
  walk(path.join(SRC_JS, 'pages'));

  // CSS bundles (minified + hashed, no bundling of imports needed)
  for (const f of fs.readdirSync(SRC_CSS)) {
    if (f.endsWith('.css') && !f.endsWith('.min.css')) entries.add(path.join(SRC_CSS, f));
  }
  return [...entries];
}

// stable name like "pages/reception/queue-3f9a2b1c.js"
function outName(file) {
  const rel = path.relative(file.startsWith(SRC_CSS) ? SRC_CSS : SRC_JS, file);
  return rel.replace(/\.js$|\.css$/, '');
}

async function buildOne(entryFile) {
  const isCss = entryFile.endsWith('.css');
  const base = outName(entryFile);
  const result = await build({
    entryPoints: [entryFile],
    bundle: !isCss,
    minify: true,
    write: false,
    format: isCss ? undefined : 'esm',
    target: ['es2019'],
    charset: 'utf8',
    legalComments: 'none',
    sourcemap: false,
    logLevel: 'silent',
  });

  const content = result.outputFiles[0].contents;
  const hash = createHash('sha256').update(content).digest('hex').slice(0, 10);
  const ext = isCss ? '.css' : '.js';
  const hashedRel = `${base}-${hash}${ext}`;
  const dest = path.join(OUT, hashedRel);

  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.writeFileSync(dest, Buffer.from(content));
  return { [`/static/js/${base}${ext}`.replace('/static/css/', '/static/css/')]: `/static/dist/${hashedRel}` };
}

async function main() {
  fs.rmSync(OUT, { recursive: true, force: true });
  fs.mkdirSync(OUT, { recursive: true });

  const manifest = {};
  const entries = collectEntries();
  console.log(`Building ${entries.length} assets ...`);

  if (!WATCH) {
    for (const e of entries) {
      Object.assign(manifest, await buildOne(e));
    }
  } else {
    // watch mode: rebuild all on change (simple, adequate for dev)
    const ctxs = [];
    for (const e of entries) {
      const ctx = await context({
        entryPoints: [e],
        bundle: !e.endsWith('.css'),
        minify: false,
        write: false,
        format: e.endsWith('.css') ? undefined : 'esm',
        target: ['es2019'],
        charset: 'utf8',
        logLevel: 'silent',
        plugins: [{
          name: 'hash-write',
          setup(b) {
            b.onEnd(async (res) => {
              if (!res.outputFiles?.length) return;
              const content = res.outputFiles[0].contents;
              const hash = createHash('sha256').update(content).digest('hex').slice(0, 10);
              const ext = e.endsWith('.css') ? '.css' : '.js';
              const rel = outName(e);
              const dest = path.join(OUT, `${rel}-dev.${hash}${ext}`);
              fs.mkdirSync(path.dirname(dest), { recursive: true });
              fs.writeFileSync(dest, Buffer.from(content));
            });
          },
        }],
      });
      ctxs.push(ctx);
    }
    await Promise.all(ctxs.map((c) => c.watch()));
    console.log('Watching for changes... (Ctrl+C to stop)');
    return; // keep process alive via esbuild watchers
  }

  fs.writeFileSync(
    path.join(OUT, 'manifest.json'),
    JSON.stringify(manifest, null, 2),
  );
  console.log(`Done -> ${OUT} (${Object.keys(manifest).length} files), manifest.json written`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
