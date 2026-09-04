# سكربتات التشغيل — Ops Scripts

> مرجع سكربتات `scripts/ops/`. آخر تحقق من الكود: **5 أغسطس 2026**.

---

## أساسي للتشغيل

| السكربت | الغرض | متى؟ |
|---------|-------|------|
| `bootstrap_platform.py` | ينشئ `module_definitions` · `product_bundles` (23) · `packages`/`package_versions` | بعد `flask db upgrade` — إلزامي |
| `audit_orphaned_tenant_rows.py` | يكشف صفوف `tenant_id = 0` أو صفوف يتيمة خارج نطاق مستأجر | CI + بعد الهجرات |
| `pre_pilot_verification.py` | تحقق ما قبل التشغيل التجريبي (86 فحصاً) | قبل go-live |

---

## إصلاحات لمرة واحدة (مستهلكة غالباً)

سكربتات `fix_*` نفّذت إصلاحات تاريخية مرة واحدة (استيرادات db، كلمات مرور ضعيفة، عبارات SQLAlchemy 1.x، bare excepts، استيرادات مستقبلية). لا تُشغَّل إلا عند الحاجة لتطبيقها على نسخة قديمة:

| السكربت | المهمة |
|---------|--------|
| `fix_db_imports_unified.py` / `fix_db_imports_smart.py` / `fix_missing_db_import*.py` / `remove_duplicate_db_imports.py` | توحيد/إصلاح استيرادات `db` |
| `fix_bare_excepts.py` / `audit_bare_except.py` | إصلاح/فحص `except:` الخام |
| `fix_sa2_queries.py` / `audit_sqlalchemy_1x_queries.py` | ترقية استعلامات SQLAlchemy 1.x → 2.x |
| `fix_future_imports.py` | إضافة `from __future__ import annotations` |
| `migrate_sqlalchemy_2x.py` | هجرة واسعة إلى SQLAlchemy 2.x |

---

## التنبيهات

- لا تشغّل سكربتات الإصلاح على قاعدة بيانات إنتاج حيّة دون نسخة احتياطية.
- `bootstrap_platform.py` آمن للتكرار (idempotent) — يشغَّل في CI وحاوية `app`.
- مرجع فحوصات CI: `scripts/ci/` (verify_migrations، audit_rls_coverage، إلخ).
