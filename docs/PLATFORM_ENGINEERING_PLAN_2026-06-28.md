# خطة الهندسة — جاهزية SaaS والاستقرار التشغيلي

**التاريخ:** 28 يونيو 2026  
**الحالة:** معتمدة للتنفيذ  
**مرجع الحقيقة التقنية الحالية:** [PLATFORM_STATUS.md](PLATFORM_STATUS.md)

> خطة تنفيذية مباشرة — بدون حشو. الأولوية: CI أخضر → RLS كامل → إخفاء الميزات الناقصة → تغطية 85%+ على المسارات المالية.

---

## الوضع الحالي (حقائق من الكود)

| البند | الحالة |
|-------|--------|
| CI `migrate` + `bootstrap` | ✅ يمر |
| CI `test` | ❌ 5 فشل من ~1238 |
| التغطية | ~62% |
| RLS | 31 جدول (s1_002 + s1_004) — عشرات الجداول `tenant_id` بدون RLS |
| عزل الخلفية | `bind_g_tenant(tenant, db_session=...)` مكسور في job runner |
| Stripe webhook `subscription.deleted` | موجود في الكود — مسار SDK cancel ناقص |
| SMS / WebAuthn / FHIR | ناقصة أو واجهة غير مكتملة |

---

## المرحلة 0 — طوارئ CI (P0) — ابدأ هنا

**الهدف:** صفر فشل في CI خلال 4–8 ساعات.

### خريطة الفشل الخمسة → الإصلاح

| # | الاختبار | السبب | الإصلاح |
|---|----------|-------|---------|
| 1–2 | `tests/test_background_tenant_isolation.py` (`TestTenantJobRunner`) | `services/tenant_job_runner.py:61` يستدعي `bind_g_tenant(tenant, db_session=db.session)` لكن الدالة تقبل `tenant` فقط → TypeError يُبتلع والـ job لا يُنفَّذ | غيّر السطر إلى `bind_g_tenant(tenant)` |
| 3 | `tests/test_e2e_api.py::test_protected_apis_require_auth` | `GET /saas/signup` عام بالتصميم لكن `_PUBLIC_RE` لا يشمل `saas.` | أضف `saas\.` إلى `_PUBLIC_RE` (~سطر 48–51) |
| 4 | `tests/test_route_inventory.py` | `/saas/signup` غير موجود في `route_inventory.json` | أضف مدخلاً (انظر أدناه) |
| 5 | `tests/test_stripe_billing_outbound.py::test_cancel_subscription_updates_local_entitlements` | `cancel_subscription(..., at_period_end=True)` لا يستدعي `cancel_tenant` | أصلح منطق الإلغاء (انظر Stripe) |

### خطوات التنفيذ (بالترتيب)

#### 1. Tenant job runner

```
services/tenant_job_runner.py
app/core/tenant/middleware.py          # اختياري: **kwargs للتوافق
tests/test_background_tenant_isolation.py
```

#### 2. المسارات العامة (عقد الأمان)

```
tests/test_e2e_api.py                  # _PUBLIC_RE += saas\.
route_inventory.json
```

مدخل `route_inventory.json`:

```json
{
  "endpoint": "saas.signup_organization",
  "path": "/saas/signup",
  "methods": ["GET", "POST"],
  "classification": "public"
}
```

#### 3. Stripe — إلغاء الاشتراك → `CANCELLED`

```
services/stripe_billing_service.py     # cancel_subscription()
services/stripe_subscription_service.py  # webhook موجود L119–125
tests/test_stripe_billing_outbound.py
tests/test_stripe_webhook_lifecycle.py # إنشاء — اختبارات webhook
```

**منطق مطلوب في `cancel_subscription`:**

```python
# بعد stripe.Subscription.modify(..., cancel_at_period_end=True):
if getattr(subscription, 'status', None) in ('canceled', 'cancelled'):
    TenantProvisioningService.cancel_tenant(tenant_id)
    EntitlementProjectionService.calculate(tenant_id)
# عند at_period_end=False: الإبقاء على مسار الإلغاء الفوري الحالي
```

**Webhook:** `customer.subscription.deleted` → `TenantProvisioningService.cancel_tenant` — تحقق باختبار وحدة.

#### 4. التحقق

```bash
pytest tests/test_background_tenant_isolation.py \
  tests/test_e2e_api.py::TestE2EApiContracts::test_protected_apis_require_auth \
  tests/test_route_inventory.py \
  tests/test_stripe_billing_outbound.py -q
```

---

### عزل المستأجر في Celery والمهام الخلفية

**المشكلة:** `celery_app.py` يوفّر `app_context()` فقط — بدون `g.tenant_id` وبدون `SET LOCAL app.tenant_id`.

**الملفات:**

```
services/tenant_job_runner.py        # for_each_tenant, with_tenant_context
celery_app.py
tasks/system_tasks.py
services/backup_automation_service.py
services/notification_service.py
app_factory.py                       # حلقة الإشعارات ~1071–1084
```

**النمط المعماري:**

1. **`tenant_task` decorator** في `tenant_job_runner.py` — يلف المهمة بـ `with_tenant_context(app, tenant_id, fn)`.
2. **Fan-out:** `for_each_tenant(app, lambda tid: job(tenant_id=tid))` — لا استعلامات عالمية على جداول tenant.
3. **مهمة لمستأجر واحد** (مثل backup):

```python
backup = Backup.query.get(backup_id)
with_tenant_context(app, backup.tenant_id, lambda: execute_backup_by_id(backup_id))
```

4. **SQL خام:** `SET LOCAL app.tenant_id = '{tenant_id}'` قبل أي استعلام.
5. **تدقيق:** `rg "celery\.task|for_each_tenant|Thread\(" services/ tasks/ app_factory.py`

---

### حماية `/saas/signup` (عام + مُؤمَّن)

| الطبقة | الإجراء | الملف |
|--------|---------|-------|
| قائمة بيضاء للتدقيق | `_PUBLIC_RE` + `route_inventory` | `tests/test_e2e_api.py`, `route_inventory.json` |
| Rate limit | موجود: 20/5د — شدّد POST على `/api/saas/register` | `routes/saas_routes.py` |
| Captcha | Turnstile/hCaptcha — `SIGNUP_CAPTCHA_SECRET` | `saas_routes.py`, `templates/saas/signup.html` |
| Honeypot | حقل مخفي → 400 | `signup.html`, `saas_registration_service.py` |
| منع إغراق DB | حد pending لكل IP/email/ساعة | `services/saas_registration_service.py` |

---

## المرحلة 1 — RLS 100% (P1) — أسبوع 1–2

**الحقيقة:** 31 جدول بـ RLS؛ ~80+ نموذجاً بـ `tenant_id`. ORM وحده لا يكفي.

### 1. سكربت التدقيق (جديد)

```
scripts/audit_rls_coverage.py
```

- يجمع جداول `tenant_id` من ORM
- يطرح `_skip_table` من `app/shared/tenant_filter.py`
- يطرح `RLS_TABLES` من s1_002 + s1_004
- يخرج: `MISSING_RLS`, `ALREADY_RLS`, `SKIP_SHARED`

### 2. مصنع التهجير

```
migrations/migration_utils.py        # enable_tenant_rls(tables)
migrations/versions/s1_005_rls_phase2.py
migrations/versions/s1_006_rls_phase3.py
scripts/verify_migrations.py
tests/test_migrations_upgrade.py
```

**نمط التهجير** (من `s1_002_tenant_rls_policies.py`):

```python
for table in RLS_TABLES:
    op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
    op.execute(
        f"CREATE POLICY tenant_isolation_{table} ON {table} "
        f"USING (tenant_id = current_setting('app.tenant_id', true)::int)"
    )
```

### 3. دفعة المرحلة 2 (مالي/سريري أولاً)

workflows, tasks, pricing, supply_requests, referrals, dicom, fhir_mappings, sso_configs, telemedicine, online_bookings, patient_accounts, lab_test_catalog, …

### 4. عقد التشغيل

كل مسار DB يستدعي `bind_g_tenant()` → `SET LOCAL app.tenant_id`.

### 5. بوابة CI

أضف `audit_rls_coverage.py` لـ job الـ migrate — فشل إذا `MISSING_RLS` غير فارغ.

**لا RLS أبداً:** `tenants`, `module_definitions`, `product_bundles`, `packages`, جداول ICD/CPT المرجعية — انظر `_skip_table`.

---

## المرحلة 2 — تجميد وإخفاء الميزات الناقصة (P1) — 2–3 أيام

**الهدف:** لا واجهات مكسورة للمستخدم.

### سجل القدرات (جديد)

```
app/core/platform_capabilities.py
.env.example
app_factory.py                       # platform_capability() في القوالب
```

```python
CAPABILITIES = {
    'sms_live':   env_bool('PLATFORM_CAP_SMS_LIVE', False),
    'webauthn':   env_bool('PLATFORM_CAP_WEBAUTHN', False),
    'fhir_api':   env_bool('PLATFORM_CAP_FHIR', False),
    'sso':        env_bool('PLATFORM_CAP_SSO', False),
}
```

| الوحدة | إخفاء عند | الملفات |
|--------|-----------|---------|
| SMS حي | `not sms_live` | `app/integrations/sms/`, `routes/super_admin/system.py`, قوالب الإعدادات |
| WebAuthn | `not webauthn` | `routes/biometric_routes.py`, قوالب biometric |
| FHIR/SSO | `not fhir_api` / `not sso` | `app/modules/sso/`, `routes/fhir_routes.py`, `registry.py` |

```
routes/biometric_routes.py           # require_platform_capability → 404
routes/fhir_routes.py
services/feature_gate_service.py
templates/partials/_sidebar.html
```

**إنتاج:** كل `PLATFORM_CAP_*=false` حتى الجاهزية.

---

## المرحلة 3 — التغطية 62% → 85%+ (P2) — أسبوع 2–3

**النطاق:** `services/` + `app/core/saas/` + access control — ليس القوالب.

```bash
pytest --cov=services --cov=app/core/saas --cov=app/core/tenant --cov-report=term-missing
```

| الوحدة | الحالي (~) | الهدف | ملف اختبار |
|--------|------------|-------|------------|
| `stripe_subscription_service` | 54% | 90% | `tests/test_stripe_webhook_lifecycle.py` |
| `stripe_billing_service` | ~60% | 90% | `tests/test_stripe_billing_outbound.py` |
| `saas_registration_service` | جزئي | 85% | `tests/test_saas_registration_service.py` |
| `financial_service` | جديد | 85% | `tests/test_financial_service_expenses.py` |
| `access_control_service` | — | 90% | `tests/test_access_control_service.py` |
| `tenant_job_runner` | 0% | 95% | `test_background_tenant_isolation.py` |

**سيناريوهات webhook إلزامية:**

- `checkout.session.completed` → ACTIVE
- `customer.subscription.updated` → past_due → SUSPENDED
- `customer.subscription.deleted` → CANCELLED
- `invoice.payment_failed` / `invoice.paid`
- Idempotency عبر `StripeWebhookEvent`

**بوابة CI تدريجية:** `.github/workflows/ci.yml` — `--cov-fail-under` +5 كل sprint حتى 85.

---

## ترتيب التنفيذ (لوحة Sprint)

```
الأسبوع 1 — ship-blocking
├── [2h]  إصلاح tenant_job_runner bind_g_tenant
├── [1h]  whitelist /saas/signup
├── [2h]  stripe cancel_subscription + webhook tests
├── [4h]  Celery tenant_task + تدقيق المستدعين
└── [2h]  signup honeypot + captcha stub

الأسبوع 2 — أمان
├── [1d]  audit_rls_coverage.py + CI
├── [2d]  s1_005_rls_phase2 (~25 جدول)
└── [1d]  إصلاح اختبارات backup/celery بعد RLS

الأسبوع 3 — منتج + تغطية
├── [1d]  platform_capabilities + إخفاء UI
├── [3d]  اختبارات Stripe/billing/registration/access
└── [1d]  s1_006_rls_phase3 (الباقي)
```

---

## الملفات — افتحها أولاً اليوم

| الأولوية | المسار |
|----------|--------|
| P0 | `services/tenant_job_runner.py` |
| P0 | `services/stripe_billing_service.py` |
| P0 | `tests/test_e2e_api.py` |
| P0 | `route_inventory.json` |
| P0 | `celery_app.py`, `tasks/system_tasks.py` |
| P1 | `migrations/migration_utils.py`, `s1_005_*` |
| P1 | `scripts/audit_rls_coverage.py` (إنشاء) |
| P1 | `app/core/platform_capabilities.py` (إنشاء) |
| P2 | `tests/test_stripe_webhook_lifecycle.py` (إنشاء) |
| P2 | `services/saas_registration_service.py` |

---

## حقائق صعبة (بدون تجميل)

1. **الـ 5 فشل جراحية** — kwarg خاطئ، قائمة بيضاء ناقصة، فرع billing ناقص.
2. **RLS عند 31 جدول هو الفجوة الأمنية الحقيقية** — يمنع بيع SaaS enterprise.
3. **Webhook cancel يعمل؛ SDK cancel لا** — العميل قد يبقى `active` حتى webhook أو أبداً.
4. **62% → 85% واقعي في 2–3 أسابيع** إذا نُطقت على `services/` + `app/core/saas/`.
5. **Feature flags أفضل من تنفيذ وهمي** — أخفِ SMS حي / WebAuthn / FHIR حتى الاكتمال.

---

## سجل التنفيذ

| التاريخ | البند | الحالة | ملاحظات |
|---------|-------|--------|---------|
| 2026-06-28 | إنشاء الخطة | ✅ | هذا الملف |
| 2026-06-29 | Phase 0 — CI أخضر | ✅ | tenant_job_runner، _PUBLIC_RE، route_inventory، stripe cancel |
| 2026-06-29 | Celery tenant isolation | ✅ | with_tenant_context return، tenant_task، run_system_backup |
| 2026-06-29 | /saas/signup hardening | ✅ | honeypot، Turnstile captcha، flood limits |
| 2026-06-29 | Phase 1 — RLS (start) | ✅ | audit_rls_coverage.py، s1_005_rls_phase2 (~28 جدول) |
| 2026-06-29 | Phase 1 — RLS (complete) | ✅ | s1_006_rls_phase3 (56 جدول)، CI audit gate |
| 2026-06-29 | Phase 2 — feature flags | ✅ | platform_capabilities.py، route/UI gating، tests |
| 2026-06-29 | Phase 3 — coverage 85% | ✅ | 6 وحدات ≥85%: stripe_subscription 92%, stripe_billing 96%, saas_registration 96%, financial 86%, access_control 85%, tenant_job_runner 86% |
