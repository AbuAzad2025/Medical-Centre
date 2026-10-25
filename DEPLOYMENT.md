# دليل النشر — Deployment Guide

دليل شامل لنشر منصة المركز الطبي في بيئات التطوير، الاختبار، والإنتاج.

---

## 1. متطلبات النظام

| المكوّن | الإصدار الأدنى | ملاحظات |
|----------|----------------|---------|
| **PostgreSQL** | 16 | وحيد المدعوم رسمياً (متحقق على 14/15/17 في CI) |
| **Redis** | 7 | للـ cache، Celery broker، SocketIO |
| **Python** | 3.11+ | 3.11/3.12 مدعومان |
| **نظام التشغيل** | Linux (Ubuntu 22.04+/Debian 12) أو Windows (تطوير فقط) |
| **ذاكرة** | 4 GB+ | 8 GB للإنتاج مع Celery workers |
| **مساحة قرص** | 20 GB+ | للمخطط، الفهارس، النسخ الاحتياطية |

---

## 2. متغيرات البيئة (`.env`)

انسخ `.env.example` إلى `.env` واملأ القيم:

```bash
cp .env.example .env
```

### مطلوبة في جميع البيئات

| المتغير | مثال | الوصف |
|----------|-------|---------|
| `SECRET_KEY` | `ci-test-secret-key-for-jwt-hs256-min32` | 32+ حرف عشوائي — **إلزامي** |
| `DATABASE_URL` | `postgresql://user:pass@host:5432/db` | DSN قاعدة البيانات |
| `REDIS_URL` | `redis://127.0.0.1:6379/0` | Redis DSN |
| `FIELD_ENCRYPTION_KEY` | `base64-encoded-32-byte-key` | لتشفير حقول PHI (AES-SIV) |

### خاصة بالبيئة

| المتغير | تطوير | اختبار | إنتاج |
|----------|--------|--------|-------|
| `APP_ENV` | `development` | `testing` | `production` |
| `FLASK_ENV` | `development` | `testing` | `production` |
| `FLASK_DEBUG` | `1` | `0` | `0` |
| `SUPPRESS_LOGGING` | `0` | `1` | `0` |
| `ENABLE_SAAS_MODE` | `false` | `true` | `true/false` |
| `TENANT_DEFAULT_SLUG` | `clinic` | — | مطلوب إذا `ENABLE_SAAS_MODE=false` |
| `DEPLOYMENT_MODE` | `standalone` | `saas` | `saas` / `standalone` |

### SaaS / فوترة (عند `ENABLE_SAAS_MODE=true`)

| المتغير | مطلوب؟ |
|----------|---------|
| `STRIPE_SECRET_KEY` | ✅ للإنتاج |
| `STRIPE_WEBHOOK_SECRET` | ✅ للإنتاج |
| `STRIPE_PUBLISHABLE_KEY` | ✅ للإنتاج |
| `STRIPE_PRICE_ID_*` | للأسعار |

### تكاملات خارجية (اختيارية)

| المتغير | الغرض |
|----------|---------|
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` | SMS |
| `WHATSAPP_BUSINESS_TOKEN` / `WHATSAPP_PHONE_ID` | WhatsApp Business |
| `OIDC_CLIENT_ID` / `OIDC_CLIENT_SECRET` / `OIDC_DISCOVERY_URL` | SSO (OIDC) |
| `MINIO_ENDPOINT` / `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | تخزين ملفات S3 |

---

## 3. النشر خطوة بخطوة

### 3.1. تطوير محلي (Windows / Linux / macOS)

```bash
# 1. استنساخ وتعيين بيئة
git clone https://github.com/AbuAzad2025/Medical-Centre.git
cd Medical-Centre
cp .env.example .env
# عدل .env مع قيمك

# 2. PostgreSQL + Redis (Docker أو تثبيت محلي)
docker compose up -d db redis
# أو ثبّت PostgreSQL 16 و Redis 7 محلياً

# 3. بيئة بايثون
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
.\.venv\Scripts\activate   # Windows PowerShell

pip install -r requirements.txt

# 4. ترحيل قاعدة البيانات
flask db upgrade

# 5. بذر المنصة (مرة واحدة)
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

# 6. تشغيل الخادم
gunicorn -c gunicorn.conf.py wsgi:app
# أو للتطوير مع إعادة تحميل:
flask run --host=0.0.0.0 --port=5000
```

### 3.2. النشر باستخدام Docker Compose (إنتاج)

```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-medical_centre}
      POSTGRES_USER: ${POSTGRES_USER:-med_app}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./scripts/ops/init_extensions.sql:/docker-entrypoint-initdb.d/init_extensions.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U \${POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    volumes:
      - redisdata:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  app:
    build:
      context: .
      dockerfile: Dockerfile.prod
    environment:
      - APP_ENV=production
      - ENABLE_SAAS_MODE=true
      - SECRET_KEY=${SECRET_KEY}
      - DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
      - REDIS_URL=redis://redis:6379/0
      - FIELD_ENCRYPTION_KEY=${FIELD_ENCRYPTION_KEY}
      - STRIPE_SECRET_KEY=${STRIPE_SECRET_KEY}
      - STRIPE_WEBHOOK_SECRET=${STRIPE_WEBHOOK_SECRET}
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    ports:
      - "8080:8080"
    command: >
      sh -c "
        flask db upgrade &&
        python -c \"
        from app_factory import create_app
        from app.core.tenant.models import seed_default_bundles
        from app.bootstrap.rbac_seed import seed_rbac_and_catalogs
        from seeds.production_baseline import platform_tenant_scope
        from app.core.platform_bootstrap import ensure_module_definitions
        app = create_app('production')
        with app.app_context():
            with platform_tenant_scope():
                seed_rbac_and_catalogs(db)
                seed_default_bundles()
            ensure_module_definitions()
        \" &&
        gunicorn -c gunicorn.conf.py wsgi:app
      "

  celery-worker:
    build:
      context: .
      dockerfile: Dockerfile.prod
    command: celery -A wsgi:app.celery worker -l INFO
    depends_on:
      - redis
      - db

  celery-beat:
    build:
      context: .
      dockerfile: Dockerfile.prod
    command: celery -A wsgi:app.celery beat -l INFO
    depends_on:
      - redis

volumes:
  pgdata:
  redisdata:
```

```bash
# تشغيل الإنتاج
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# فحص الصحة
curl -f http://localhost:8080/health
curl -f http://localhost:8080/__health
```

---

## 4. أوامر ما بعد النشر

```bash
# داخل حاوية app أو بيئة مُفعّلة

# التحقق من المخطط
python scripts/ci/verify_migrations.py

# تدقيق RLS
python scripts/ci/audit_rls_coverage.py

# التحقق من الحزم والبذور
flask module-seed   # يفعّل كل الوحدات لكل المستأجرين (للإنتاج الأولي فقط)

# التحقق من صحة البذور
python -c "
from app_factory import create_app
from app.core.tenant.models import ProductBundle
app = create_app('production')
with app.app_context():
    for b in ProductBundle.query.filter_by(is_active=True).all():
        print(b.slug, '->', b.get_modules())
"
```

---

## 5. إعدادات إنتاج مهمة

### 5.1. قاعدة البيانات
- **RLS:** مفروض افتراضياً — لا تعطّل `row_security`.
- **Superuser:** لا يستخدم `postgres` للوصول التطبيقي — التطبيق يستخدم دور `med_app` مع `NOSUPERUSER NOBYPASSRLS`.
- **فهرس `btree_gist`:** مطلوب لقيود الاستبعاد (يتم إنشاؤه في `conftest.py` للاختبارات، في الإنتاج أضف `CREATE EXTENSION IF NOT EXISTS btree_gist;` في سكريبت `init_extensions.sql`).

### 5.2. Redis
- `maxmemory-policy: allkeys-lru`
- تعطيل `persistence` إذا كان للتخزين المؤقت فقط (RDB/AOF غير مطلوبين للـ Celery broker).

### 5.3. Nginx (Reverse Proxy)
```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    client_max_body_size 50M;

    location / {
        proxy_pass http://app:8080;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120s;
    }

    location /socket.io/ {
        proxy_pass http://app:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_read_timeout 86400;
    }
}
```

### 5.4. SSL / TLS
- استخدم شهادات Let's Encrypt (Certbot) أو شهادات مدارة.
- `SECURE_SSL_REDIRECT = True` في الإنتاج (Flask-Talisman أو middleware مخصص).

---

## 6. النسخ الاحتياطي والاستعادة

```bash
# نسخة احتياطية منطقية (pg_dump)
pg_dump -h localhost -U med_app -d medical_centre -Fc -f backup_$(date +%F_%H-%M).dump

# استعادة
pg_restore -h localhost -U med_app -d medical_centre -c backup_2026-01-15_03-00.dump

# نسخة احتياطية عبر المنصة (API)
curl -X POST http://localhost:8080/super-admin/backup/create \
  -H "Content-Type: application/json" \
  -d '{"type": "full"}' \
  -u super_admin:password
```

---

## 7. الترقية (Upgrades)

```bash
# 1. إيقاف العمال
docker compose stop celery-worker celery-beat

# 2. سحب الكود الجديد
git pull origin main

# 3. بناء الصور الجديدة
docker compose -f docker-compose.yml -f docker-compose.prod.yml build

# 4. ترحيل قاعدة البيانات (قبل تشغيل التطبيق الجديد!)
docker compose run --rm app flask db upgrade

# 5. تشغيل الخدمات
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 6. التحقق
curl -f http://localhost:8080/health
python scripts/ci/verify_migrations.py
```

---

## 8. استكشاف الأخطاء الشائعة

| المشكلة | السبب | الحل |
|----------|-------|-------|
| `RuntimeError: SECRET_KEY environment variable is required` | متغير مفقود | أضف `SECRET_KEY` في `.env` |
| `psycopg2.errors.InsufficientPrivilege` RLS | لا يوجد `app.tenant_id` | استخدم `platform_tenant_scope()` للبذر، أو تأكد من middleware tenant |
| `DuplicateTable` أثناء `flask db upgrade` | قاعدة بيانات غير نظيفة | اسقط المخطط (`db.drop_all()` مع CASCADE) ثم `flask db upgrade` |
| `ModuleNotEnabledError` عند الدخول | دور يتطلب وحدة غير مفعلة | فعّل الوحدة للمستأجر عبر `tenant_modules` أو غيّر الباقة |
| `Connection refused` Redis | Redis غير متاح | تحقق من `REDIS_URL`، صحة الحاوية `redis` |

---

## 9. التحقق بعد النشر

```bash
# 1. نقاط الصحة
curl -f https://your-domain.com/health
curl -f https://your-domain.com/__health

# 2. تحقق المخطط
python scripts/ci/verify_migrations.py

# 3. تدقيق RLS
python scripts/ci/audit_rls_coverage.py

# 4. تسجيل دخول تجريبي
# افتح https://your-domain.com وسجل دخول ببيانات صحيحة
```

---

## 10. المراجع

- [PLATFORM_STATUS.md](PLATFORM_STATUS.md) — الحالة التقنية والأرقام
- [ARCHITECTURE.md](ARCHITECTURE.md) — المعمارية والأنماط
- [OPERATIONS.md](OPERATIONS.md) — عمليات التشغيل اليومية
- [scripts/ops/README.md](../scripts/ops/README.md) — أوامر التشغيل المتاحة