// App bootstrap (RTL-aware) - ES Module
import { initCsrf } from './csrf.js';
import { normalizeArabicDigits } from './digits-ar.js';
import { initFlashAutoHide } from './flash.js';
import { initDataTables } from './datatables-init.js';

document.addEventListener('DOMContentLoaded', () => {
  initCsrf();
  initFlashAutoHide();
  normalizeArabicDigits(document.body);
  initDataTables();
});