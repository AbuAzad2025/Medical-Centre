# اختبارات E2E — Playwright

## التشغيل السريع

```bash
# 1. تثبيت المتصفح (مرة واحدة)
npm run e2e:install

# 2. شغّل تطبيق Flask على 127.0.0.1:8080 مع قاعدة بيانات اختبار مهيأة
#    (seeds/ + مستخدمون: reception_e2e / doctor_e2e / pharmacist_test)

# 3. نفّذ الاختبارات
npm run e2e            # headless
npm run e2e:headed     # بمتصفح مرئي
npm run e2e:ui         # واجهة تفاعلية
```

## متغيرات البيئة

| المتغير | الافتراضي | الوصف |
|---------|-----------|-------|
| `E2E_BASE_URL` | `http://127.0.0.1:8080` | عنوان التطبيق |
| `E2E_RECEPTION_USER/_PASS` | `reception_e2e` / `ValidPass123!` | حساب الاستقبال |
| `E2E_DOCTOR_USER/_PASS` | `doctor_e2e` / `ValidPass123!` | حساب الطبيب |
| `E2E_PHARMACIST_USER/_PASS` | `pharmacist_test` / `ValidPass123!` | حساب الصيدلي |

## المواصفات (Specs)

| الملف | التغطية |
|-------|---------|
| `specs/auth.spec.js` | تسجيل الدخول/الخروج، كلمة مرور خاطئة، صفحة استعادة الحساب |
| `specs/clinical-cycle.spec.js` | **الدورة السريرية الكاملة**: مريض ← زيارة ← طابور ← طبيب ← وصفة ← فاتورة |
| `specs/security.spec.js` | CSP بدون unsafe-inline، nonce فعّال، صفر طلبات CDN خارجية |

## التقارير والآثار

- تقرير HTML: `e2e/report/index.html`
- آثار الفشل (trace/screenshot/video): `e2e/artifacts/`

```bash
npx playwright show-report   # فتح التقرير
```

> **ملاحظة**: الدورة السريرية stateful وتُنفَّذ serially (workers=1) ضد قاعدة
> بيانات مؤقتة فقط. لا تشغّلها على قاعدة إنتاج.
