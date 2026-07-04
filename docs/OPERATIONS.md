# العمليات

**نظرة عامة:** بضع أوامر واضحة وموثقة لكل مسار تشغيل عادي.

---

## 1. التطوير اليومي (Routine Development)

### بدء التطبيق محلياً

```bash
python run_server.py
```

يتوقع الرابط: `http://127.0.0.1:8080`

لا يقوم الخادم بكتابة بيانات أعمال عند بدء التشغيل.

### تشغيل التهجيرات (Migrations)

```bash
flask db upgrade
```

### تشغيل كل الاختبارات

```bash
python -m pytest tests/ -q
```

### تشغيل اختبارات PostgreSQL/RLS فقط

```bash
python -m pytest tests/test_tenant_rls.py tests/test_rls_deployment_guard.py tests/test_notification_rls_lifecycle.py -q --tb=short
```

اختبارات RLS تتطلب PostgreSQL مع دور `med_app_runtime` مفعّل.

---

## 2. إعادة تعيين بيانات التطوير المحلية (Local Demo-Data Reset)

```bash
python scripts/dev/local_reset_seed.py --confirm-local-reset
```

**الضمانات:** فقط على المضيف المحلي/127.0.0.1، إنشاء نسخة احتياطية قبل إعادة التهيئة.

---

## 3. تهيئة المنصة الأساسية (Privileged Platform Bootstrap)

يتطلب صلاحيات PostgreSQL عالية (`CREATE ROLE`، `INSERT` على جداول عامة).

```bash
# إنشاء دور قاعدة البيانات المحدود (مرة واحدة فقط)
python scripts/bootstrap/setup_runtime_role.py

# تهيئة كتالوج المنتجات والأدوار
flask db upgrade
python scripts/ops/bootstrap_platform.py
```

---

## 4. تفاصيل CI (CI Internals — لا يحتاج المطور العادي)

يستخدم CI الأمر التالي لتشغيل الاختبارات:

```bash
python -m pytest tests/ -q --tb=short
```

يتطلب CI:
- PostgreSQL 16 مع دور `med_app_runtime` (صلاحيات `SELECT/INSERT/UPDATE/DELETE` على الجداول المستأجرة).
- متغير `ENABLE_SAAS_MODE=true`.
- لا يشمل استدعاء سكربتات CI مساعدة (تم دمج التغطية في pytest).

---

## 5. النشر الإنتاجي (Production Deployment)

```bash
flask db upgrade
python scripts/ops/bootstrap_platform.py
gunicorn -c gunicorn.conf.py wsgi:app
```

يتطلب متغيرات البيئة: `SECRET_KEY`، `DATABASE_URL`، مفاتيح Stripe إن وجدت.

---

## 6. الإصلاح اليدوي (Manual / Emergency Recovery)

| الحالة | المكان |
|--------|--------|
| النقل اليدوي لقاعدة البيانات | `scripts/manual/ready_for_migration/` |
| التنظيف الميزاني للطوارئ | `scripts/manual/cost_reconciliation/` |

---

## 7. متغيرات البيئة

راجع `.env.example` (لا يتم إرسالها إلى المستودع).
