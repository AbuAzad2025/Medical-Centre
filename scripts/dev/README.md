# سكربتات التطوير — ليست جزءاً من حزمة التشغيل

لا تُشغَّل في Docker أو الإنتاج. مُستبعدة في `.dockerignore`.

| الملف | الغرض |
|-------|--------|
| `audit_nav_links.py` | Gate 6b — صفر broken nav endpoints |
| `audit_nav_coverage.py` | تغطية مسارات القائمة الجانبية |
| `bs4_audit.py` | تدقيق قوالب Bootstrap 5 |
| `lint_debt.py` | فحص flake8 موسّع (دين تقني) |
| `create_tenants.py` | بيانات تجريبية — tenants |
| `create_test_users.py` | مستخدمون تجريبيون |
| `create_bundle_table.py` | قديم — استُبدل بـ Alembic |
| `apply_migrations.py` | بديل يدوي — استخدم `flask db upgrade` |

**التشغيل الإنتاجي:** `docker compose up` أو `flask db upgrade` ثم `python scripts/ops/bootstrap_platform.py`.
