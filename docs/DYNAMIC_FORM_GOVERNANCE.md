# Dynamic Specialty Forms — Governance Contract (UX1-005A)

## Scope
This contract governs the design and operation of versioned, tenant-scoped specialty forms in the Medical System.

## Principles

1. **Schema ownership**
   - Each form schema belongs to exactly one tenant.
   - Platform-owner supplied templates are read-only; tenants receive a private copy on first use.

2. **Version immutability**
   - A published form version is immutable.
   - Any change creates a new version; previous versions remain readable for existing submissions.

3. **Field type safety**
   - Only whitelisted field types are allowed: `text`, `number`, `date`, `select`, `checkbox`, `textarea`.
   - No arbitrary code, HTML, or script execution is permitted in form definitions or submissions.

4. **Audit retention**
   - Every form submission is stored with: form version, submitted at, submitted by, patient/visit reference, and raw answers.
   - Submissions are append-only and cannot be edited after creation.

5. **Permissioning**
   - Create/edit/publish forms: `manager`, `admin`, `super_admin`.
   - Fill forms: clinical roles authorized for the relevant specialty/department.
   - View submissions: same as fill, plus the patient (via portal) for their own records.

6. **Migration policy**
   - Schema model changes are delivered through normal Alembic migrations.
   - Tenant form data is never mutated by migrations; only the platform metadata schema changes.

7. **Validation boundaries**
   - Server-side validation is the source of truth.
   - Client-side validation is allowed for UX only and must be revalidated on the server.
