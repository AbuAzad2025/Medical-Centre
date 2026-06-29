# حالة المنصة — مصدر الحقيقة التقنية

**آخر تحقق من الكود:** 29 يونيو 2026  
**الإصدار:** 3.1

> هذا الملف يُحدَّث عند تغيير البنية أو CI. لا تعتمد على خطط أو تقارير قديمة محذوفة.

---

## التشغيل (مسار واحد)

```bash
cp .env.example .env
docker compose up -d --build
```

| الخطوة | الأمر / المكوّن |
|--------|------------------|
| 1 | `flask db upgrade` |
| 2 | `python scripts/ops/bootstrap_platform.py` |
| 3 | `gunicorn` |

**Bootstrap يُنشئ:** `module_definitions` · `product_bundles` (23) · `packages`/`package_versions` للتسجيل الذاتي.

---

## البنية

| المكوّن | التفاصيل |
|---------|----------|
| Backend | Flask, SQLAlchemy 2, PostgreSQL **16** |
| Cache / Queue | Redis 7, Celery worker |
| Multi-tenant | `ENABLE_SAAS_MODE`, ORM filter + RLS |
| رأس التهجيرات | `s1_004_expenses_rls_uniques` |
| جداول ORM | 209 (مطابقة migrations — `check_schema_parity.py`) |
| RLS | 31 جدول (11 في s1_002 + 20 في s1_004) |
| Blueprints | 54 مسجّلة في `app_factory.py` |
| وحدات المنصة | 15 في `MODULE_REGISTRY` |
| اختبارات | ~104 ملف — CI مع `ENABLE_SAAS_MODE=true` |

---

## SaaS

| الميزة | المسار / الملف |
|--------|----------------|
| تسجيل ذاتي | `GET/POST /saas/signup`, `POST /api/saas/register` |
| كتالوج الباقات | `product_bundles` → `packages` عبر `platform_bootstrap` |
| توفير tenant | `TenantProvisioningService` — Owner + API |
| فوترة | Stripe — `STRIPE_SECRET_KEY`, webhook `/api/billing/stripe/webhook` |
| حالات tenant | `TRIAL`, `ACTIVE`, `PENDING`, `SUSPENDED`, `CANCELLED` |

**23 باقة في الكتالوج الافتراضي** (22 قابلة للبيع + `custom` فارغة). التفاصيل: استعلام SQL في [CEO_OVERVIEW.md](CEO_OVERVIEW.md) أو:

```sql
SELECT slug, name_ar, monthly_price FROM product_bundles WHERE is_active ORDER BY monthly_price;
```

---

## CI (`.github/workflows/ci.yml`)

1. `verify_migrations.py` — upgrade على PostgreSQL فارغ + تطابق ORM
2. `bootstrap_platform.py`
3. `pytest` كامل + flake8 + coverage

---

## ما ليس جزءاً من التشغيل

| العنصر | الحكم |
|--------|--------|
| `scripts/dev/` | تطوير فقط (مُستبعد من `.dockerignore`) |
| `scripts/audit_*.py`, `lint_debt.py` | تدقيق يدوي |
| `migrations/manual_scripts/` | يدوي — لا يُشغَّل مع upgrade |
| `flask module-seed` | يفعّل كل الوحدات لكل tenants — **خطر في إنتاج** |

---

## التحقق السريع بعد النشر

```bash
curl -f http://localhost:8080/health
curl -f http://localhost:8080/__health
python scripts/check_schema_parity.py
```

```sql
SELECT COUNT(*) FROM product_bundles;
SELECT COUNT(*) FROM packages;
SELECT version_num FROM alembic_version;
```

---

## المستندات الحية

| ملف | الغرض |
|-----|--------|
| [README.md](../README.md) | نظرة عامة |
| [DEPLOYMENT.md](DEPLOYMENT.md) | نشر ومتغيرات بيئة |
| [USER_GUIDE.md](USER_GUIDE.md) | مستخدمو المركز |
| [CEO_OVERVIEW.md](CEO_OVERVIEW.md) | ملخص إداري |
| [../scripts/ops/README.md](../scripts/ops/README.md) | أوامر التشغيل |
| [DYNAMIC_FORM_GOVERNANCE.md](DYNAMIC_FORM_GOVERNANCE.md) | عقد نماذج التخصص |
