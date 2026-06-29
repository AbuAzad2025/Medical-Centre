# تشغيل الإنتاج — مسار واحد

```bash
cp .env.example .env   # عدّل SECRET_KEY وكلمات المرور
docker compose up -d --build
```

ما يحدث تلقائياً عند بدء `app`:

1. `flask db upgrade` — تهجيرات PostgreSQL
2. `python scripts/ops/bootstrap_platform.py` — كتالوج الباقات + SaaS packages + module definitions
3. `gunicorn` — التطبيق

**التحقق:**

```bash
curl -f http://localhost:8080/health
curl -f http://localhost:8080/__health
```

**يدوياً (بدون Docker):**

```bash
flask db upgrade
python scripts/ops/bootstrap_platform.py
gunicorn -c gunicorn.conf.py wsgi:app
```

أو: `flask platform-bootstrap`

**تعطيل البذور عند التشغيل:** `SKIP_PLATFORM_BOOTSTRAP=true`
