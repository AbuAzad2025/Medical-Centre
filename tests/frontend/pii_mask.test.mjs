import { describe, it, expect, vi, beforeEach } from 'vitest';
import { loadScript } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = '';
  loadScript('static/js/utils/pii_mask.js');
});

const PiiMask = () => window.PiiMask;

describe('PiiMask', () => {
  describe('maskNationalId', () => {
    it('masks 9-digit national ID (first 3 + X + last 1)', () => {
      expect(PiiMask().nationalId('123456789')).toBe('123XXXXX9');
    });
    it('masks 14-digit national ID (first 3 + X + last 1)', () => {
      expect(PiiMask().nationalId('12345678901234')).toBe('123XXXXXXXXXX4');
    });
    it('returns XXXX for IDs 4 chars or less', () => {
      expect(PiiMask().nationalId('1234')).toBe('XXXX');
    });
    it('returns empty for empty string', () => {
      expect(PiiMask().nationalId('')).toBe('');
    });
    it('returns empty for null', () => {
      expect(PiiMask().nationalId(null)).toBe('');
    });
  });

  describe('maskPhone', () => {
    it('masks UAE format phone keeping + and last 4', () => {
      const result = PiiMask().phone('+971501234567');
      expect(result).toMatch(/\+.*4567$/);
      expect(result).toContain('X');
    });
    it('masks international phone', () => {
      const result = PiiMask().phone('1234567890');
      expect(result).toMatch(/X.*7890$/);
    });
    it('returns XXX for too short', () => {
      expect(PiiMask().phone('12')).toBe('XXX');
    });
    it('returns empty for null', () => {
      expect(PiiMask().phone(null)).toBe('');
    });
  });

  describe('maskName', () => {
    it('masks single word name', () => {
      expect(PiiMask().name('John')).toBe('JXXX');
    });
    it('masks multi-word name keeping last word', () => {
      expect(PiiMask().name('John Smith')).toBe('JXXX Smith');
    });
    it('masks Arabic name', () => {
      expect(PiiMask().name('أحمد محمد')).toBe('أXXX محمد');
    });
    it('returns empty for null', () => {
      expect(PiiMask().name(null)).toBe('');
    });
  });

  describe('maskEmail', () => {
    it('masks valid email', () => {
      expect(PiiMask().email('john@example.com')).toBe('j***n@example.com');
    });
    it('masks short local part', () => {
      expect(PiiMask().email('ab@example.com')).toBe('a***@example.com');
    });
    it('returns value if no @', () => {
      expect(PiiMask().email('invalid')).toBe('invalid');
    });
    it('returns empty for null', () => {
      expect(PiiMask().email(null)).toBe('');
    });
  });

  describe('toggleReveal', () => {
    beforeEach(() => {
      document.body.innerHTML = `
        <div>
          <span class="pii-visible" data-masked="true">123XXXXX9</span>
          <button class="reveal-btn">إظهار</button>
        </div>
      `;
    });

    it('reveals value when masked', () => {
      const btn = document.querySelector('.reveal-btn');
      PiiMask().toggleReveal(btn, '123456789');
      expect(document.querySelector('.pii-visible').textContent).toBe('123456789');
      expect(document.querySelector('.pii-visible').getAttribute('data-masked')).toBe('false');
    });

    it('masks value when revealed', () => {
      const span = document.querySelector('.pii-visible');
      span.setAttribute('data-masked', 'false');
      span.textContent = '123456789';
      const btn = document.querySelector('.reveal-btn');
      PiiMask().toggleReveal(btn, '123456789');
      expect(span.getAttribute('data-masked')).toBe('true');
    });
  });
});
