# دليل النشر الإنتاجي — Azad Medical Platform

**الإصدار:** 3.1 · **29 يونيو 2026**  
**الحالة التقنية:** [PLATFORM_STATUS.md](PLATFORM_STATUS.md)

---

## 1. المتطلبات

| المكوّن | الإصدار |
|---------|---------|
| Docker + Docker Compose | v2+ |
| PostgreSQL | **16** (إلزامي للإنتاج) |
| Redis | **7** |
| Python | 3.11+ (للتطوير المحلي) |

> SQLite غير مدعوم للإنتاج أو CI. جميع الاختبارات والتهجيرات تفترض PostgreSQL.

---

## 2. البنية (Docker Compose)

```
┌─────────┐     ┌─────────┐     ┌──────────────┐
│  Redis  │◄────│   App   │────►│ PostgreSQL 16│
└────┬────┘     │ Gunicorn│     └──────────────┘
     │          └─────────┘
     ▼          ┌─────────┐
┌─────────┐     │ Worker  │  Celery (نسخ احتياطي، إشعارات، مهام)
│         │◄────│ Celery  │
└─────────┘     └─────────┘
```

```bash
docker compose up -d --build
```

- **المنفذ:** `8080`
- **التهجيرات:** تُنفَّذ تلقائياً عند بدء `app`
- **الرأس:** `s1_004_expenses_rls_uniques`

---

## 3. متغيرات البيئة

```bash
# إلزامي
SECRET_KEY=your-256-bit-secret-key
DATABASE_URL=postgresql://user:pass@db:5432/medical_system
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0

# التشغيل
FLASK_ENV=production
HOST=0.0.0.0
PORT=8080
CELERY_ENABLED=true

# SaaS
ENABLE_SAAS_MODE=true
DEPLOYMENT_MODE=saas

# Stripe (للتسجيل والفوترة)
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_CURRENCY=usd
SAAS_CHECKOUT_BASE_URL=https://your-domain.com
SAAS_REQUIRE_PAYMENT_AT_SIGNUP=false
SAAS_DEFAULT_PACKAGE_VERSION_ID=1

# إدارة أولية (اختياري)
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=change-me-immediately
```

---

## 4. التهجيرات

```bash
# يدوياً
flask db upgrade

# داخل الحاوية
docker compose exec app flask db upgrade

# التحقق (كما في CI)
python scripts/ci/verify_migrations.py
```

**سلسلة SaaS الحديثة:**
`s1_002_tenant_rls_policies` → `s1_003_department_tenant_unique` → `s1_004_expenses_rls_uniques`

---

## 5. تهيئة المنصة

### أ) تسجيل ذاتي (SaaS)
1. فعّل `ENABLE_SAAS_MODE=true` و Stripe
2. زُر `/saas/signup` أو وجّه العملاء إليه
3. اضبط webhook Stripe على `POST /api/billing/stripe/webhook`

### ب) توفير يدوي (Owner)
- واجهة: `/owner/tenants/provision`
- API: `POST /owner/api/tenants/provision` (يتطلب `@owner_required`)
- البرمجي: `TenantProvisioningService.provision_tenant` — يُستخدم من Owner API و`/api/saas/register`

---

## 6. Row-Level Security (RLS)

على PostgreSQL، **31 جدولاً** محمي بـ RLS عبر `app.tenant_id`:

- **s1_002 (11):** visits, patients, invoices, payments, appointments, lab_requests, prescriptions, pharmacy_sales, medical_records, queue_management, users
- **s1_004 (20):** departments, insurance_companies, insurance_claims, barcode_registry, barcode_scan_logs, expenses, biometric_credentials, biometric_auth_challenges, wards, medications, audit_trails, treatments, emergency_cases, budgets, notifications, medical_reports, receipts, refund_requests, cash_registers

يُضبط `SET LOCAL app.tenant_id` في middleware ومهام Celery (`tenant_job_runner`).

---

## 7. Stripe Webhooks

| الحدث | الإجراء |
|-------|---------|
| `checkout.session.completed` | تفعيل tenant `PENDING` → `ACTIVE` |
| `customer.subscription.created/updated` | تحديث خط الاشتراك |
| `invoice.paid` | تجديد/تفعيل |
| `invoice.payment_failed` | تعليق أو إشعار |

الـ endpoint معفى من CSRF: `@csrf.exempt` على webhook route.

---

## 8. الفحص الصحي

```bash
curl -f http://localhost:8080/health
curl -f http://localhost:8080/__health
```

---

## 9. الاختبارات (قبل النشر)

```bash
set ENABLE_SAAS_MODE=true
set DATABASE_URL=postgresql://...
python -m pytest tests/ -q --tb=short
```

CI يشغّل نفس الاختبارات على PostgreSQL 16 + Redis مع Celery eager.

---

## 10. الأمان

- أسرار في متغيرات البيئة فقط — لا تُلتزَم في Git
- CSRF على النماذج؛ webhook Stripe معفى
- Rate limiting على التسجيل والفوترة
- `guard_module` مركزي في `app_factory._add_guard_once`
- فلترة tenant افتراضية (fail-closed) في ORM
- HTTPS إلزامي في الإنتاج (`SESSION_COOKIE_SECURE`)

---

## 11. النسخ الاحتياطي

- عبر Super Admin: `POST /super-admin/backup/create` (Celery + `pg_dump`)
- يتطلب `pg_dump` في بيئة الـ worker
- اضبط `BACKUP_LOCAL_DIR` أو تخزين سحابي حسب بيئتك

---

## 12. الوحدات والاشتراكات

- كل tenant يحصل على وحدات حسب `PackageVersion` / entitlements
- الاستقبال إلزامي عند تفعيل أكثر من وحدة سريرية
- تعطيل وحدة = 403 على مساراتها

---

## 13. الدعم

- Issues: https://github.com/AbuAzad2025/Med1/issues
- دليل المستخدم: [USER_GUIDE.md](USER_GUIDE.md)
- ملخص تنفيذي: [CEO_OVERVIEW.md](CEO_OVERVIEW.md)
