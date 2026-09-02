# دليل النشر — Deployment

> مرجع النشر ومتغيرات البيئة. آخر تحقق من الكود: **2 سبتمبر 2026** — الإصدار 3.1 — رأس `f224b8d0c4d2`.

---

## 1. متطلبات التشغيل

| المكوّن | الإصدار |
|---------|---------|
| Docker + Docker Compose | أي حديث يدعم compose v2 |
| PostgreSQL | **16** (وحيد المدعوم — يُبنى عبر الحاوية) |
| Redis | **7** |
| Python | 3.11+ (لتطوير خارج الحاوية فقط) |

---

## 2. متغيرات البيئة (من `.env.example`)

| المتغير | إلزامي؟ | الوصف |
|---------|---------|-------|
| `SECRET_KEY` | نعم | مفتاح الجلسات — `docker compose` يفشل بدونه |
| `FIELD_ENCRYPTION_KEY` | نعم* | تشفير الحقول الحساسة (PHI) |
| `DATABASE_URL` | نعم | DSN PostgreSQL للحاوية يُبنى من `PG_USER/PG_PASSWORD/PG_DB_NAME` |
| `TEST_DATABASE_URL` | للاختبار | قاعدة بيانات الاختبارات |
| `REDIS_URL` | نعم | `redis://redis:6379/0` |
| `CELERY_BROKER_URL` | نعم | نفس Redis |
| `CELERY_ENABLED` | لا | `true` لتشغيل المهام الخلفية |
| `ENABLE_SAAS_MODE` | لا | `true` للوضع السحابي متعدد المستأجرين |
| `DEPLOYMENT_MODE` | لا | `saas` أو `single` |
| `TENANT_RESOLUTION_MODE` | لا | `domain` / `subdomain` / `path` |
| `PLATFORM_OWNER_API_KEY` | لا | مفتاح واجهة المالك (SaaS) |
| `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` | لا (حتى go-live) | فوترة Stripe |
| `WHATSAPP_API_TOKEN` + `PHONE_NUMBER_ID` + `BUSINESS_ACCOUNT_ID` + `WEBHOOK_VERIFY_TOKEN` | لا | WhatsApp Business API |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_PHONE_NUMBER` | لا | SMS (إنتاج) |
| `MAIL_SERVER` / `MAIL_PORT` / `MAIL_USERNAME` / `MAIL_PASSWORD` / `MAIL_USE_TLS` | لا | البريد |
| `DEFAULT_ADMIN_NAME` / `DEFAULT_ADMIN_EMAIL` / `DEFAULT_ADMIN_PASSWORD` | لا | مدير المنصة الافتراضي |
| `BIOMETRIC_DEVICE_ENABLED` | لا | جهاز بصمات |
| `PLATFORM_CAP_WEBAUTHN` / `PLATFORM_CAP_FHIR` / `PLATFORM_CAP_SSO` / `PLATFORM_CAP_SMS_LIVE` | لا | تفعيل قدرات المنصة |

> كل المتغيرات موثّقة قيمها الافتراضية في `.env.example`.

---

## 3. التشغيل (تطوير)

```bash
cp .env.example .env
# عدّل SECRET_KEY + FIELD_ENCRYPTION_KEY
docker compose up -d --build
```

الحاوية `app` تنفّذ تلقائياً عند الإقلاع:

```bash
flask db upgrade
python scripts/ops/bootstrap_platform.py
gunicorn -c gunicorn.conf.py wsgi:app
```

| الخدمة | المنفذ |
|--------|--------|
| التطبيق | `8080` |
| PostgreSQL | `5432` |
| Redis | `6379` |
| Prometheus exporter (isolate metrics) | `9180` |

---

## 4. التشغيل (إنتاج)

```bash
export SECRET_KEY=... FIELD_ENCRYPTION_KEY=... DB_USER=... DB_PASSWORD=... DB_NAME=...
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

`docker-compose.prod.yml` يضيف:

- `restart: unless-stopped` + healthcheck (`/health`) لكل الخدمات.
- حدود موارد (CPU/ذاكرة) لكل خدمة.
- PostgreSQL مع تلقيم منضبط (`max_connections=200`, `shared_buffers=256MB`...).
- Redis مع `appendonly` + حد ذاكرة.
- ميناءا DB/Redis محصوران على `127.0.0.1` (لا تُفتح خارجياً).
- Worker بموازاة 4: `celery -A celery_app.celery worker --concurrency=4`.
- صورة node-exporter للمقاييس.

**قبل go-live:**

1. `curl -f https://<host>/health` و `curl -f https://<host>/__health`.
2. `python scripts/ci/verify_migrations.py` للتأكد من التهجيرات ورأس واحد.
3. راجع `docs/PLATFORM_STATUS.md` لقسم «التحقق السريع بعد النشر».
4. راجع `COMMERCIAL_READINESS_AUDIT.md` (86 فحصاً) و `PRE_PILOT_VERIFICATION_REPORT.md`.

---

## 5. الهجرات (Migrations)

- رأس التهجيرات الحالي: **`f224b8d0c4d2`** (`s3_007_add_missing_system_configs` → `clean_old_rules`, 59 revision).
- التشغيل: `flask db upgrade` (تلقائي داخل حاوية `app`).
- **إنتاج Multi-tenant:** لا تشغّل `flask module-seed` — يفعّل كل الوحدات لكل المستأجرين (خطر).
- `migrations/manual_scripts/` يدوي — لا يدخل في `upgrade`.

### جدول جديد؟

- يجب أن يرث `TenantMixin` وأن يمرر `__tenant_migration__ = True`.
- سيتم إدراجه تلقائياً في تتبع RLS — أعد تشغيل `scripts/ci/audit_rls_coverage.py` للتحقق.
- حدّث `docs/PLATFORM_STATUS.md`.

---

## 6. النسخ الاحتياطي

PostgreSQL (مثال يومي):

```bash
docker compose exec db pg_dump -U "$DB_USER" "$DB_NAME" | gzip > backups/$(date +%F).sql.gz
```

> حاوية `db` في prod تركّب `./backups:/backups` لتسهيل السحب.

---

## 7. المشاكل الشائعة

| المشكلة | الحل |
|---------|------|
| `SECRET_KEY required` | المتغير غير موجود في `.env` |
| توقف عند تشفير PHI | تأكد من `FIELD_ENCRYPTION_KEY` قبل أول تشغيل |
| RLS يرفض superuser | وضع الإنتاج يرفض اتصالات superuser — استخدم مستخدم `med_app_runtime` |
| تغيّر في فهرس RLS | `audit_rls_coverage.py` يحدد الجداول الناقصة |

---

## 8. CI

15 وظيفة في `.github/workflows/ci.yml` — أي تغيير جديد يمر عبر: تهجيرات على PG فارغ، bootstrap، تدقيق RLS، أمان (bandit/mypy/pip-audit)، قوالب، تدقيق إملائي.
