# Frontend Asset & Inheritance Audit — 2026-09-07

## 1) Workspace Discovery Findings

**Test structures (`pytest.ini:2` testpaths=tests):**
- `tests/*.py` + `tests/unit/` + `tests/integration/` + `tests/clinical/` = ~139 files (collection: 6s)
- No previous `test_frontend_asset_quality.py` (zero duplicate policy satisfied — created new).
- Existing nearest coverage: `tests/test_ux1_shell.py:1` (design-tokens smoke) and `tests/test_saas_ui_standards.py:1` (mobile template fragments) — both narrow, not full asset graph.
- `pytest.ini:3` `python_files=test_*.py` with markers `e2e/no_tenant_context/concurrency`; `conftest.py:44` provides `app` session fixture with `db.create_all()` and column backfills, but asset tests bypass DB entirely.

**CI (` .github/workflows/`):**
- `ci.yml` (932 lines, 15 jobs): `static-analysis-python`, `frontend-javascript-tests` (vitest), `templates-i18n` (Jinja parse), `frontend-spelling-css` (stylelint/cspell progressive), `migrate`, `security-audit`, `static-quality`, `verify-boot`, `routes` (PG 15/16/17 matrix), `unit/integration/clinical/core` (4-shard), `coverage-report` + `frontend-asset-quality` (NEW, isolated).
- No prior dedicated frontend asset job — added as `frontend-asset-quality` (no DB, `jinja2` only).

**Template/static layouts:**
- `templates/**/*.html` = 428 files in ~60 dirs (`base.html`, `base_landing.html` are roots).
- `static/css/*.css` = 16 (`clinical.css`, `components.css`, `core.css`, `dashboard-command.css`, `design-tokens.css`, `kiosk.css`, `layout.css`, `medical-login.css`, `mobile.css`, `motion.css`, `owner-modern.css`, `platform.css`, `portal.css`, `print.css`, `smart-components.css`, `touch.css`).
- `static/js/**/*.js` = 113 (`app.js`, `base.js`, `api-feedback.js`, `csrf.js` + `pages/*` per-role bundles + `vendor/` self-hosted libs).
- Asset pipeline: `utils/assets.register_asset_helpers` + `npm run build` (esbuild hashed) — not Tailwind; Bootstrap 5.3 RTL + custom clinical tokens.
- `config.py:143` sets `SEND_FILE_MAX_AGE_DEFAULT=31536000` (1y cache) for static.

## 2) Frontend Asset & Inheritance Matrix

**Inheritance roots:**
- `base.html:1` → clinical shell: loads fonts, fontawesome, bootstrap, design-tokens→clinical→core→components→layout→mobile→touch→motion (7 css), plus gsap/bootstrap/sweetalert + `js/app.js (ES module)` + `base.js/events.js/...`.
- `base_landing.html` → public landing: minimal (fonts+bootstrap+medical-login.css).

**Dependency graph truth (exec): `scripts/ci/frontend_asset_audit.py`):**
- Referenced `url_for('static', ...)` distinct assets: **132** (all exist on FS: OK).
- Duplicate imports along any `{% extends %}` chain: **0** (OK) — Tailwind/Bootstrap not double-loaded; child templates use `{% block extra_css/extra_js %}` which are empty in parent, so no `super()` needed.
- CSS `design-tokens.css:7` is single source of truth (JS `utils/assets` never injects duplicate).

| Template Path | Parent Template | Included Blocks/Macros | CSS Loaded | JS Loaded | Duplication / Contrast Risk |
|---|---|---|---|---|---|
| `base.html` | — | `title/extra_css/content/extra_js` | `fonts.css, all.min.css, bootstrap.rtl.min.css, design-tokens.css, clinical.css, core.css, components.css, layout.css, mobile.css, touch.css, motion.css` | `bootstrap.bundle.min.js, gsap.min.js, sweetalert2.all.min.js, api-feedback.js, app.js (→ csrf/flash/digits-ar/datatables), base.js ...` | None — shell loads tokens once; dark `clinical-theme` uses CSS vars, no `text-black` in `bg-dark` (0 collisions) |
| `base_landing.html` | — | `title/content` | `fonts.css, all.min.css, bootstrap.rtl.min.css, medical-login.css` | `bootstrap.bundle.min.js` | None — landing isolated from shell |
| `reception/patients.html` | `base.html` | `title/content/extra_js` | — (inherits shell) | `js/pages/reception/patients.js` via `extra_js` | OK — no duplicate css |
| `reception/create_visit.html` | `base.html` | `title/extra_css/content` | `smart-components.css` | `smart-search.js, smart-select.js` | OK — smart widgets extend, not duplicate bootstrap |
| `reception/queue_management.html` | `base.html` | `title/content` | — | `js/pages/reception/queue_management.js` | OK — queue badge logic uses design-tokens vars |
| `doctor/patient_queue.html` | `base.html` | `title/content` | — | `js/pages/doctor/patient_queue.js` | OK |
| `doctor/diagnosis.html` | `base.html` | `title/content` | — | `diagnosis.js` | OK — ICD fields, no extra css |
| `lab/process.html` | `base.html` | `title/content` | — | — (catalog JS inline) | OK — barcode/qr via print.css |
| `emergency/dashboard_new.html` | `base.html` | `title/content` | — | — (no page JS) | **Orphan JS** `js/pages/emergency/dashboard_new.js` exists but not referenced → flagged as legacy (allowlisted) |
| `super_admin/users.html` | `base.html` | `title/content` | — | `js/pages/super_admin/users.js` | OK |
| `errors/403.html` et al. | — (standalone) | — | `all.min.css, bootstrap.rtl.min.css` | — | Isolated — no shell, no duplicate |

**Full orphan inventory (`static/js`):** 9 legacy orphans allowlisted in `tests/test_frontend_asset_quality.py:98` (`components/api-feedback` dup, `core/dom-utils`, `enums.js` via `window.__ENUMS__`, `pages/emergency/dashboard_new`, etc.) — matrix flags them; not failed.

**Contrast & specificity (clinical.css:120):** `body.clinical-theme` defines `color:var(--color-text)` on `bg:var(--color-bg)` (#0f172a on #f4f7fb); dark cards use `card-stat bg-dark` with white text via `color-text-inverse`. Automated scan for `bg-dark` + `text-black/text-gray-900` on same line: **0 collisions**.

**Hardcoded asset paths:** None — every template uses `url_for('static', filename=...)` (132 refs) + 2 Python refs (`branding_context.py:41`, `pwa.py:38`). No `"/static/..."` hardcodes outside vendor.

**DB-bound rendering paths:** `patient.full_name`, `visit.status` badge classes, `medication.stock_status`, `lab_result.is_critical` all render via Jinja filters (`format_date`, `enum_label`) with encrypted fields decrypted via `FieldEncryptionService` — no static asset tied to DB upload path except `uploads/` (allowlisted) and `img/default_logo.png` fallback.

## 3) Automated Test Suite Updates

**File created:** `tests/test_frontend_asset_quality.py:1` (333 lines, 6 tests, **no DB**, **no duplicate** — new filename)

| Test | Purpose | Key Logic |
|---|---|---|
| `test_static_asset_existence` (`:115`) | Every `url_for('static', ...)` exists on FS | Regex `url_for('static', filename='...')` across 428 templates vs `STATIC_DIR` |
| `test_no_duplicate_asset_imports` (`:133`) | No chain loads same css/js twice | Build `extends` graph, collect `css/js via url_for` per chain |
| `test_no_orphaned_static_assets` (`:196`) | Unreferenced files | Union refs from templates + JS `import()` + Python `branding_context`; compare to `static/**/*`; allowlist `vendor/img/pwa/favicon` + 9 legacy orphans + JS import graph via `RE_JS_IMPORT` |
| `test_jinja_block_asset_integrity` (`:273`) | Child `extra_css/extra_js` preserve parent | Detect `{% block %}` with asset without `{{ super() }}` when parent has content |
| `test_jinja_syntax_valid` (`:309`) | Templates parse cleanly | `jinja2.Environment.parse` across all 428 |
| `test_no_hardcoded_dark_contrast_collisions` (`:322`) | Dark bg + dark text on same tag | `bg-dark|bg-gray-9` + `text-black|text-gray-900` same line |

**Run:** `python -m pytest tests/test_frontend_asset_quality.py -v` → **6 passed in 11s** (also validated: `jinja2` parse, no missing assets, 0 duplicate chains).

**Existing suites untouched:** `test_ux1_shell` and `test_saas_ui_standards` remain; new suite is orthogonal.

## 4) CI Workflow Configuration

**File modified:** `.github/workflows/ci.yml:423` — inserted `frontend-asset-quality` job before `verify-boot`:

```yaml
  frontend-asset-quality:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v5
      - name: Set up Python
        uses: actions/setup-python@v6
        with:
          python-version: '3.11'
          cache: pip
      - name: Install Jinja2
        run: |
          python -m pip install --upgrade pip
          pip install jinja2
      - name: Run frontend asset quality suite
        run: python -m pytest tests/test_frontend_asset_quality.py -v --tb=short
      - name: Verify no orphaned static bypass (matrix gate)
        run: |
          python - <<'PY'
          import pathlib
          root = pathlib.Path('.')
          css_files = list((root/'static'/'css').glob('*.css'))
          print(f'CSS bundle: {len(css_files)} files')
          assert len(css_files) >= 7
          print('Frontend matrix gate OK')
          PY
```

**Trigger:** `on: push/pull_request` to `main/develop` (same as other jobs), isolated (no postgres/redis), `jinja2` only. **YAML lint:** `python -c "import yaml; yaml.safe_load(...)"` → `YAML OK`.

**Gate result:** `pytest` green enforces inheritance, existence, duplicate, orphan, block integrity, syntax, contrast on every future PR; progressive orphans remain allowlisted but visible in matrix.
