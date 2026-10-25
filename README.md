# منصة المركز الطبي — Medical Centre Platform

نظام إدارة مراكز طبية متكامل (HIS/EHR) يدعم اللغة العربية والإنجليزية، بنمط تعدد المستأجرين (SaaS multi-tenant) مع عزل كامل للبيانات عبر Row Level Security (RLS) على مستوى قاعدة البيانات PostgreSQL.

**الإصدار الحالي:** 3.3 — رأس التهجيرات `s3_015_patient_search_ngrams`

---

## نظرة عامة

منصة طبية شاملة تغطي دورة المريض الكاملة: الاستقبال → العيادة → المختبر → الأشعة → الصيدلية → الطوارئ → التمريض → الفوترة → المخزون → المواعيد → التقارير، مع بوابات رقمية للمريض ولوحة مالك للمنصة السحابية.

| المسار | الوصف |
|--------|-------|
| [docs/PLATFORM_STATUS.md](docs/PLATFORM_STATUS.md) | مصدر الحقيقة التقنية (أرقام متحققة من الكود وقاعدة البيانات) |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | دليل النشر والإعداد للإنتاج |
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | دليل استخدام المركز الطبي |
| [docs/CEO_OVERVIEW.md](docs/CEO_OVERVIEW.md) | ملخص إداري تنفيذي |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | المعمارية والأنماط التقنية |
| [docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md) | دليل المطور (إعداد، اختبارات، مساهمة) |
| [docs/API_REFERENCE.md](docs/API_REFERENCE.md) | مرجع API (OpenAPI 3.0) |
| [docs/OPERATIONS.md](docs/OPERATIONS.md) | عمليات التشغيل والصيانة |

---

## التقنية

| المكوّن | الإصدار/الوصف |
|---------|---------------|
| Backend | Python 3.11+, Flask 3.1, SQLAlchemy 2.0 |
| قاعدة البيانات | PostgreSQL 16 (وحيد المدعوم، متحقق أيضاً على 14/15/17) |
| Cache / Queue | Redis 7 + Celery (worker + beat) |
| Frontend | Jinja2 SSR, Bootstrap 5, JavaScript ES6 (ثنائي اللغة AR/EN) |
| Web Server | Gunicorn (إنتاج) + SocketIO (وقت حقيقي) |
| CI/CD | GitHub Actions — 23 وظيفة على PostgreSQL 16 |

---

## الوحدات المسجلة (22 وحدة في `MODULE_REGISTRY`)

| الوحدة | التصنيف | الوصف | مطالبة جداول |
|---------|---------|-------|--------------|
| `reception` | إداري | تسجيل المرضى، الزيارات، المواعيد، الطابور | 16 |
| `doctor` | سريري | الفحوصات، التشخيص، الروشيتات، الاستشارات عن بعد | 42 |
| `lab` | سريري | طلبات التحاليل، العينات، النتائج، ضبط الجودة | 7 |
| `radiology` | سريري | طلبات الأشعة، التقارير، الصور (DICOM) | 6 |
| `pharmacy` | سريري | إدارة الأدوية، المخزون، البيع (POS)، صرف الروشيتات | 19 |
| `emergency` | سريري | حالات الطوارئ، الفرز، لوحة الطوارئ | 4 |
| `nursing` | سريري | رعاية المرضى، eMAR، العلامات الحيوية، الأسرّة | 8 |
| `billing` | مالي | الفواتير، الدفعات، الإيصالات، التأمين، الأقساط | 27 |
| `inventory` | إداري | المستودعات، المشتريات، المخزون، الباركود | 11 |
| `appointments` | إداري | جدولة المواعيد، الحجز الإلكتروني | 5 |
| `reporting` | إداري | التقارير الطبية/المالية، مستودع البيانات | 14 |
| `owner` | تكامل | لوحة المالك، إدارة المستأجرين، المنصة | 0 |
| `portal` | سريري | بوابة المريض (نتائج، مواعيد، فواتير) | 5 |
| `ai_imaging` | سريري | تحليل الصور الطبية بالذكاء الاصطناعي | 5 |
| `integration` | تكامل | FHIR، SSO، DICOM listener | 12 |
| `clinic_intake` | سريري | استقبال العيادة (استمارات ديناميكية) | 3 |
| `lab_intake` | سريري | استقبال المختبر | 4 |
| `radiology_intake` | سريري | استقبال الأشعة | 3 |
| `pharmacy_pos` | سريري | نقطة بيع الصيدلية | 6 |
| `pharmacy_customer_intake` | سريري | تسجيل عميل الصيدلية | 2 |
| `standalone_intake` | سريري | استقبال مستقل | 2 |
| `inpatient` | سريري | الإقامة الداخلية، إدارة الأسرّة | 9 |

**ملاحظة:** الوحدات الـ 7 الأخيرة (`*_intake`, `pharmacy_pos`, `pharmacy_customer_intake`, `standalone_intake`) هي وحدات استقبال متخصصة (`intake modules`) تُفعّل تلقائياً مع وحداتها الأم ولا تظهر في قوائم البيع المباشر.

---

## نظام الحزم (23 باقة في `product_bundles`)

| الحزمة | الوحدات النشطة | الوصف المختصر |
|---------|----------------|---------------|
| `private_doctor_clinic` | doctor, billing, appointments | طبيب منفرد بعيادة خاصة |
| `doctor_clinic_reception` | reception, doctor, billing, appointments | طبيب باستقبال ومواعيد |
| `small_clinic` | reception, doctor, billing, appointments | عيادة صغيرة |
| `doctor_clinic_full` | reception, doctor, billing, lab, radiology, appointments, pharmacy, reporting | عيادة طبيب متكاملة |
| `clinic_with_lab` | reception, doctor, lab, billing, appointments | عيادة مع مختبر |
| `clinic_with_radiology` | reception, doctor, radiology, billing, appointments | عيادة مع أشعة |
| `clinic_with_lab_radiology` | reception, doctor, lab, radiology, billing, appointments | عيادة مع مختبر وأشعة |
| `standalone_lab` | lab, billing, reporting | مختبر مستقل |
| `lab_with_reception` | reception, lab, billing, appointments, reporting | مختبر مع استقبال |
| `standalone_radiology` | radiology, billing, reporting | مركز أشعة مستقل |
| `radiology_with_reception` | reception, radiology, billing, appointments, reporting | أشعة مع استقبال |
| `standalone_pharmacy` | pharmacy, inventory, billing | صيدلية مستقلة |
| `standalone_emergency` | reception, emergency, doctor, nursing, billing | طوارئ مستقلة |
| `walkin_clinic` | reception, doctor, billing, pharmacy | عيادة بدون مواعيد |
| `urgent_care` | reception, doctor, emergency, nursing, billing, lab, radiology, pharmacy | مركز إسعاف وعناية عاجلة |
| `diagnostic_center` | reception, lab, radiology, billing, reporting | مركز تشخيص (مختبر + أشعة) |
| `community_clinic` | reception, doctor, nursing, billing, appointments, lab, pharmacy, reporting | مركز صحي مجتمعي |
| `nursing_home` | reception, nursing, doctor, appointments, pharmacy, inventory | دار رعاية تمريضية |
| `multi_department_center` | 11 وحدة (كل شيء ما عدا portal/ai_imaging/integration/intake) | مركز طبي متعدد الأقسام |
| `polyclinic` | 12 وحدة (+ portal) | مجمع عيادات مع بوابة مرضى |
| `hospital` | 14 وحدة (شاملة ai_imaging, integration) | مستشفى كامل |
| `billing_only` | billing, appointments | فوترة ومواعيد فقط |
| `custom` | billing, reporting (قاعدة مضمّنة) | حسب الطلب |

---

## الأدوار والصلاحيات (17 دور قابل للتعيين)

| الدور | المستوى | الوحدة المطلوبة للدخول | لوحة التحكم |
|--------|---------|----------------------|-------------|
| `super_admin` | منصة | owner (دائم) | `owner.owner_dashboard` |
| `platform_owner` (اسم بديل) | منصة | owner (دائم) | `owner.owner_dashboard` |
| `owner` | مالك المركز | owner (دائم) | `owner.owner_dashboard` |
| `admin` | مدير المركز | أول وحدة سريرية في الحزمة | أول لوحة سريرية |
| `manager` | تدبير | أول وحدة سريرية في الحزمة | أول لوحة سريرية |
| `doctor` | سريري | doctor | `doctor.dashboard` |
| `er_doctor` | طوارئ | emergency | `emergency.dashboard` |
| `nurse` | سريري | nursing | `nurse.dashboard` |
| `reception` / `receptionist` | إداري | reception | `reception.dashboard` |
| `accountant` / `tenant_admin` | مالي | billing | `accountant.dashboard` |
| `pharmacist` | سريري | pharmacy | `medication.dashboard` |
| `lab` / `lab_tech` / `technician` | سريري | lab | `lab.dashboard` |
| `radiology` | سريري | radiology | `radiology.dashboard` |
| `emergency` | سريري | emergency | `emergency.dashboard` |
| `patient` | مريض | portal (دائم) | `portal.dashboard` |
| `user` | أولي | — (مغلوق) | `main.package_restricted` |

**آلية الدخول:** `resolve_dashboard_for_user()` يفحص `ROLE_TO_MODULE_MAP` ويتحقق من تفعيل الوحدة في المستأجر (`g.enabled_modules`). إذا لم تكن الوحدة مفعّلة → `main.package_restricted`.

---

## عزل البيانات (RLS)

| المقياس | القيمة |
|----------|-------|
| جداول عامة (`public`) | 227 |
| جداول عالمية (بلا `tenant_id`) | 18 |
| جداول منصة بـ `tenant_id` (قائمة استثنائية) | 7 |
| **جداول tenant-scoped تحت RLS مفعّل + FORCE** | **202** |
| سياسات PostgreSQL إجمالاً | 210 |
| جدول بلا سياسة / سياسة بلا ربط `app.tenant_id` | 0 / 0 |

**نمط السياسة:** `USING (tenant_id = NULLIF(current_setting('app.tenant_id'::text, true), '')::integer)` + سياسة تجاوز للمنصة (`app.bypass_rls = 'on'`).

---

## التشغيل السريع (تطوير)

```bash
# 1. متطلبات: PostgreSQL 16، Redis 7، Python 3.11+
cp .env.example .env
# عدل .env مع SECRET_KEY، DATABASE_URL، REDIS_URL

# 2. بيئة بايثون
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

# 3. قاعدة البيانات (أو docker compose up -d db redis)
flask db upgrade

# 4. بذر المنصة (RBAC + الحزم + الوحدات)
python -c "
from app_factory import create_app
from app.core.tenant.models import seed_default_bundles
from app.bootstrap.rbac_seed import seed_rbac_and_catalogs
from seeds.production_baseline import platform_tenant_scope
app = create_app('development')
with app.app_context():
    with platform_tenant_scope():
        seed_rbac_and_catalogs(db)
        seed_default_bundles()
    from app.core.platform_bootstrap import ensure_module_definitions
    ensure_module_definitions()
"

# 5. تشغيل
gunicorn -c gunicorn.conf.py wsgi:app
```

---

## الاختبارات

```bash
# بيئة الاختبار (PostgreSQL 16 + Redis على نفس المنفذ أو منفذ منفصل)
export TEST_DATABASE_URL='postgresql://med_app:med_app@127.0.0.1:5432/medical_centre_platform_test'

# تشغيل الاختبارات
pytest -q --tb=short

# شرائح محددة
pytest tests/test_tenant_rls.py tests/test_module_table_ownership.py -q
pytest tests/test_role_functional_isolation.py -q
pytest tests/test_bundle_isolation_audit.py -q

# مع التغطية
pytest --cov=app --cov=routes --cov=services --cov=models --cov=utils
```

---

## متغيرات البيئة الأساسية

| المتغير | مطلوب؟ | الوصف |
|----------|--------|---------|
| `SECRET_KEY` | ✅ نعم | مفتاح JWT/جلسة (32+ حرف) |
| `DATABASE_URL` | ✅ نعم | PostgreSQL DSN |
| `REDIS_URL` | ✅ نعم | `redis://host:6379/0` |
| `FIELD_ENCRYPTION_KEY` | ✅ نعم | تشفير حقول PHI (AES-SIV) |
| `APP_ENV` | لا | `development` / `testing` / `production` |
| `ENABLE_SAAS_MODE` | لا | `true` لتعدد المستأجرين، `false` لمركز واحد |
| `TENANT_DEFAULT_SLUG` | عند `ENABLE_SAAS_MODE=false` | slug المركز الوحيد |
| `STRIPE_SECRET_KEY` | للـ SaaS | مفتاح Stripe للإنتاج |
| `STRIPE_WEBHOOK_SECRET` | للـ SaaS | سر webhook Stripe |

---

## الأمان

- **تشفير PHI:** حقول الهوية/الهاتف بـ AES-SIV حتمي، الهوية/الهاتف بـ blind index HMAC، بحث جزئي عبر `patient_search_ngrams` (3 أحرف+).
- **RLS:** 202 جدول tenant-scoped تحت سياسات `FORCE` (210 سياسة)، نمط `NULLIF(current_setting('app.tenant_id'...)`.
- **Audit Logs:** تتبع شامل للـ PHI والإجراءات الحرجة (`phi_audit_logs`, `audit_trails`).
- **MFA / WebAuthn / SSO:** مدعوم عبر `PLATFORM_CAP_WEBAUTHN`، `PLATFORM_CAP_SSO`.
- **Superuser blocked:** في الإنتاج، `postgres`/`superuser` ممنوع من قراءة بيانات المستأجرين.

---

## المساهمات

1. أي تغيير في البنية (جداول، ميزات، CI) يجب أن يُحدّث `docs/PLATFORM_STATUS.md`.
2. النصوص في الواجهات ثنائية اللغة — لا تُضف نصاً مكتوباً داخل القوالب (استخدم `gettext` / `_()`).
3. قبل كل PR: `ruff check . && ruff format --check . && mypy app/ routes/ services/ models/ utils/ && pytest -q`.
4. نمط الكود: `ruff` (أسطر 120، اقتباسات مزدوجة، ترقيم imports).
5. التعليقات: **لا تُضاف تعليقات** ما لم يُطلب صراحة — الكود يوثق نفسه.

---

## الترخيص

ملكية خاصة — جميع الحقوق محفوظة.