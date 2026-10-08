import { readFileSync } from 'fs';
import { resolve } from 'path';
import { pathToFileURL } from 'url';
import { vi } from 'vitest';

const ROOT = resolve(import.meta.dirname, '../..');

/**
 * Load a page script for real, so the coverage provider can see it.
 *
 * The original helper read the file and called `eval` on it. That works for
 * asserting "this script does not throw", and it is why 318 frontend tests
 * reported 0.45% line coverage: `eval` bypasses the module pipeline entirely, so
 * the v8 provider never instruments the code that actually runs. The tests were
 * real but the measurement was empty.
 *
 * Dynamic `import` goes through the module runner, which is what v8 instruments.
 * `vi.resetModules` clears the registry between tests so a script that attaches
 * listeners to the document is re-executed against a fresh DOM.
 *
 * These page files are IIFE scripts with no exports; importing them runs the IIFE
 * and leaves its handlers attached to the document, which is the behaviour the
 * tests drive.
 */
export async function loadModule(relativePath) {
  const filePath = resolve(ROOT, relativePath);
  vi.resetModules();
  return import(pathToFileURL(filePath).href);
}

/**
 * The original eval-based loader, kept so the distinction stays visible and so a
 * test can assert that a script still parses without claiming coverage.
 */
export function loadScript(relativePath) {
  const filePath = resolve(ROOT, relativePath);
  const code = readFileSync(filePath, 'utf-8');
  (0, eval)(code);
}

export { ROOT };