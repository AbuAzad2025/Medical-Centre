# سكربتات التطوير — ليست جزءاً من حزمة التشغيل

لا تُشغَّل في Docker أو الإنتاج. مُستبعدة في `.dockerignore`.

| الملف | الغرض |
|-------|--------|
| `audit_nav_links.py` | Gate 6b — صفر broken nav endpoints |
| `audit_nav_coverage.py` | تغطية مسارات القائمة الجانبية |
| `bs4_audit.py` | تدقيق قوالب Bootstrap 5 |
| `lint_debt.py` | فحص flake8 موسّع (دين تقني) |
| `create_tenants.py` | بيانات تجريبية — 10 tenants |
| `create_test_users.py` | مستخدمون تجريبيون لكل tenant |
| `create_bundle_table.py` | **مهمل** — يخرج بخطأ (استخدم Alembic) |
| `apply_migrations.py` | **مهمل** — يوجّه إلى `flask db upgrade` |
| `convert_backref.py` | codemod لمرة واحدة — backref → back_populates |
| `_bootstrap.py` | مساعد مسار — لا يُشغَّل مباشرة |

**التشغيل الإنتاجي:** `docker compose up` أو `flask db upgrade` ثم `python scripts/ops/bootstrap_platform.py`.
