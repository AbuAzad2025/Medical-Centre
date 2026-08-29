import { readFileSync } from 'fs';
import { resolve } from 'path';
import { vi } from 'vitest';

const ROOT = resolve(import.meta.dirname, '../..');

export function loadScript(relativePath) {
  const filePath = resolve(ROOT, relativePath);
  const code = readFileSync(filePath, 'utf-8');
  (0, eval)(code);
}

export { ROOT };
