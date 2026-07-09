# GRIMOIRE.md — The Golden Rules

> Enforced since the July 2026 security audit.  
> Every new route, model, service, or template **must** conform.

---

## 1. Every query must be tenant-scoped

```python
# ✅ GOOD — filtered by tenant
Patient.query.filter(
    Patient.id == patient_id,
    Patient.tenant_id == g.tenant_id
).first_or_404()

# ❌ BAD — cross-tenant leak
db.session.get(Patient, patient_id)
```

- The `TenantMixin` + `before_compile` event + RLS handle this at the ORM/DB layer.
- **Never bypass** by using `db.session.get()`, `Model.query.get()`, or raw SQL that omits `tenant_id`.

---

## 2. Every `commit()` must be wrapped in try/except/rollback

```python
try:
    db.session.commit()
except Exception as e:
    db.session.rollback()
    current_app.logger.error(f"…: {e}")
    raise
```

- Applies to `routes/`, `services/`, `models/`, `tasks/`.
- ZERO bare `except Exception: pass` — every handler must log.

---

## 3. Every `get_json()` must use `silent=True`

```python
data = request.get_json(silent=True)
if data is None:
    return jsonify({"error": "Invalid JSON"}), 400
```

- Prevents internal `400 Bad Request` without a useful error body.

---

## 4. Never check `current_user.role` manually — use decorators

```python
# ✅ GOOD
@role_required('doctor', 'manager')       # for HTML routes
@role_required_json('doctor', 'manager')   # for JSON API routes

# ❌ BAD
if current_user.role not in ['doctor', 'manager']:
    abort(403)
```

- `@role_required` (html) → flash + redirect  
- `@role_required_json` (json) → `jsonify` + 403  
- Owner module uses `@owner_required` from `app/modules/owner/decorators.py`

---

## 5. Every POST/PUT/DELETE route must be protected

- If it mutates data, it needs authentication + authorisation:
  - `@login_required` + `@role_required(...)` or `@role_required_json(...)`
- Template forms need `{{ form.hidden_tag() }}` or `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`.

---

## 6. Service-layer guards raise `PermissionError` — don't return empty

```python
def create_request(data):
    if not _module_active('lab'):
        raise PermissionError("Lab module is not enabled")
```

- Never return `{}` or `None` — the caller must receive a clear error.

---

## 7. Logs are for debugging, not secrets

- Log user IDs, actions, errors — never passwords, tokens, PII payloads.
- Use `current_app.logger.warning/error/info` consistently.

---

## 8. Dynamic forms are governed

- Template-level gating: `{% if module_active('lab') %}`.
- Dynamic form definitions live in `docs/DYNAMIC_FORM_GOVERNANCE.md`.
- No inline raw HTML that bypasses CSRF.

---

## 9. Migration safety

- Every new column on a multi-tenant table must have a `NOT NULL` + default, or be nullable.
- Run `verify_migrations.py` before deploying.
- Run `verify_rls_enforcement.py` after any model change.

---

## 10. No stale code in the root

- `routes/` — grouped by module (`doctor/`, `lab/`, `manager/`, etc.)
- `services/` — one file per domain concern
- `scripts/` — organised as `dev/`, `ops/`, `ci/`, `bootstrap/`
- Root directory must not contain log files, temp files, old reports, or unorganised scripts.
