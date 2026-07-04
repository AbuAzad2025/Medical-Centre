# العمليات

**نظرة عامة:** بضع أوامر واضحة وموثقة لكل مسار تشغيل عادي. لا حاجة لمسارات ملفات عشوائية أو أدلة مساعدة منفصلة.

---

## 1. الإعداد المحلي لأول مرة

```bash
# قم بتخزين متغيرات البيئة الخاصة بك
cp .env.example .env
# قم بتعديل SECRET_KEY وكلمات المرور حسب الحاجة

# التثبيت المطلوب عبر pip فقط (Linux/macOS)
python -m venv .venv && .venv/bin/pip install -r requirements.txt

# أو استخدم حزمة Docker Compose الكاملة (موصى به)
docker compose up -d --build
```

---

## 2. بدء التطبيق

**المشروع (Docker):** `docker compose up -d` ثم `curl http://localhost:8080/__health`.

**محلي (Flask):**

```bash
flask db upgrade                    # هجرة Alembic
python scripts/ops/bootstrap_platform.py   # كتالوج الباقات + SaaS setup
python run_server.py
```

**--- التطبيق HTTPS في الإنتاج:** أضف gunicorn + proxy.

---

## 3. تشغيل اختبار سلسلة التطبيق الكاملة (فقط في CI/staging)

```bash
set ENABLE_SAAS_MODE=true
python -m pytest tests/ -q --tb=short
```

يجري CI شفافة:
- يمنح دور قاعدة البيانات المحدود (`med_app_runtime`) مسؤوليات `SELECT/INSERT/UPDATE/DELETE` المناسبة على الطاولات المستأجرة في قاعدة بيانات test.
- يشغل `pytest tests/test_tenant_rls.py` كخطوة CI للتحقق من أدوار التطبيق.

---

## 4. توفير بنية قاعدة البيانات API المحدد (يحتاج أذونات PostgreSQL)

**ملاحظة:** يجب أن يتم تشغيل هذه الخطوة خارج البيئة الآمنة للتطبيق لأن الادعاء على `postgres` مع `CREATE ROLE`.

```bash
python scripts/bootstrap/setup_runtime_role.py
```

يخلق بيئة الإنتاج الآمنة المحدود `med_app_runtime` (مع `NOBYPASSRLS`) ويكتب `DATABASE_URL` الفعالة لـ Flask.

**هذا مستقل عن عامل التطبيق ولا ينبغي تشغيله تلقائياً.**

---

## 5. LLM/assistant القابل لإعادة الإنتاج (فقط في بيئة التطوير المحلية)

```bash
python scripts/dev/local_reset_seed.py --confirm-local-reset
```

**الضمانات:** فقط على المضيف المحلي/127.0.0.1، إنشاء نسخة احتياطية قبل إعادة التهيئة، يتطلب تأكيد مطابق لعنوان IP في الإنتاج.

- يرسل قاعدة بيانات test المحلية إلى ملف `pg_dump` ببيانات وصفية.
- يخلق tenant للاختبار، مستخدمين للاختبار، مسارات زيارات تجريبية صغيرة، ولوحة تحكم كاملة.
- يستخدم `User.set_password()` لتجنب تخزين كلمات المرور في الكود.

**تجنب:** لا يعيد تهيئة شيء خارج مضيف localhost/127.0.0.1::1.

---

## 6. PostgreSQL/RLS التحقق بعد عملية bootstrap

```bash
# إنشاء رول DB المحدد وتثبيته
python scripts/bootstrap/setup_runtime_role.py

# تشغيل اختبارات RLS/SaaS وتصحيح الأمان
python -m pytest tests/test_tenant_rls.py tests/test_rls_deployment_guard.py -q --tb=short
```

**ملاحظة:** هذه خطوة CI/bootstrap مطلوبة قبل تشغيل الاختبارات، وليست جزءاً من مسار تطوير التطبيق الطبيعي.

---

## 7. بيئة الإنتاج الأساسية (نعم، فقط للمشرف)

```bash
# + استخدام المفتاح المناسب|سر Stripe.
flask db upgrade
python scripts/ops/bootstrap_platform.py
```

يشمل: هجرة PostgreSQL، كتالوج منتجات SaaS، و `admin`,
`owner`, `manager`, `reception`, `doctor`, `accountant`، إلك.

---

## 8. الرعاية والإصلاح اليدوي (حالات الطوارئ فقط)

| الحالة | المكان | ملاحظة |
|-----------|----------|-------|
| النقل اليدوي لقاعدة البيانات | `scripts/manual/ready_for_migration/` | طلب manual، تأكيد قابل للاسترداد |
| التنظيف الميزاني للطوارئ | `scripts/manual/cost_reconciliation/` | مستودع أخطاء mendatory |

جميع عمليات الاسترداد اليدوية لديها `README.md` منفصل يصف سبباً، من يجب أن يشغله، الآثار الجانبية، وإجراءات الاسترداد.

---

## 9. المتغيرات البيئية (لا تخزن اسماء الخدمة)

راجع `.env.example` (لا يتم إرسالها أبداً إلى المستودع).

يمكن تعديلها بشكل آمن في:
- `docker compose` (لا حاجة لـ .env)
- `.env.local` (للتطوير) في Gitignore

---

## 10. البيئة مقابل التطوير

| البيئة | المستخدمة لـ | الرابط |
|------------|-----------|------|
| المتطور (`.venv`) | SSO عبر Safari، الاختبار السريع، التشغيل | `python run_server.py`، `python scripts/dev/local_reset_seed.py` |
| التجريبي (`docker compose`) | CI/B المستقر | `docker compose exec app python run_server.py` |
| الإنتاج (`.env + gunicorn` + proxy) | إنتاج العملاء | `gunicorn -c gunicorn.conf.py wsgi:app` |
| CI (مهاجر CI السابق) | CI | يطلق `python -m pytest` |

---

## الحفظ والتخلص عبر الأوقات

- قاعدة بيانات الإنتاج: `docker compose exec postgres pg_dump`، خارجة من النسخ الاحتياطي النظامي أو مراقبة جزء الملف.
- دليل التشغيل: `docs/OPERATIONS.md` مستودع واحد للعمليات الصحيحة.
- ذاكرة المشروع: `MEMORY.md` (يحتوي على إجراءات الطوارئ والمخاطر، الأدلة، الأمور الصعبة).

---

## جدوى بيئة التطوير المحلية

```bash
# يجب يجب يجب يجب يجب يجب يجب يجب يجب يجب يجب يجب يجب يجب يجب يجب يجب يجب يجب.
```
