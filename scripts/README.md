# Scripts — فصل التشغيل عن CI عن التطوير

| المجلد | الغرض | Docker / إنتاج |
|--------|--------|----------------|
| [`ops/`](ops/README.md) | bootstrap المنصة بعد `flask db upgrade` | ✅ يُشغَّل |
| [`dev/`](dev/README.md) | بيانات تجريبية، تدقيق يدوي، codemods | ❌ تطوير محلي |

## إنتاج (`scripts/ops/`)

```bash
python scripts/ops/bootstrap_platform.py
```

## تطوير (`scripts/dev/`)

سكربتات بذور وتدقيق — لا تُضمَّن في صورة Docker.
