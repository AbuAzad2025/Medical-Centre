import { defineConfig } from 'vitest/config';
import path from 'path';

/**
 * Give the page scripts the global scope they have in a browser.
 *
 * The scripts under static/js are classic scripts: a top-level `function
 * loadDoctors() {}` in a <script> tag becomes a property of the global
 * object, and the pages and the tests both rely on that. A module import
 * does not - a top-level declaration in a module is module-scoped - so
 * importing a page script the way the tests used to import it left the
 * functions unreachable by name.
 *
 * The fix is to restore the classic semantics in the transform, so the
 * declarations the script would have published globally are published
 * globally here too. It runs through Vite's pipeline, which is what the
 * coverage provider instruments - the point of loading the scripts as
 * modules rather than through eval.
 *
 * Only top-level declarations are collected. A declaration that is indented
 * is inside a function or a block, and was never global.
 */
function exposeClassicScriptGlobals() {
  const TOP_LEVEL_DECLARATION =
    /^(?:async\s+function|function|var|let|const|class)\s+([A-Za-z_$][\w$]*)/;

  return {
    name: 'expose-classic-script-globals',
    enforce: 'pre',
    transform(code, id) {
      const path = id.split('?')[0].replace(/\\/g, '/');
      if (!path.includes('/static/js/') || !path.endsWith('.js')) {
        return null;
      }
      if (path.endsWith('.min.js')) {
        return null;
      }

      const names = [];
      for (const line of code.split('\n')) {
        // A top-level declaration starts at column zero. Anything indented
        // is inside a block and was never a global. A byte-order mark
        // counts as column zero - the file starts with one, and the
        // declaration after it is still a top-level one.
        const stripped = line.replace(/^\uFEFF/, '');
        if (/^\s/.test(stripped)) {
          continue;
        }
        const match = TOP_LEVEL_DECLARATION.exec(stripped);
        if (match) {
          names.push(match[1]);
        }
      }
      if (!names.length) {
        return null;
      }
      // Each name is published only if it actually exists here. A file can
      // declare a function at column zero that is really inside an IIFE -
      // indentation is not the same thing as scope - and referencing such a
      // name from here would raise a ReferenceError at import time and take
      // the whole page script down with it.
      const publish = names
        .map(
          (name) =>
            `try { if (typeof ${name} !== 'undefined') globalThis[${JSON.stringify(name)}] = ${name}; } catch (e) {}`,
        )
        .join('\n');
      return {
        code: `${code}\n;${publish}\n`,
        map: null,
      };
    },
  };
}

export default defineConfig({
  plugins: [exposeClassicScriptGlobals()],
  resolve: {
    alias: {
      '@src': path.resolve(__dirname, 'static/js'),
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./tests/frontend/setup.js'],
    include: ['tests/frontend/**/*.test.js', 'tests/frontend/**/*.test.mjs'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      include: ['static/js/**/*.js'],
      exclude: ['static/js/**/*.test.*', 'static/js/**/*.min.js'],
    },
    testTimeout: 10000,
    pool: 'forks',
    server: {
      deps: {
        inline: [/static\/js/],
      },
    },
  },
});


