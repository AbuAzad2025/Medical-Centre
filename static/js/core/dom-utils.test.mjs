import { test } from 'node:test';
import assert from 'node:assert/strict';
import { escHtml, debounce, digitsOnly, formatMoney } from './dom-utils.js';

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

test('escHtml escapes & < > " \' correctly', () => {
  assert.equal(escHtml('a & b<c>"d"<\'e\'>'), 'a &amp; b&lt;c&gt;&quot;d&quot;&lt;&#39;e&#39;&gt;');
});

test('escHtml passes Arabic content through', () => {
  assert.equal(escHtml('مركز طبي'), 'مركز طبي');
});

test('escHtml handles null, undefined and numbers', () => {
  assert.equal(escHtml(null), '');
  assert.equal(escHtml(undefined), '');
  assert.equal(escHtml(42), '42');
});

test('debounce fires once for rapid calls', async () => {
  let calls = 0;
  const fn = debounce(() => {
    calls += 1;
  }, 20);
  fn();
  fn();
  fn();
  await sleep(50);
  assert.equal(calls, 1);
});

test("digitsOnly '12ab34' -> '1234'", () => {
  assert.equal(digitsOnly('12ab34'), '1234');
});

test("digitsOnly 'abcdefgh' -> ''", () => {
  assert.equal(digitsOnly('abcdefgh'), '');
});

test('digitsOnly null -> empty string', () => {
  assert.equal(digitsOnly(null), '');
});

test('digitsOnly caps at 4 keeping first chars', () => {
  assert.equal(digitsOnly('1234567890'), '1234');
});

test('formatMoney basic cases', () => {
  assert.equal(formatMoney(5), '5.00');
  assert.equal(formatMoney(2.345), '2.35');
  assert.equal(formatMoney(-1.5), '-1.50');
});
