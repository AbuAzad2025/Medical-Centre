# دليل المطور — Developer Guide

دليل شامل لإعداد بيئة التطوير، تشغيل الاختبارات، إضافة الميزات، والمساهمة في المنصة.

---

## 1. إعداد بيئة التطوير

### 1.1. المتطلبات

| الأداة | الإصدار | التثبيت |
|--------|---------|---------|
| Python | 3.11+ | `pyenv` أو التثبيت الرسمي |
| PostgreSQL | 16 | `brew install postgresql@16` / `apt install postgresql-16` |
| Redis | 7 | `brew install redis` / `apt install redis-server` |
| Node.js | 18+ | لـ frontend tooling (Vitest, Stylelint, cspell) |
| Git | 2.40+ | |
| Docker | اختياري | لبيئة متطابقة مع CI |

### 1.2. الإعداد السريع (Windows PowerShell)

```powershell
# 1. استنساخ
git clone https://github.com/AbuAzad2025/Medical-Centre.git
cd Medical-Centre

# 2. متغيرات البيئة
cp .env.example .env
# عدل .env:
# SECRET_KEY=dev-secret-key-32-chars-minimum
# DATABASE_URL=postgresql://med_app:med_app@127.0.0.1:5432/medical_centre_platform_dev
# REDIS_URL=redis://127.0.0.1:6379/0
# FIELD_ENCRYPTION_KEY=base64-encoded-32-byte-key
# APP_ENV=development
# FLASK_DEBUG=1

# 3. قاعدة البيانات (إذا لم تستخدم Docker)
createdb medical_centre_platform_dev
createuser med_app -P  # كلمة مرور: med_app
psql -d medical_centre_platform_dev -c "GRANT ALL PRIVILEGES ON DATABASE medical_centre_platform_dev TO med_app;"

# 4. بيئة بايثون
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 5. Node.js (للواجهة)
npm ci

# 6. ترحيل قاعدة البيانات
flask db upgrade

# 7. بذر المنصة (RBAC + الحزم + الوحدات)
python -c "
from app_factory import create_app
from app.core.tenant.models import seed_default_bundles
from app.bootstrap.rbac_seed import seed_rbac_and_catalogs
from seeds.production_baseline import platform_tenant_scope
from app.core.platform_bootstrap import ensure_module_definitions
app = create_app('development')
with app.app_context():
    with platform_tenant_scope():
        seed_rbac_and_catalogs(db)
        seed_default_bundles()
    ensure_module_definitions()
"

# 8. تشغيل الخادم
flask run --host=0.0.0.0 --port=5000
# أو مع gunicorn للتطوير:
gunicorn -c gunicorn.conf.py wsgi:app --reload
```

### 1.3. باستخدام Docker Compose (موصى به للتطابق مع CI)

```bash
# تطوير
docker compose up -d db redis
# ثم خطوات 3-8 أعلاه

# أو بيئة كاملة في حاويات
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

---

## 2. تشغيل الاختبارات

### 2.1. متغيرات بيئة الاختبار

```bash
export TEST_DATABASE_URL='postgresql://med_app:med_app@127.0.0.1:5432/medical_centre_platform_test'
export DATABASE_URL='postgresql://med_app:med_app@127.0.0.1:5432/medical_centre_platform_test'
```

> **ملاحظة:** قاعدة بيانات الاختبار تُبنى من الصفر في كل تشغيل CI عبر `conftest.py::_migrate_test_schema()` — تهجرات Alembic + بذور RBAC + حزم.

### 2.2. أوامر الاختبار الشائعة

```bash
# كل الاختبارات (قد يستغرق 20-30 دقيقة)
pytest -q --tb=short

# اختبارات سريعة (الوحدة فقط)
pytest tests/unit -q --tb=short

# اختبارات محددة
pytest tests/test_tenant_rls.py tests/test_module_table_ownership.py -q --tb=short
pytest tests/test_role_functional_isolation.py -q --tb=short
pytest tests/test_bundle_isolation_audit.py -q --tb=short

# مع التغطية
pytest --cov=app --cov=routes --cov=services --cov=models --cov=utils \
  --cov-report=term-missing --cov-report=html

# تشغيل شريحة واحدة من core (كما في CI)
pytest tests/ -q --tb=short \
  --ignore=tests/unit --ignore=tests/integration --ignore=tests/clinical \
  --ignore=tests/test_route_inventory.py \
  --splits 4 --group 1

# واجهة المستخدم (Vitest)
npx vitest run
```

### 2.3. علامات الاختبار (Pytest Marks)

| العلامة | الوصف | مثال |
|---------|--------|-------|
| `@pytest.mark.e2e` | اختبارات نهاية إلى نهاية (بطيئة) | `pytest -m e2e` |
| `@pytest.mark.db` | تحتاج قاعدة بيانات | `pytest -m db` |
| `@pytest.mark.skipif` | تخطي شرطي | `pytest -m "not e2e"` |
| `@pytest.mark.xfail` | متوقع الفشل (صارم + سبب) | **لا توجد علامات xfail نشطة** |

---

## 3. هيكل المشروع (مختصر)

```
Medical-Centre/
├── app/                    # كود التطبيق الرئيسي
│   ├── core/               # البنية التحتية الأساسية
│   │   ├── module/         # سجل الوحدات، التحقق
│   │   ├── saas/           # دورة حياة المستأجر، الفوترة
│   │   ├── tenant/         # نماذج المستأجر، middleware
│   │   └── platform_bootstrap.py
│   ├── shared/             # مشترك بين الوحدات
│   │   ├── tenant_filter.py    # فلتر ORM + RLS
│   │   ├── user_role_policy.py # سياسات الأدوار
│   │   ├── dashboard_registry.py # واجهة commandes
│   │   └── nav_resolver.py     # تنقل ديناميكي
│   ├── modules/            # الوحدات الوظيفية (blueprints)
│   └── bootstrap/          # بذور RBAC
├── routes/                 # Blueprints مسارات HTTP
├── services/               # طبقة الخدمات (domain logic)
├── models/                 # نماذج SQLAlchemy (224)
├── utils/                  # أدوات مساعدة (decorators, etc.)
├── migrations/             # Alembic (67 ملف)
├── seeds/                  # بذور الإنتاج
├── tests/                  # 212 ملف اختبار
│   ├── unit/               # وحدة
│   ├── integration/        # تكامل
│   ├── clinical/           # سريرية
│   └── *.py                # ملفات الجذر (core shards)
├── scripts/                # سكريبتات التشغيل
│   ├── ci/                 # بوابات CI
│   └── ops/                # عمليات التشغيل
├── scripts/ops/bootstrap_platform.py  # بذر شامل
├── app_factory.py          # نقطة الدخول (create_app)
├── wsgi.py                 # نقطة دخول Gunicorn
├── gunicorn.conf.py        # إعدادات الإنتاج
├── requirements.txt        # تبعيات Python
├── package.json            # تبعيات Node.js
└── .github/workflows/ci.yml # CI Pipeline (23 وظيفة)
```

---

## 4. إضافة ميزة جديدة (Workflow)

### 4.1. وحدة جديدة (Module)

1. **سجل الوحدة** في `app/core/module/registry.py`:
```python
ModuleMeta(
    name='new_module',
    name_ar='وحدة جديدة',
    category='clinical',
    capabilities=('cap1', 'cap2'),
    tables=('table1', 'table2'),  # مطالبة الجداول
    standalone_allowed=True,
    default_route='/new-module/dashboard',
    route_prefixes=('/new-module',),
)
```

2. **أنشئ Blueprint** في `app/modules/new_module/`:
```
app/modules/new_module/
├── __init__.py          # bp = Blueprint('new_module', ...)
├── routes.py            # المسارات
├── models.py            # نماذج SQLAlchemy (إن وجدت)
├── services.py          # منطق العمل
└── templates/new_module/ # قوالب Jinja2
```

3. **سجل الـ Blueprint** في `app_factory.py` (بترتيب التبعيات).

4. **أضف اختبارات**:
```bash
# tests/test_new_module.py
# tests/test_new_module_isolation.py (عزل الوحدة)
```

5. **أضف(unit/intake) إذا لزم** — سجل في `MODULE_REGISTRY` مع `category='clinical'` أو `administrative`.

### 4.2. حزمة جديدة (Bundle)

1. **أضف في `_PRODUCT_PROFILE_SEED`** (`app/core/tenant/models.py`):
```python
'new_bundle': {
    'modules': ['reception', 'doctor', 'new_module'],
    'bundle_slug': 'new_bundle',
    'monthly_price': 999,
    'max_users': 10,
    'max_patients': 5000,
}
```

2. **أضف `Package` + `PackageVersion` + `PackageVersionEntitlement`** في `seed_default_bundles()`.

3. **اختبر**: `pytest tests/test_bundle_isolation_audit.py -k new_bundle -q`

### 4.3. دور جديد (Role)

1. **أضف في `ASSIGNABLE_ROLES`** و `CLINICAL_STAFF_ROLES` في `app/shared/user_role_policy.py`.

2. **أضف في `ROLE_HIERARCHY`** و `ROLE_TO_MODULE_MAP` في `utils/decorators.py` و `services/dashboard_routing.py`.

3. **أضف في `ROLE_LAYOUTS`** في `app/shared/dashboard_registry.py` (widgets + التنقل).

4. **حدّث `models/user.py`** constraint `role` regex.

5. **اختبر**: `pytest tests/test_role_functional_isolation.py -q`

---

## 5. العمل مع قاعدة البيانات

### 5.1. إنشاء تهجير (Migration)

```bash
# إنشاء تلقائي (بعد تغيير النماذج)
flask db migrate -m "وصف التغيير"

# أو يدوي للمخططات المعقدة
# أنشئ ملف في migrations/versions/ يدوياً
```

**قواعد التهجير:**
- لا `create_all` في الكود — Alembic فقط.
- كل جدول `tenant-scoped` يجب أن يحصل على سياسة RLS في نفس التهجير.
- استخدم `migration_utils.py` للوظائف المساعدة (`create_tenant_isolation_policy`).
- تهجيرات `s3_*` = نظام SaaS/RLS، `p*` = ميزات المنصة.

### 5.2. تشغيل التهجيرات

```bash
# تطوير
flask db upgrade

# إنتاج (داخل حاوية app)
flask db upgrade

# التحقق
python scripts/ci/verify_migrations.py
```

### 5.3. فحص المخطط

```bash
# تدقيق RLS
python scripts/ci/audit_rls_coverage.py

# تدقيق سياسات عميق
python scripts/ci/rls_deep_audit.py

# التحقق من انحراف ORM vs DB
flask db check
```

---

## 6. قواعد الكود والجودة (Code Quality Gates)

### 6.1. قبل كل Commit/PR

```bash
# 1. تنسيق + lint
ruff check . --fix
ruff format .

# 2. Type checking
mypy app/ routes/ services/ models/ utils/ --explicit-package-bases

# 3. اختبارات سريعة
pytest tests/test_module_table_ownership.py tests/test_tenant_rls.py -q

# 4. فحص الأمان
bandit -r app/ routes/ services/ -lll
pip-audit -r requirements.txt
```

### 6.2. بوابات CI (يجب أن تمر جميعها)

| البوابة | الأمر | المهلة |
|----------|--------|--------|
| `ruff format --check` | `ruff format --check .` | صارم |
| `ruff check` | `ruff check . --select I001 --fix` ثم `ruff check . --statistics` | صارم |
| `mypy` | `mypy app/ routes/ services/ models/ utils/ --explicit-package-bases` | صارم |
| `pip-audit` | `pip-audit -r requirements.txt` | صارم |
| `bandit` | `bandit -r app/ routes/ services/ -lll` (0 high) | صارم |
| `templates-i18n` | تحليل Jinja2 + كشف نصوص غير مترجمة | صارم |
| `RLS audit` | `audit_rls_coverage.py` (202/202) | صارم |
| `verify_migrations` | upgrade على PG فارغ + bootstrap | صارم |

---

## 7. التصحيح الشائع (Debugging)

| المشكلة | التشخيص | الحل |
|---------|----------|-------|
| `ModuleNotEnabledError` | وحدة مطلوبة غير مفعلة للمستأجر | تحقق `tenant_modules`، فعّل الوحدة أو غيّر الباقة |
| `TenantIsolationError` | فلتر ORM لم يجد `tenant_id` | تأكد من `g.tenant_id` أو `platform_tenant_scope()` |
| `InsufficientPrivilege` RLS | كتابة في جدول RLS بدون `app.tenant_id` | استخدم `platform_tenant_scope()` للبذر/المهام |
| `DuplicateTable` في migrate | قاعدة بيانات غير نظيفة | `db.drop_all()` مع CASCADE ثم `flask db upgrade` |
| اختبار يفشل عشوائياً | تلوث قاعدة بيانات من عملية متوازية | تأكد من `TEST_DATABASE_URL` منفصل، لا عمليات pytest متزامنة |

---

## 8. أوامر مفيدة (Cheat Sheet)

```bash
# غلاف Flask مع سياق تطبيق
flask shell

# تشغيل سكريبت مع سياق تطبيق
flask run-script myscript.py

# إنشاء مستخدم super_admin
flask create-super-admin --email admin@domain.com --password "Pass123!"

# بذر الوحدات لكل المستأجرين (خطر في إنتاج!)
flask module-seed

# إنشاء مستأجر جديد يدوياً
flask tenant-create --slug myclinic --name "My Clinic" --package doctor_clinic_full

# تصدير OpenAPI spec
flask openapi-export > openapi.json

# فحص الترجمات المفقودة
pybabel extract -F babel.cfg -o messages.pot .
pybabel update -i messages.pot -d translations

# تشغيل Celery worker محلياً
celery -A wsgi:app.celery worker -l INFO

# تشغيل Celery beat (المهام المجدولة)
celery -A wsgi:app.celery beat -l INFO
```

---

## 9. المساهمة (Contributing)

1. **فرع (fork)** المستودع.
2. **فرع ميزة:** `git checkout -b feature/amazing-feature`.
3. **تطوير** مع الاختبارات المحلية الخضراء.
4. **بوابات الجودة:** `ruff check . && ruff format --check . && mypy ... && pytest -q`.
5. **Commit** برسالة واضحة: `feat(module): add new capability for X`.
6. **Push** وافتح **Pull Request**.
7. **CI** يجب أن يكون أخضر (23/23).
8. **مراجعة** ودمج.

**نمط commit messages:**
```
feat(module): add drug interaction checking for pharmacy
fix(routing): er_doctor now lands on emergency dashboard
docs(arch): update RLS policy count to 210
refactor(tenant): simplify module scope caching
test(isolation): add bundle isolation for new_bundle
chore(deps): update Flask to 3.1.1
```

---

## 10. موارد مفيدة

- **التوثيق التقني:** `docs/ARCHITECTURE.md`، `docs/PLATFORM_STATUS.md`
- **CI Pipeline:** `.github/workflows/ci.yml`
- **سكريبتات التشغيل:** `scripts/ops/README.md`
- **قاعدة البيانات:** `scripts/ci/verify_migrations.py`، `scripts/ci/audit_rls_coverage.py`
- **Issues/Discussions:** GitHub Issues للمشاكل، Discussions للأسئلة التصميمية