# خطة التعافي من الكوارث واستعادة قواعد البيانات (DR / PITR)

> Disaster Recovery & Point-In-Time Recovery Plan — Medical System Platform
> Last updated: 2026-08-21

---

## 1. أهداف التعافي (Recovery Objectives)

| الهدف | التعريف | القيمة المستهدفة | طريقة التحقق |
|-------|---------|------------------|---------------|
| **RPO** | Recovery Point Objective — أقصى فقدان بيانات مقبول | ≤ 15 دقيقة | WAL archiving مع `archive_timeout = 300` |
| **RTO** | Recovery Time Objective — أقصى زمن توقف مقبول | ≤ 60 دقيقة | اختبار استرجاع مؤتمت (هذا المستند §5) |

---

## 2. استراتيجية النسخ الاحتياطي (Backup Strategy)

النظام يستخدم ثلاث طبقات متكاملة:

### الطبقة 1 — نسخ منطقية يومية (pg_dump)
- **الأداة**: `services/pg_backup_service.py` → `pg_dump` مضغوط gzip
- **التكرار**: يومياً الساعة 02:00 UTC عبر Celery Beat (`tasks/`)
- **الاحتفاظ**: 30 يوماً محلياً + رفع تلقائي إلى S3 (`BACKUP_S3_BUCKET`)
- **التحقق**: حجم الملف > 1KB وفحص `pg_restore --list` بعد كل نسخة

### الطبقة 2 — أرشفة WAL للنسخ اللحظية (PITR)
مطلوب على خادم PostgreSQL الإنتاجي في `postgresql.conf`:

```conf
# ─── PITR: WAL Archiving ───
wal_level = replica
archive_mode = on
archive_timeout = 300              # قطعة WAL كل 5 دقائق → RPO ≤ 15د
archive_command = 'test ! -f /var/backups/pg_wal_archive/%f && cp %p /var/backups/pg_wal_archive/%f'

# ─── PITR: Base Backups عبر pg_basebackup ───
# تشغيل مجدول (أسبوعياً كحد أدنى، ويُفضَّل يومياً):
# pg_basebackup -h localhost -U backup_user -D /var/backups/pg_base/%Y%m%d \
#   -Fp -Xs -P -R --wal-method=stream
```

> **ملاحظة Docker**: عند التشغيل عبر `docker-compose.prod.yml`، تأكد من تركيب
> volume دائم لمجلد الأرشيف `/var/backups/pg_wal_archive` ومجلد base backups.

### الطبقة 3 — لقطات S3 مشفرة
- نسخ pg_dump ترفع إلى `BACKUP_S3_BUCKET` مع تشفير SSE-KMS اختيارياً
  (`BACKUP_S3_KMS_KEY_ID`) — انظر `services/backup_automation_service.py`
- تفعيل **S3 Object Lock / Versioning** على bucket النسخ للحماية من الحذف الخبيث

---

## 3. سيناريوهات التعافي (Recovery Scenarios)

### السيناريو أ: حذف خاطئ لجدول/بيانات قبل N دقيقة (PITR كامل)

```bash
# 1. أوقف التطبيق فوراً (منع كتابة إضافية)
docker compose -f docker-compose.prod.yml stop app worker beat

# 2. أنشئ ملف إشارة الاسترجاع للوقت المستهدف
TARGET_TS="2026-08-21 14:30:00+00"
cat > /var/lib/postgresql/data/recovery.signal <<EOF
EOF   # ملف فارغ يكفي؛ الوقت يحدد في recovery settings

# 3. أعد البنية الأساسية من أحدث base backup
rm -rf /var/lib/postgresql/data/*
pg_basebackup -h <primary> -D /var/lib/postgresql/data -Xs -R

# 4. اضبط نقطة الاسترجاع في postgresql.auto.conf
cat >> /var/lib/postgresql/data/postgresql.auto.conf <<EOF
restore_command = 'cp /var/backups/pg_wal_archive/%f %p'
recovery_target_time = '$TARGET_TS'
recovery_target_action = 'promote'
EOF

# 5. شغّل PostgreSQL — سيعيد تشغيل WAL حتى اللحظة المحددة ثم يرقى تلقائياً
docker compose -f docker-compose.prod.yml start db

# 6. تحقق من سلامة البيانات ثم شغّل التطبيق
python scripts/verify_restore_integrity.py
docker compose -f docker-compose.prod.yml start app worker beat
```

### السيناريو ب: فساد كامل لقاعدة البيانات (استرجاع من آخر نسخة منطقية)

```bash
# 1. أنشئ قاعدة فارغة جديدة
createdb -h localhost -U postgres medical_system_restored

# 2. افك الضغط واسترجع
gunzip -c backups/2026/08/latest_backup.sql.gz | \
  psql -h localhost -U postgres -d medical_system_restored

# 3. فحص السلامة ثم التبديل
python scripts/verify_restore_integrity.py --database medical_system_restored
```

### السيناريو ج: خطأ منطقي فقط (بدون توقف الخدمة)
استرجع إلى قاعدة مؤقتة بالطريقة (أ) أو (ب)، ثم انسخ الجداول المتأثرة فقط:
```sql
-- على قاعدة الاسترجاع:
pg_dump -t visits -t patients medical_system_restored > salvage.sql
-- على قاعدة الإنتاج:
psql medical_system < salvage.sql
```

---

## 4. جدول صيانة النسخ (Retention Schedule)

| نوع النسخة | التكرار | مدة الاحتفاظ المحلي | S3 |
|-----------|---------|---------------------|-----|
| pg_dump يومية | يومياً 02:00 | 30 يوم | 90 يوم (Object Lock) |
| Base backup (pg_basebackup) | أسبوعياً الجمعة | 4 نسخ | — |
| WAL archive | مستمر (≤5د) | 14 يوم | — |
| نسخة شهرية أرشيفية | أول كل شهر | — | سنة كاملة |

---

## 5. اختبار الاسترجاع المؤتمت (Automated Restore Testing)

> ⚠️ النسخ الاحتياطي غير المُختبَر ليس نسخة احتياطية.
> الاختبار يعمل شهرياً عبر CI وينبغي تشغيله يدوياً بعد أي تغيير مخطط كبير.

```bash
# اختبار كامل: dump → restore → integrity checks
python scripts/test_pitr_restore.py

# مع تحديد ملف نسخة موجودة بدل إنشاء واحدة جديدة
python scripts/test_pitr_restore.py --backup-file backups/path/to/file.sql.gz
```

ما الذي يفحصه الاختبار:
1. ✅ نجاح `pg_dump` (حجم > عتبة دنيا)
2. ✅ نجاح الاسترجاع إلى قاعدة مؤقتة `_restore_test`
3. ✅ وجود الجداول الحرجة: `users`, `patients`, `visits`, `audit_trails`
4. ✅ تطابق عدد صفوف الجداول الحرجة بين الأصل والمسترجعة
5. ✅ تنظيف قاعدة الاختبار المؤقتة

### جدولة CI (GitHub Actions)
```yaml
# .github/workflows/dr-drill.yml
name: Monthly DR Drill
on:
  schedule:
    - cron: '0 3 1 * *'   # أول كل شهر 03:00 UTC
jobs:
  pitr-restore-test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env: {POSTGRES_PASSWORD: testpass}
        ports: ['5432:5432']
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: '3.11'}
      - run: pip install -r requirements_no_psycopg2.txt
      - name: Run restore drill
        env:
          DATABASE_URL: postgresql://postgres:testpass@localhost:5432/medical_system
          SECRET_KEY: ci-only-key
          APP_ENV: testing
        run: python scripts/test_pitr_restore.py
```

---

## 6. متغيرات البيئة ذات الصلة

```env
# أساسي
DATABASE_URL=postgresql://app_user:***@db-host:5432/medical_system

# نسخ احتياطي سحابي
BACKUP_S3_BUCKET=medical-backups
BACKUP_S3_PREFIX=medical-system/backups
BACKUP_S3_ENDPOINT_URL=            # MinIO إن وجد
BACKUP_S3_REGION=us-east-1
BACKUP_S3_KMS_KEY_ID=

# دور PostgreSQL المخصص للنسخ (صلاحيات دنيا: pg_backup role)
PG_BACKUP_USER=backup_user
```

---

## 7. قائمة فحص ما الكوارث (Pre-Disaster Checklist)

- [ ] `archive_mode = on` مفعّل على الإنتاج وتُراجع سجلات الأرشفة أسبوعياً
- [ ] `pg_basebackup` يعمل بنجاح (اختبار يدوي شهري)
- [ ] `scripts/test_pitr_restore.py` أخضر في CI خلال آخر 30 يوماً
- [ ] bucket النسخ عليه Versioning + Object Lock
- [ ] بيانات اعتماد S3/MinIO مخزنة في secret manager وليست في .env بالإنتاج
- [ ] RPO/RTO موثقة ومعتمدة من الإدارة (هذا المستند §1)
- [ ] تجربة تعافٍ كاملة (Full DR drill) مرتين سنوياً على بيئة معزولة
