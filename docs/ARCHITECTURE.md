# المعمارية — Architecture Guide

وثيقة شاملة للمعمارية، الأنماط التقنية، تدفقات البيانات، وقرارات التصميم في منصة المركز الطبي.

---

## 1. نظرة عامة عالية المستوى

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Medical Centre Platform                       │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │   Web UI     │  │   API        │  │  Real-time   │              │
│  │  (Jinja2)    │  │  (Flask)     │  │  (SocketIO)  │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
│         │                 │                 │                      │
│         └─────────────────┼─────────────────┘                      │
│                           ▼                                        │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    Flask Application (wsgi:app)               │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │  │
│  │  │ Blueprints  │  │ Middleware  │  │   Services Layer    │   │  │
│  │  │ (61)        │  │ (tenant,    │  │  (domain logic,     │   │  │
│  │  │             │  │  RLS, auth) │  │   external APIs)    │   │  │
│  │  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘   │  │
│  └─────────┼───────────────┼─────────────────────┼──────────────┘  │
│            ▼               ▼                     ▼                 │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                  SQLAlchemy 2.0 ORM                          │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │  │
│  │  │ Models      │  │ Tenant      │  │   Module Registry   │   │  │
│  │  │ (224)       │  │ Filter      │  │   (22 modules)      │   │  │
│  │  └─────────────┘  └──────┬──────┘  └─────────────────────┘   │  │
│  └──────────────────────────┼────────────────────────────────────┘  │
│                             ▼                                        │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              PostgreSQL 16 + RLS                             │  │
│  │  227 tables · 202 tenant-scoped · 210 policies · 206 FORCE  │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. الأنماط المعمارية الأساسية

### 2.1. تعدد المستأجرين (Multi-Tenancy) — SaaS Pattern

| الطبقة | الآلية |
|--------|--------|
| **تحديد المستأجر (Tenant Resolution)** | `TenantResolutionService` — يدعم: subdomain (`clinic.domain.com`)، path (`/t/slug/`)، domain، header |
| **عزل ORM (ORM Filter)** | `tenant_filter.py` — `before_compile` (legacy queries) + `do_orm_execute` (SQLAlchemy 2.0 `select()`) — يضيف `tenant_id = current_setting('app.tenant_id')` تلقائياً |
| **RLS (Row Level Security)** | PostgreSQL policies — `tenant_id = NULLIF(current_setting('app.tenant_id'::text, true), '')::integer` — **202 جدول** تحت `FORCE ROW LEVEL SECURITY` |
| **تجاوز المنصة (Platform Bypass)** | `SET LOCAL app.bypass_rls = 'on'` — للمشرفين، المهام المجدولة، النسخ الاحتياطية |

**قاعدة الذهب:** كل استعلام ORM يمر عبر الفلتر؛ كل استعلام SQL خام يجب أن يربط `tenant_id` أو يعمل داخل `platform_tenant_scope()`.

### 2.2. نظام الوحدات (Module System) — Feature Gating

```
MODULE_REGISTRY (22 modules)
    │
    ├── tables: tuple[str]          # مطالبة الجداول (non-exclusive)
    ├── category: str               # clinical | administrative | financial | integration
    ├── capabilities: tuple[str]    # ما تستطيع الوحدة فعله
    ├── required_modules: tuple     # تبعيات صلبة
    └── standalone_allowed: bool    # هل يمكن بيعها وحدها
```

**التفعيل:**
- **وقت التوفير:** `TenantProvisioningService._ensure_modules_for_package()` → ينشئ `TenantModule` rows نشطة.
- **وقت التشغيل:** `get_active_modules_for_current_tenant()` يقرأ من `g.enabled_modules` (مُضبط في middleware) أو session.
- **حارس المسار (Route Guard):** `guard_module(module_name)` في `before_request` لكل blueprint — يرفع `ModuleNotEnabledError` (403) إذا الوحدة مطفأة.

**عزل البيانات عبر الوحدات (Module Data Isolation):**
- `tenant_filter.py` يحسب `module_scope = (restricted_tables, active_modules)` لكل مستأجر.
- **قراءة:** جدول لا تلمسه أي وحدة نشطة → `filter(false())` (صفر صفوف).
- **كتابة:** محاولة كتابة في جدول لا تلمسه وحدة نشطة → `ModuleNotEnabledError`.
- **استثناء:** جداول لا تطالب بها أي وحدة (48 جدول منصة) → مفتوحة دائماً.

### 2.3. نظام الأدوار والصلاحيات (RBAC)

| المكوّن | الملف | المسؤولية |
|----------|-------|-----------|
| `ASSIGNABLE_ROLES` | `user_role_policy.py` | 17 دور قابل للتعيين عبر UI |
| `ROLE_HIERARCHY` | `utils/decorators.py` | وراثة: `owner → super_admin → admin → manager → reception/accountant` |
| `role_required()` | `utils/decorators.py` | ديكوريتر للتحقق من الدور + الهرمية |
| `AccessControlService` | `services/access_control.py` | تحقق صلاحيات دقيقة (`require_permission`) |
| `CLINICAL_STAFF_ROLES` | `user_role_policy.py` | من يقرأ البيانات المرجعية (كتالوجات، قوائم أسعار) |

**خريطة الدور → الوحدة (Dashboard Routing):**
```python
ROLE_TO_MODULE_MAP = {
    'doctor': 'doctor',
    'er_doctor': 'emergency',
    'pharmacist': 'pharmacy',
    'reception': 'reception',
    'lab': 'lab',
    'radiology': 'radiology',
    'emergency': 'emergency',
    'nurse': 'nursing',
    'accountant': 'billing',
    'manager': 'reporting',
    'owner': 'owner',
    'super_admin': 'owner',
    'platform_owner': 'owner',
    'patient': 'portal',
    'technician': 'lab',
    'tenant_admin': 'billing',
}
```

---

## 3. تدفقات البيانات الحرجة

### 3.1. تسجيل مستأجر جديد (SaaS Signup)

```
POST /api/saas/register
    │
    ▼
TenantProvisioningService.provision_tenant()
    │
    ├── 1. إنشاء Tenant (status=TRIAL)
    ├── 2. إنشاء مستخدم مالك (owner)
    ├── 3. _ensure_modules_for_package() → tenant_modules actifs
    ├── 4. تهيئة إعدادات افتراضية (tenant_module_settings)
    ├── 5. إنشاء اشتراك تجريبي (SubscriptionLine)
    └── 6. إرجاع tenant_id + بيانات الدخول
```

### 3.2. زيارة طبية كاملة (Clinical Flow)

```
Patient ← Reception → Doctor → Lab/Radiology → Pharmacy → Billing
    │         │           │           │           │          │
    ▼         ▼           ▼           ▼           ▼          ▼
patients  visits    medical_   lab_      radiology_  prescription_
          visits    records   requests  requests    dispense_logs
          SOAP     ICD-10   specimens  images      invoices
          ICD-10   CPT      results    reports     payments
```

**العزل:** كل خدمة تكتب في جداولها؛ الوحدة الحارسة تمنع الوصول لوحدة مطفأة. القراءة عبر `tenant_filter` تضمن صفر صفوف لوحدة غير نشطة.

### 3.3. بحث المريض (PHI Search) — AES-SIV + HMAC Blind Index

```
إدخال: "أحمد محمد" + "1234567890" (هوية) + "0501234567" (هاتف)
    │
    ├── الاسم/العنوان → تشفير AES-SIV حتمي (deterministic) → `enc_name`, `enc_address`
    ├── الهوية → HMAC-SHA256(key=FIELD_ENCRYPTION_KEY) → `national_id_hash` (فهرس فريد)
    ├── الهاتف → HMAC-SHA256 → `phone_hash`
    └── البحث الجزئي (3+ أحرف) → `patient_search_ngrams` (trigram ngrams)
```

---

## 4. قاعدة البيانات — PostgreSQL 16 + RLS

### 4.1. إحصائيات المخطط (متحققة)

| التصنيف | العدد |
|----------|-------|
| جداول عامة (`public`) | 227 |
| جداول عالمية (بلا `tenant_id`) | 18 |
| جداول منصة بـ `tenant_id` (استثنائية) | 7 |
| **جداول tenant-scoped تحت RLS FORCE** | **202** |
| سياسات إجمالاً | 210 |
| سياسات `tenant_isolation_*` | 206 |

### 4.2. نمط السياسة (Policy Pattern)

```sql
-- سياسة القراءة/الكتابة القياسية
CREATE POLICY tenant_isolation_<table> ON <table>
    USING (tenant_id = NULLIF(current_setting('app.tenant_id'::text, true), '')::integer)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id'::text, true), '')::integer);

-- سياسة تجاوز المنصة (super_admin, backup, migration)
CREATE POLICY <table>_super_admin ON <table>
    FOR ALL USING (current_setting('app.bypass_rls', true) = 'on');
```

### 4.3. جداول غير مطالبة (Orphan Tables — 48 جدول)

هذه الجداول لها `tenant_id` لكن لا تطالب بها أي وحدة — **تظل قابلة للقراءة/الكتابة** لكل مستأجر (سلوك منصة):
- `audit_trails`, `audit_logs`, `phi_audit_logs` (سجلات تدقيق)
- `users`, `nurses` (مستخدمون/طاقم)
- `notifications`, `notification_templates`, `whatsapp_messages` (إشعارات)
- `backups`, `backup_logs` (نسخ احتياطية)
- `subscription_lines`, `tenant_entitlements`, `tenant_modules` (آليات SaaS)
- `security_events`, `session_logs`, `login_attempts` (أمان)
- `projects`, `tasks`, `task_*` (إدارة مشاريع — ميزة بدون وحدة مسجلة)

---

## 5. الواجهة الأمامية (Frontend)

| التقنية | التفاصيل |
|---------|----------|
| **Template Engine** | Jinja2 (SSR) — 432 قالب في `templates/` |
| **CSS Framework** | Bootstrap 5 + SCSS مخصص |
| **JavaScript** | ES6 Modules، Alpine.js للتفاعل الخفيف، SocketIO للوقت الحقيقي |
| **دعم RTL** | كامل — `dir="rtl"`、`lang="ar"`، خطوط عربية (Noto Sans Arabic) |
| **i18n** | Flask-Babel + `gettext` — 0 نص غير مترجم في CI |
| **اختبارات الواجهة** | Vitest — 67 ملف، 280 اختبار (`npx vitest run`) |
| **Linting** | Stylelint (CSS)، cspell (إملاء)، actionlint (GitHub Actions YAML) |

---

## 6. الأمان (Security)

| الطبقة | التنفيذ |
|--------|----------|
| **تشفير PHI** | AES-SIV حتمي للأسماء/العناوين، HMAC blind index للهوية/الهاتف، الفهرس الفريد `(tenant_id, national_id_hash)`، البحث الجزئي عبر `patient_search_ngrams` (trigram 3+) |
| **Audit Logs** | `audit_trails` (كل العمليات)، `phi_audit_logs` (وصول PHI)، `platform_audit_logs` (أحداث المنصة) — كلها RLS محمية |
| **MFA / WebAuthn** | اختياري عبر `PLATFORM_CAP_WEBAUTHN=true`، `PLATFORM_CAP_SSO=true` |
| **Superuser Block** | في الإنتاج: `postgres`/`superuser` ممنوع من قراءة بيانات المستأجرين (RLS FORCE) |
| **Dependency Scanning** | `pip-audit` في CI، `bandit -lll` (0 high) |

---

## 7. CI/CD Pipeline (23 وظيفة)

| المرحلة | الوظائف |
|---------|---------|
| **Static Analysis** | `static-analysis-python` (ruff, mypy, pip-audit, bandit)، `static-quality`، `workflow-integrity` |
| **Frontend** | `templates-i18n`، `frontend-spelling-css`، `frontend-asset-quality` |
| **Database** | `migrate` (upgrade على PG فارغ + bootstrap + RLS audit)، `verify-boot` |
| **Security** | `security-audit` (5 نصوص: guard رفض superuser، enforcement، RLS coverage، orphaned rows، stale actions) |
| **Tests** | `routes` (PG 15/16/17)، `unit`، `integration`، `clinical`، `core` (4 شاردات)، `coverage-report` |

**إجمالي وقت CI:** ~18-25 دقيقة على GitHub Actions (PostgreSQL 16).

---

## 8. قرارات التصميم المسجلة (Architecture Decision Records)

| ADR | الموضوع | الحالة |
|-----|---------|-------|
| ADR-001 | RLS + ORM Filter للعزل المزدوج | ✅ مطبق |
| ADR-002 | Module Registry غير حصري (non-exclusive table claims) | ✅ مطبق (`e69c81c0`) |
| ADR-003 | AES-SIV + HMAC blind index لـ PHI search | ✅ مطبق (`s3_014/015`) |
| ADR-004 | er_doctor → emergency module mapping | ✅ مطبق (`e69c81c0`) |
| ADR-005 | Module data isolation (read=filter false, write=error) | ✅ مطبق |
| ADR-006 | Platform bypass via `app.bypass_rls` | ✅ مطبق |
| ADR-007 | Alembic-only schema (لا `create_all` في الإنتاج) | ✅ مفروض في CI |

---

## 9. المراجع السريعة للكود

| المفهوم | الملف الرئيسي |
|---------|---------------|
| تطبيق Flask | `app_factory.py:create_app()` |
| تسجيل Blueprint | `app_factory.py` خطوط 300-500 |
| Middleware المستأجر | `app/core/tenant/middleware.py` |
| فلتر ORM | `app/shared/tenant_filter.py` |
| سجل الوحدات | `app/core/module/registry.py` |
| تفعيل الوحدات | `app/core/saas/lifecycle.py` |
| توجيه لوحة التحكم | `services/dashboard_routing.py` |
| سياسة الأدوار | `app/shared/user_role_policy.py` |
| ديكوريتر الصلاحيات | `utils/decorators.py:role_required()` |
| بذر RBAC | `app/bootstrap/rbac_seed.py` |
| بذر الحزم | `app/core/tenant/models.py:seed_default_bundles()` |
| تدقيق RLS | `scripts/ci/audit_rls_coverage.py` |
| التحقق من الهجرات | `scripts/ci/verify_migrations.py` |

---

## 10. التوسعات المستقبلية (Roadmap)

| الميزة | الحالة | الملاحظات |
|--------|--------|-----------|
| FHIR R4 API كامل | 🟡 قيد التصميم | وحدة `integration` جاهزة |
| DICOM PACS كامل | 🟡 جزئي | `ai_imaging` + `dicom_listener` |
| تطبيق جوال (React Native) | 🔴 مخطط | API جاهز، واجهة مطلوبة |
| تحليلات تنبؤية (ML) | 🔴 مخطط | `ai_imaging` الأساس |
| Marketplace للوحدات | 🔴 مخطط | توسعة `module_registry` |