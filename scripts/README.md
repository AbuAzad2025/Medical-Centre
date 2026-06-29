# Scripts — فصل التشغيل عن CI عن التطوير

| المجلد | الغرض | Docker / إنتاج |
|--------|--------|----------------|
| [`ops/`](ops/README.md) | bootstrap المنصة بعد `flask db upgrade` | ✅ يُشغَّل |
| [`ci/`](ci/) | تحقق CI: تهجيرات، RLS، تطابق ORM | ❌ GitHub Actions فقط |
| [`dev/`](dev/README.md) | بيانات تجريبية وتدقيق يدوي | ❌ تطوير محلي |

## CI (`scripts/ci/`)

```bash
python scripts/ci/verify_migrations.py      # upgrade على DB فارغ + head
python scripts/ci/audit_rls_coverage.py     # تدقيق RLS (enforce)
python scripts/ci/check_schema_parity.py    # ORM ↔ migrations
```

## إنتاج (`scripts/ops/`)

```bash
python scripts/ops/bootstrap_platform.py
```

## تطوير (`scripts/dev/`)

سكربتات بذور وتدقيق — لا تُضمَّن في صورة Docker.
