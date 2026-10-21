# Frontend coverage

Produced by the vitest v8 provider over `static/js`. Regenerate with
`npm run test:js:coverage` followed by
`python tools/reports/coverage_report.py`.

## The number that was previously reported was zero for the wrong reason

CI read `summary.covered` and `total` from `coverage-final.json`. The v8
provider writes neither; it writes per-file `s`, `f` and `b` maps. The
arithmetic therefore ran over two missing keys and produced `0/0`, which
looked like a measured result rather than a broken reader.

## A second reason the figure was near zero

The page scripts are loaded by `tests/frontend/test-utils.mjs`, which reads
the file and calls `eval` on it. `eval` runs outside the module pipeline,
so the provider never instrumented the code that executed. The tests were
real, 318 of them, but they were measuring nothing.

The tests still use that loader, because the scripts rely on top-level `var`
leaking onto `window`, which only happens for classic scripts. Converting the
loader to a dynamic `import` instruments the code and breaks that global leak,
which is why the migration was reverted rather than shipped.

**The page scripts are not instrumented, so this figure is not application
coverage.** It counts the module bodies the provider did see, which excludes
every script loaded through the eval loader. Treat it as the floor of what is
measured, not as the state of the frontend.

So the figure below is honest about a narrow measurement: it counts the module
bodies the provider saw. Treating it as statement coverage of the application
frontend would be wrong, and the header says so on purpose.

| measure | covered | total | percent |
|---|---|---|---|
| statements | 2,209 | 7,696 | 28.7% |
| branches | 953 | 5,546 | 17.2% |
| functions | 180 | 1,531 | 11.8% |

## By area

| area | covered | statements | percent |
|---|---|---|---|
| `static/js/api-feedback.js` | 0 | 32 | 0.0% |
| `static/js/app.js` | 0 | 33 | 0.0% |
| `static/js/components` | 0 | 92 | 0.0% |
| `static/js/csrf.js` | 0 | 14 | 0.0% |
| `static/js/datatables-init.js` | 0 | 6 | 0.0% |
| `static/js/document_ocr.js` | 0 | 31 | 0.0% |
| `static/js/form-stepper.js` | 0 | 34 | 0.0% |
| `static/js/login.js` | 0 | 44 | 0.0% |
| `static/js/pages/barcode` | 0 | 20 | 0.0% |
| `static/js/pages/biometric` | 0 | 24 | 0.0% |
| `static/js/pages/kiosk` | 0 | 46 | 0.0% |
| `static/js/pages/nurse` | 0 | 51 | 0.0% |
| `static/js/pages/owner` | 0 | 29 | 0.0% |
| `static/js/pages/partials` | 0 | 15 | 0.0% |
| `static/js/pages/portal` | 0 | 2 | 0.0% |
| `static/js/smart-select.js` | 0 | 14 | 0.0% |
| `static/js/touch-mode.js` | 0 | 6 | 0.0% |
| `static/js/theme-toggle.js` | 2 | 27 | 7.4% |
| `static/js/focus-trap.js` | 3 | 39 | 7.7% |
| `static/js/pages/booking` | 10 | 122 | 8.2% |
| `static/js/security.js` | 24 | 224 | 10.7% |
| `static/js/base.js` | 54 | 381 | 14.2% |
| `static/js/performance.js` | 46 | 316 | 14.6% |
| `static/js/pages/pharmacy` | 30 | 161 | 18.6% |
| `static/js/pages/super_admin` | 380 | 1,383 | 27.5% |
| `static/js/pwa-install.js` | 12 | 43 | 27.9% |
| `static/js/events.js` | 27 | 96 | 28.1% |
| `static/js/pages/reception` | 456 | 1,597 | 28.6% |
| `static/js/pages/doctor` | 265 | 806 | 32.9% |
| `static/js/pages/print` | 6 | 18 | 33.3% |
| `static/js/ux-enhance.js` | 27 | 80 | 33.8% |
| `static/js/form-validation.js` | 31 | 85 | 36.5% |
| `static/js/global-errors.js` | 21 | 57 | 36.8% |
| `static/js/pages/emergency` | 77 | 204 | 37.7% |
| `static/js/pages/radiology` | 142 | 373 | 38.1% |
| `static/js/pages/manager` | 208 | 545 | 38.2% |
| `static/js/pages/accountant` | 30 | 75 | 40.0% |
| `static/js/pages/medication` | 17 | 39 | 43.6% |
| `static/js/ui-preferences.js` | 20 | 43 | 46.5% |
| `static/js/smart-search.js` | 38 | 79 | 48.1% |
| `static/js/pages/report_builder` | 58 | 115 | 50.4% |
| `static/js/motion.js` | 8 | 14 | 57.1% |
| `static/js/flash.js` | 49 | 79 | 62.0% |
| `static/js/dashboard-live.js` | 26 | 38 | 68.4% |
| `static/js/digits-ar.js` | 20 | 27 | 74.1% |
| `static/js/dashboard-customize.js` | 23 | 30 | 76.7% |
| `static/js/pages/lab` | 23 | 28 | 82.1% |
| `static/js/pages/quality_compliance` | 16 | 18 | 88.9% |
| `static/js/utils` | 38 | 39 | 97.4% |
| `static/js/core` | 19 | 19 | 100.0% |
| `static/js/enums.js` | 3 | 3 | 100.0% |

## Least covered scripts

| script | covered/total | percent |
|---|---|---|
| `D:/recovers/data/medical/static/js/pages/super_admin/system_config.js` | 0/139 | 0.0% |
| `D:/recovers/data/medical/static/js/pages/super_admin/queue_settings.js` | 0/92 | 0.0% |
| `D:/recovers/data/medical/static/js/pages/booking/create.js` | 0/83 | 0.0% |
| `D:/recovers/data/medical/static/js/components/pos-charge.js` | 0/62 | 0.0% |
| `D:/recovers/data/medical/static/js/pages/kiosk/check_in.js` | 0/46 | 0.0% |
| `D:/recovers/data/medical/static/js/login.js` | 0/44 | 0.0% |
| `D:/recovers/data/medical/static/js/pages/super_admin/system_maintenance.js` | 0/41 | 0.0% |
| `D:/recovers/data/medical/static/js/pages/super_admin/department_staff.js` | 0/37 | 0.0% |
| `D:/recovers/data/medical/static/js/form-stepper.js` | 0/34 | 0.0% |
| `D:/recovers/data/medical/static/js/app.js` | 0/33 | 0.0% |
| `D:/recovers/data/medical/static/js/api-feedback.js` | 0/32 | 0.0% |
| `D:/recovers/data/medical/static/js/document_ocr.js` | 0/31 | 0.0% |
| `D:/recovers/data/medical/static/js/components/api-feedback.js` | 0/30 | 0.0% |
| `D:/recovers/data/medical/static/js/pages/super_admin/service_detail.js` | 0/30 | 0.0% |
| `D:/recovers/data/medical/static/js/pages/accountant/dashboard_new.js` | 0/29 | 0.0% |
| `D:/recovers/data/medical/static/js/pages/nurse/dashboard_new.js` | 0/29 | 0.0% |
| `D:/recovers/data/medical/static/js/pages/owner/dashboard.js` | 0/29 | 0.0% |
| `D:/recovers/data/medical/static/js/pages/super_admin/branch_templates.js` | 0/28 | 0.0% |
| `D:/recovers/data/medical/static/js/pages/super_admin/department_detail.js` | 0/28 | 0.0% |
| `D:/recovers/data/medical/static/js/pages/biometric/status.js` | 0/24 | 0.0% |

