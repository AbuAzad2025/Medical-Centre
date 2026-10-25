# عمليات التشغيل والصيانة — Operations Guide

دليل شامل للعمليات اليومية، الصيانة الدورية، استكشاف الأخطاء، والاستجابة للحوادث في بيئة الإنتاج.

---

## 1. المراقبة اليومية (Daily Operations)

### 1.1. فحوصات الصحة (Health Checks)

```bash
# 1. نقطة الصحة الأساسية (لـ Load Balancer)
curl -f https://your-domain.com/health
# متوقع: 200 OK {"status": "healthy"}

# 2. نقطة الصحة المفصلة (قاعدة البيانات، Redis، التهجيرات)
curl -f https://your-domain.com/__health
# متوقع: 200 OK مع JSON مفصل:
# {
#   "database": "connected",
#   "redis": "connected",
#   "migrations": "current",
#   "rls_policies": 210,
#   "tenant_count": 42
# }

# 3. فحص مقاييس Prometheus
curl https://your-domain.com/metrics | head -20
```

**معدلات SLA المستهدفة:**
- `/health` < 100ms
- `/__health` < 500ms
- توفر الخدمة: 99.9%

### 1.2. مراقبة قاعدة البيانات

```bash
# عدد الاتصالات النشطة
psql -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';"

# استعلامات بطيئة (> 1 ثانية)
psql -c "SELECT pid, now() - query_start AS duration, query FROM pg_stat_activity WHERE state = 'active' AND now() - query_start > interval '1 second';"

# حجم الجداول الأكبر
psql -c "SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size FROM pg_tables WHERE schemaname='public' ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC LIMIT 20;"

# حالة RLS (يجب أن يكون 202 جدول FORCE)
psql -c "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relrowsecurity AND c.relforcerowsecurity;"
```

### 1.3. مراقبة Celery / Redis

```bash
# طابور المهام
celery -A wsgi:app.celery inspect active
celery -A wsgi:app.celery inspect reserved
celery -A wsgi:app.celery inspect stats

# طول الطوابير
redis-cli LLEN celery
redis-cli LLEN celery:low_priority

# مهام فاشلة
celery -A wsgi:app.celery control inspect failed
```

---

## 2. الصيانة الدورية (Scheduled Maintenance)

### 2.1. يومي (Automated via Celery Beat)

| المهمة | الجدولة | الأمر |
|--------|---------|-------|
| تنظيف الجلسات المنتهية | كل 6 ساعات | `session_cleanup` |
| معالجة طابور الإشعارات | كل 5 دقائق | `process_notification_queue` |
| مزامنة مستودع البيانات | يومياً 02:00 | `sync_data_warehouse` |
| فحص سلامة RLS | يومياً 03:00 | `audit_rls_enforcement` |
| نسخ احتياطي تلقائي | يومياً 01:00 | `create_backup` (full) |

### 2.2. أسبوعي

```bash
# 1. تحليل الفهارس (ANALYZE)
psql -c "ANALYZE VERBOSE;"

# 2. فحص سلامة القيود (Foreign Keys)
psql -c "SELECT conname, conrelid::regclass, confrelid::regclass FROM pg_constraint WHERE contype = 'f' AND NOT convalidated;"

# 3. تقرير استخدام القرص
psql -c "SELECT pg_size_pretty(pg_database_size(current_database()));"

# 4. مراجعة سجلات التدقيق (آخر 7 أيام)
psql -c "SELECT count(*), action FROM audit_trails WHERE created_at > now() - interval '7 days' GROUP BY action ORDER BY count DESC;"
```

### 2.3. شهري

```bash
# 1. REINDEX متزامن (للفهارس المجزأة)
psql -c "REINDEX DATABASE medical_centre CONCURRENTLY;"

# 2. تحديث إحصائيات pg_stat_statements
psql -c "SELECT pg_stat_reset();"

# 3. مراجعة سياسات RLS (يجب أن تبقى 210)
psql -c "SELECT count(*) FROM pg_policy WHERE polname LIKE 'tenant_isolation_%';"

# 4. اختبار الاستعادة (DR Drill) — في بيئة staging
# pg_restore -d staging_db backup_latest.dump
```

---

## 3. النسخ الاحتياطي والاستعادة (Backup & Restore)

### 3.1. استراتيجية النسخ الاحتياطي

| النوع | التكرار | الاحتفاظ | الموقع |
|-------|---------|----------|--------|
| **Full (pg_dump -Fc)** | يومي 01:00 | 30 يوم | S3 / MinIO مشفر |
| **Incremental (WAL-G)** | مستمر (WAL) | 7 أيام | S3 |
| **Schema only** | أسبوعي | 90 يوم | Git (مشفّر) |

### 3.2. إنشاء نسخة احتياطية يدوية

```bash
# عبر API المنصة (يتطلب super_admin)
curl -X POST https://your-domain.com/super-admin/backup/create \
  -H "Content-Type: application/json" \
  -d '{"type": "full"}' \
  -u super_admin:password

# أو مباشرة عبر pg_dump
pg_dump -h localhost -U med_app -d medical_centre -Fc -Z 9 \
  -f "backup_$(date +%Y%m%d_%H%M).dump"
```

### 3.3. استعادة (Point-in-Time Recovery)

```bash
# 1. إيقاف التطبيق
docker compose stop app celery-worker celery-beat

# 2. استعادة من نسخة كاملة
pg_restore -h localhost -U med_app -d medical_centre \
  -c --if-exists backup_20261025_0100.dump

# 3. تطبيق WALs للوصول للنقطة الزمنية المطلوبة (إذا متاح WAL-G)
# wal-g backup-fetch LATEST /tmp/wal && pg_ctl start -o "recovery_target_time='2026-10-25 14:30:00'"

# 4. تشغيل التهجيرات (إذا تغير المخطط)
flask db upgrade

# 5. تشغيل التطبيق
docker compose up -d app celery-worker celery-beat

# 6. التحقق
curl -f https://your-domain.com/__health
python scripts/ci/audit_rls_coverage.py
```

---

## 4. استكشاف الأخطاء الشائعة (Troubleshooting)

### 4.1. مشاكل قاعدة البيانات

| العرض | السبب المحتمل | الحل |
|-------|--------------|-------|
| `InsufficientPrivilege: row-level security policy` | كتابة في جدول RLS بدون `app.tenant_id` | استخدم `platform_tenant_scope()` للبذر/المهام، أو تحقق middleware المستأجر |
| `ModuleNotEnabledError` | دور يحاول الوصول لوحدة مطفأة | فعّل الوحدة للمستأجر عبر `/owner/api/tenants/<id>/modules/<module>/activate` |
| `DuplicateTable` أثناء `flask db upgrade` | قاعدة بيانات غير نظيفة | `db.drop_all()` مع CASCADE ثم `flask db upgrade` |
| `psycopg2.errors.ForeignKeyViolation` | حذف مرجع مطلوب | تحقق من القيود، استخدم `ON DELETE SET NULL` أو احذف التابع أولاً |
| بطء شديد في الاستعلامات | فهرس مفقود / إحصائيات قديمة | `ANALYZE`، تحقق `EXPLAIN ANALYZE`، أضف فهرس مركب |

### 4.2. مشاكل المستأجرين (Tenant Issues)

| العرض | السبب | الحل |
|-------|-------|-------|
| تسجيل دخول يفشل "Tenant not found" | `TENANT_DEFAULT_SLUG` خاطئ أو المستأجر معلق | تحقق `TENANT_DEFAULT_SLUG` في `.env`، حالة المستأجر في `tenants` |
| "Package restricted" بعد الدخول | دور المستخدم يتطلب وحدة غير مفعلة في الباقة | فعّل الوحدة المطلوبة أو غيّر باقة المستأجر |
| بيانات مريض لا تظهر | فلتر ORM يطبق `tenant_id` خاطئ | تحقق `g.tenant_id` في middleware، أو استخدم `bind_g_tenant(tenant)` |

### 4.3. مشاكل Celery / المهام المجدولة

| العرض | السبب | الحل |
|-------|-------|-------|
| مهام عالقة في `PENDING` | Worker معطل / Redis غير متاح | أعد تشغيل `celery-worker`، تحقق `redis-cli ping` |
| مهام تفشل بـ `OperationalError` | اتصال DB منقطع | تحقق pool connections، أعد تشغيل worker |
| طابور `celery` يطول | مهام بطيئة / worker غير كافٍ | أضف workers، أو حسّن المهمة (`acks_late`, `prefetch_multiplier`) |

---

## 4.4. مشاكل RLS / العزل

```bash
# تشخيص: هل السياسات مفعلة؟
psql -c "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind='r' AND relrowsecurity ORDER BY relname;"

# تشخيص: هل سياق المستأجر مضبوط؟
psql -c "SHOW app.tenant_id;"

# اختبار يدوي للعزل
psql -c "
SET LOCAL app.tenant_id = '1';
SELECT count(*) FROM patients;  -- يجب أن يرجع مرضى المستأجر 1 فقط
SET LOCAL app.tenant_id = '2';
SELECT count(*) FROM patients;  -- يجب أن يرجع مرضى المستأجر 2 فقط
"
```

---

## 5. الاستجابة للحوادث (Incident Response)

### 5.1. مستويات الخطورة

| المستوى | التعريف | وقت الاستجابة | التصعيد |
|--------|----------|---------------|---------|
| **P0 (Critical)** | الخدمة متوقفة بالكامل، تسرب بيانات، RLS معطل | 15 دقيقة | On-call + Tech Lead + CTO |
| **P1 (High)** | وحدة رئيسية معطلة، مستأجر رئيسي متأثر | 1 ساعة | On-call + Team Lead |
| **P2 (Medium)** | ميزة ثانوية معطلة، أداء متدني | 4 ساعات | Team Lead |
| **P3 (Low)** | خطأ تجميلي، طلب تحسين | الأسبوع القادم | Backlog |

### 5.2. إجراءات P0 (قائمة تحقق)

1. **تأكيد الحادث** — تحقق `/health`، `/__health`، سجلات التطبيق
2. **عزل** — إن كان تسرب بيانات: أوقف الكتابة (`ALTER DATABASE ... SET default_transaction_read_only = on`)
3. **تواصل** — قناة `#incidents`، أبلغ أصحاب المصلحة
3. **تشخيص** — سجلات `app.logger.exception`، `pg_stat_activity`، `celery inspect`
4. **إصلاح** — تطبيق hotfix / rollback / استعادة نسخة احتياطية
5. **تحقق** — `/__health`، `audit_rls_coverage.py`، اختبارات الدخان
6. **توثيق** — سجل الحادث في `docs/INCIDENT_LOG_*.md` مع RCA

### 5.3. Runbooks سريعة

| السيناريو | الإجراءات الفورية |
|-----------|------------------|
| **RLS معطل على جدول** | `ALTER TABLE x ENABLE ROW LEVEL SECURITY; ALTER TABLE x FORCE ROW LEVEL SECURITY;` + تحقق السياسات |
| **تسرب بيانات بين مستأجرين** | 1. أوقف التطبيق 2. تحقق `audit_trails` 3. أصلح السياسة المفقودة 4. أعد التشغيل |
| **قاعدة بيانات ممتلئة (disk full)** | 1. احذف سجلات قديمة `DELETE FROM audit_trails WHERE created_at < now() - interval '2 years'` 2. `VACUUM FULL` 3. أضف قرص |
| **Stripe webhook يفشل** | تحقق `STRIPE_WEBHOOK_SECRET`، سجلات `/api/billing/stripe/webhook`، أعد إرسال من Stripe Dashboard |

---

## 6. الترقية والنشر (Deployment & Upgrades)

### 6.1. نشر إصدار جديد (Zero-downtime إن أمكن)

```bash
# 1. سحب الكود الجديد
git pull origin main

# 2. بناء صورة Docker جديدة
docker compose -f docker-compose.yml -f docker-compose.prod.yml build

# 3. تشغيل التهجيرات (قبل إعادة تشغيل التطبيق!)
docker compose run --rm app flask db upgrade

# 4. إعادة تشغيل تدريجي (rolling restart)
docker compose up -d --no-deps app
# انتظر health check يمر
docker compose up -d --no-deps celery-worker celery-beat

# 5. التحقق
curl -f https://your-domain.com/__health
python scripts/ci/verify_migrations.py
```

### 6.2. Rollback سريع

```bash
# العودة للالتزام السابق
git checkout HEAD~1
docker compose -f docker-compose.yml -f docker-compose.prod.yml build
docker compose run --rm app flask db downgrade  # إذا غير المخطط
docker compose up -d --no-deps app celery-worker celery-beat
```

---

## 7. إدارة الأسرار (Secrets Management)

| السر | التدوير | التخزين |
|-------|---------|---------|
| `SECRET_KEY` | سنوياً | Vault / AWS Secrets Manager |
| `FIELD_ENCRYPTION_KEY` | **لا تدوير** (يفقد القدرة على فك التشفير) | Vault، نسخة احتياطية آمنة |
| `STRIPE_SECRET_KEY` | حسب سياسة Stripe | Stripe Dashboard + Vault |
| `DATABASE_URL` (كلمة مرور) | كل 90 يوم | Vault، تدوير تلقائي عبر RDS/IAM |
| `REDIS_URL` | كل 90 يوم | Vault |
| `JWT_PRIVATE_KEY` | سنوياً | Vault |

**ملاحظة هامة:** `FIELD_ENCRYPTION_KEY` **لا يُدوّر أبداً** — تدويره يجعل كل بيانات PHI المشفرة غير قابلة للقراءة. احتفظ بنسخة احتياطية آمنة ومتعددة المواقع.

---

## 8. سجلات التدقيق والامتثال (Audit & Compliance)

### 8.1. الجداول المحمية (Immutable)

| الجدول | الوصف | سياسة الحذف |
|--------|---------|-------------|
| `audit_trails` | كل العمليات (CRUD) | ممنوع الحذف (`NO DELETE` policy) |
| `phi_audit_logs` | وصول بيانات PHI | ممنوع الحذف |
| `audit_logs` | أحداث النظام العامة | ممنوع الحذف |
| `backup_logs` | سجلات النسخ الاحتياطي | مسموح بعد 7 سنوات |

### 8.2. تقارير الامتثال الشهرية

```bash
# 1. عدد عمليات الوصول لـ PHI
psql -c "SELECT count(*) FROM phi_audit_logs WHERE created_at > now() - interval '1 month';"

# 2. محاولات دخول فاشلة
psql -c "SELECT count(*) FROM login_attempts WHERE success = false AND created_at > now() - interval '1 month';"

# 3. تغييرات صلاحيات
psql -c "SELECT * FROM audit_trails WHERE table_name IN ('roles','permissions','role_permissions') AND created_at > now() - interval '1 month';"
```

---

## 9. تحسين الأداء (Performance Tuning)

### 9.1. فهارس مقترحة (من `pg_stat_statements`)

```sql
-- فهارس مركبة للاستعلامات الشائعة
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_visits_tenant_status_date 
  ON visits (tenant_id, status, created_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_patients_tenant_search 
  ON patients (tenant_id, national_id_hash) INCLUDE (first_name, last_name);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_lab_requests_tenant_status 
  ON lab_requests (tenant_id, status, created_at DESC);
```

### 9.2. إعدادات PostgreSQL مقترحة (لإنتاج 8GB RAM)

```postgresql
# postgresql.conf
shared_buffers = 2GB
effective_cache_size = 6GB
work_mem = 64MB
maintenance_work_mem = 512MB
max_connections = 200
random_page_cost = 1.1          # لـ SSD
effective_io_concurrency = 200  # لـ SSD/NVMe
wal_buffers = 64MB
checkpoint_completion_target = 0.9
max_wal_size = 4GB
min_wal_size = 1GB
```

---

## 10. مراجع سريعة (Quick Reference)

| العملية | الأمر |
|----------|-------|
| **فحص الصحة الكامل** | `curl -f https://domain.com/__health && python scripts/ci/audit_rls_coverage.py` |
| **إعادة تشغيل العمال** | `docker compose restart celery-worker celery-beat` |
| **مسح كاش Redis** | `redis-cli FLUSHDB` (حذر: يسقط الجلسات) |
| **إعادة تعيين كلمة مرور super_admin** | `flask create-super-admin --email admin@domain.com --password "NewPass123!"` |
| **إضافة مستأجر يدوياً** | `flask tenant-create --slug newclinic --name "New Clinic" --package hospital` |
| **تصدير OpenAPI** | `flask openapi-export > openapi.json` |
| **تشغيل التهجيرات يدوياً** | `flask db upgrade` |
| **التحقق من المخطط** | `python scripts/ci/verify_migrations.py` |

---

## 11. جهات الاتصال (Contacts)

| الدور | الاسم | القناة |
|--------|------|---------|
| On-call Engineer | — | `#oncall` / PagerDuty |
| Tech Lead | — | Slack DM |
| DBA | — | `#database` |
| Security Officer | — | `#security` |
| Product Owner | — | `#product` |

---

## 12. سجل التغييرات (Changelog)

| التاريخ | الإصدار | التغيير |
|--------|--------|---------|
| 2026-10-25 | 3.3 | إنشاء هذا الدليل — متوافقة مع commit `e69c81c0` |