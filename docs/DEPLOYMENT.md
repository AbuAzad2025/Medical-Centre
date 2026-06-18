# دليل النشر الإنتاجي — Azad Medical Platform v3.0

## 1. المتطلبات
- Docker + Docker Compose
- PostgreSQL 15+
- Redis 7+ (للجلسات والكاش)
- Python 3.11+

## 2. متغيرات البيئة

```bash
# .env
SECRET_KEY=your-256-bit-secret-key
DATABASE_URL=postgresql://user:pass@db:5432/medical
REDIS_URL=redis://redis:6379/0
FLASK_ENV=production
ADMIN_EMAIL=admin@azad.com
ADMIN_PASSWORD=change-me
WHATSAPP_API_KEY=your-meta-api-key
WHATSAPP_PHONE_NUMBER_ID=your-phone-number-id
```

## 3. التهجيرات

```bash
# أول تشغيل
flask db upgrade

# أو عبر Docker
docker-compose exec app flask db upgrade
```

## 4. تهيئة المنصة

```bash
python scripts/setup_platform.py
```

يقوم بـ:
- تشغيل التهجيرات
- تعبئة الوحدات (Module Definitions)
- إنشاء Tenant افتراضي
- إنشاء مستخدم إداري

## 5. إنشاء Tenant جديد

```bash
python scripts/setup_tenant.py \
  --slug clinic1 \
  --name "عيادة النور" \
  --email admin@clinic1.com \
  --plan monthly \
  --modules reception,doctor,lab,pharmacy
```

## 6. الفحص الصحي

```bash
python scripts/health_check.py
```

## 7. الاختبارات

```bash
python -m pytest tests/ -v --cov=app --cov-report=html
```

## 8. الأمان
- جميع الأسرار في متغيرات البيئة
- CSP headers مفعلة
- CSRF حماية على جميع النماذج
- Rate limiting على API
- Audit log على كل العمليات الحساسة

## 9. الوحدات الإلزامية
- **الاستقبال**: إلزامية لأي tenant يفعل أكثر من وحدة سريرية واحدة
- يمكن تفعيل/تعطيل الوحدات حسب الاشتراك

## 10. الدعم
للاستفسارات: support@azad.com
