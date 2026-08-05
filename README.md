# منصة المركز الطبي — Medical Centre Platform

نظام إدارة مراكز طبية متكامل (HIS) يدعم اللغة العربية والإنجليزية، بنمط تعدد المستأجرين (SaaS multi-tenant) مع عزل كامل للبيانات عبر RLS على مستوى قاعدة البيانات.

**الإصدار الحالي:** 3.1

---

## نظرة عامة

منصة طبية شاملة تغطي دورة المريض الكاملة: الاستقبال → العيادة → المختبر → الأشعة → الصيدلية → الطوارئ → التمريض → الفوترة → التقارير، مع بوابات رقمية للمريض ولوحة مالك للمنصة السحابية.

| المسار | الوصف |
|--------|-------|
| [docs/PLATFORM_STATUS.md](docs/PLATFORM_STATUS.md) | مصدر الحقيقة التقني (أرقام متحققة من الكود) |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | النشر والمتغيرات |
| [docs/CEO_OVERVIEW.md](docs/CEO_OVERVIEW.md) | ملخص إداري تنفيذي |
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | دليل استخدام مركز طبي واحد |
| [docs/DYNAMIC_FORM_GOVERNANCE.md](docs/DYNAMIC_FORM_GOVERNANCE.md) | عقد نماذج التخصص الديناميكية |
| [COMMERCIAL_READINESS_AUDIT.md](COMMERCIAL_READINESS_AUDIT.md) | تدقيق الجاهزية التجارية (2026-07) |
| [ENHANCEMENT_SUMMARY.md](ENHANCEMENT_SUMMARY.md) | ملخص التحسينات (2026-07) |
| [PRE_PILOT_VERIFICATION_REPORT.md](PRE_PILOT_VERIFICATION_REPORT.md) | تقرير تحقق ما قبل التشغيل التجريبي |

---

## التقنية

| المكوّن | الإصدار/الوصف |
|---------|---------------|
| Backend | Python 3.11+, Flask 3.1, SQLAlchemy 2.0 |
| قاعدة البيانات | PostgreSQL 16 (وحيد المدعوم) |
| Cache / Queue | Redis 7 + Celery |
| Frontend | Jinja2 SSR, Bootstrap, JavaScript (ثنائي اللغة AR/EN) |
| Web | Gunicorn (إنتاج) + SocketIO (تطوير) |

---

## الأدوار والوحدات

**أدوار المستخدم:** استقبال · طبيب · ممرض · مختبر · أشعة · محاسب · مدير · مشرف · صاحب مركز (مالك SaaS).

**15 وحدة مسجلة في `MODULE_REGISTRY`:**

| الوحدة | التصنيف | الوصف |
|--------|---------|-------|
| `reception` | إداري | تسجيل المرضى والزيارات والمواعيد |
| `doctor` | سريري | الفحوصات والتشخيص والروشيتات والاستشارات عن بعد |
| `lab` | سريري | طلبات التحاليل والعينات والنتائج والجودة |
| `radiology` | سريري | طلبات الأشعة والتقارير والصور (DICOM) |
| `pharmacy` | سريري | إدارة الأدوية والمخزون والبيع (POS) |
| `emergency` | سريري | حالات الطوارئ والفرز |
| `nursing` | سريري | رعاية المرضى والعلاجات (eMAR) والأسرّة |
| `billing` | مالي | الفواتير والدفعات والإيصالات والتأمين |
| `inventory` | إداري | المستودعات والمشتريات والمخزون والباركود |
| `appointments` | إداري | جدولة المواعيد والحجز الإلكتروني |
| `reporting` | إداري | التقارير الطبية والمالية ومستودع البيانات |
| `owner` | تكامل | لوحة المالك وإدارة المستأجرين والمنصة |
| `portal` | سريري | بوابة المريض الإلكترونية (نتائج/مواعيد/فواتير) |
| `ai_imaging` | سريري | تحليل الصور الطبية بالذكاء الاصطناعي |
| `integration` | تكامل | FHIR · SSO · DICOM listener |

---

## التشغيل السريع

```bash
cp .env.example .env
docker compose up -d --build
```

بعد الإقلاع الأول تعمل الحاوية تلقائياً:

```bash
flask db upgrade
python scripts/ops/bootstrap_platform.py
gunicorn -c gunicorn.conf.py wsgi:app
```

التحقق:

```bash
curl -f http://localhost:8080/health
curl -f http://localhost:8080/__health
```

**ملاحظات:**
- `SECRET_KEY` إلزامي قبل الإقلاع (`.env`).
- `FIELD_ENCRYPTION_KEY` مطلوب لتشفير البيانات الحساسة (PHI).
- للوضع السحابي: `ENABLE_SAAS_MODE=true` و `DEPLOYMENT_MODE=saas`.
- `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d` للإنتاج.

---

## الاختبارات

```bash
# إعداد البيئة (PostgreSQL 16 + Redis)
docker compose up -d db redis

# الهجرات + البذرة
flask db upgrade
python scripts/ops/bootstrap_platform.py

# الاختبارات
python -m pytest -q --tb=short
```

- **139 ملف** اختبار موزعة على `unit/` · `integration/` · `clinical/` · ملفات الجذر.
- CI يدير 15 وظيفة على PostgreSQL 16 مع مصفوفة 15/16/17 لاختبارات المسارات.

---

## SaaS

| الميزة | الوصف |
|--------|-------|
| تسجيل ذاتي | `/saas/signup` و `/api/saas/register` |
| الباقات | 23 باقة (22 قابلة للبيع + `custom`) في `product_bundles` |
| الفوترة | Stripe عبر `/api/billing/stripe/webhook` |
| حالات tenant | `TRIAL` · `ACTIVE` · `PENDING` · `SUSPENDED` · `CANCELLED` |
| العزل | ORM filter + RLS (`TABLES_WITH_POLICIES=181` + `NO_POLICY=10`) |

---

## الأمان

- تشفير الحقول الحساسة (PHI) بمفتاح `FIELD_ENCRYPTION_KEY`.
- سجلات تتبع PHI و audit logs على مستوى المنصة.
- MFA / WebAuthn / SSO حسب إعدادات المنصة.
- ضوابط RLS تفرض على 181 جدولاً مع رفض الوصول لـ superuser في وضع الإنتاج.

---

## المساهمات

- أي تغيير في البنية (جداول/ميزات/CI) يجب أن يحدّث [docs/PLATFORM_STATUS.md](docs/PLATFORM_STATUS.md).
- النصوص في الواجهات ثنائية اللغة — لا تُضف نصاً مكتوباً داخل القوالب.
- `npx cspell` و `npx stylelint` على كل تغيير جديد.
