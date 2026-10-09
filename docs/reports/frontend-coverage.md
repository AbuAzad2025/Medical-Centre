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
| statements | 33 | 6,481 | 0.5% |
| branches | 20 | 4,736 | 0.4% |
| functions | 8 | 1,531 | 0.5% |

## By area

| area | covered | statements | percent |
|---|---|---|---|
| `static/js/api-feedback.js` | 0 | 32 | 0.0% |
| `static/js/app.js` | 0 | 33 | 0.0% |
| `static/js/base.js` | 0 | 354 | 0.0% |
| `static/js/components` | 0 | 92 | 0.0% |
| `static/js/csrf.js` | 0 | 14 | 0.0% |
| `static/js/dashboard-customize.js` | 0 | 30 | 0.0% |
| `static/js/dashboard-live.js` | 0 | 38 | 0.0% |
| `static/js/datatables-init.js` | 0 | 6 | 0.0% |
| `static/js/document_ocr.js` | 0 | 31 | 0.0% |
| `static/js/enums.js` | 0 | 3 | 0.0% |
| `static/js/events.js` | 0 | 96 | 0.0% |
| `static/js/flash.js` | 0 | 79 | 0.0% |
| `static/js/focus-trap.js` | 0 | 39 | 0.0% |
| `static/js/form-stepper.js` | 0 | 34 | 0.0% |
| `static/js/form-validation.js` | 0 | 85 | 0.0% |
| `static/js/global-errors.js` | 0 | 57 | 0.0% |
| `static/js/login.js` | 0 | 32 | 0.0% |
| `static/js/motion.js` | 0 | 14 | 0.0% |
| `static/js/pages/accountant` | 0 | 57 | 0.0% |
| `static/js/pages/barcode` | 0 | 14 | 0.0% |
| `static/js/pages/biometric` | 0 | 21 | 0.0% |
| `static/js/pages/booking` | 0 | 95 | 0.0% |
| `static/js/pages/doctor` | 0 | 629 | 0.0% |
| `static/js/pages/emergency` | 0 | 174 | 0.0% |
| `static/js/pages/kiosk` | 0 | 46 | 0.0% |
| `static/js/pages/lab` | 0 | 25 | 0.0% |
| `static/js/pages/manager` | 0 | 380 | 0.0% |
| `static/js/pages/medication` | 0 | 24 | 0.0% |
| `static/js/pages/nurse` | 0 | 42 | 0.0% |
| `static/js/pages/owner` | 0 | 26 | 0.0% |
| `static/js/pages/partials` | 0 | 12 | 0.0% |
| `static/js/pages/pharmacy` | 0 | 161 | 0.0% |
| `static/js/pages/portal` | 0 | 2 | 0.0% |
| `static/js/pages/print` | 0 | 18 | 0.0% |
| `static/js/pages/quality_compliance` | 0 | 15 | 0.0% |
| `static/js/pages/radiology` | 0 | 367 | 0.0% |
| `static/js/pages/reception` | 0 | 1,339 | 0.0% |
| `static/js/pages/report_builder` | 0 | 79 | 0.0% |
| `static/js/pages/super_admin` | 0 | 1,017 | 0.0% |
| `static/js/performance.js` | 0 | 289 | 0.0% |
| `static/js/pwa-install.js` | 0 | 43 | 0.0% |
| `static/js/security.js` | 0 | 209 | 0.0% |
| `static/js/smart-search.js` | 0 | 79 | 0.0% |
| `static/js/smart-select.js` | 0 | 14 | 0.0% |
| `static/js/theme-toggle.js` | 0 | 27 | 0.0% |
| `static/js/touch-mode.js` | 0 | 6 | 0.0% |
| `static/js/ui-preferences.js` | 0 | 43 | 0.0% |
| `static/js/utils` | 0 | 39 | 0.0% |
| `static/js/ux-enhance.js` | 0 | 80 | 0.0% |
| `static/js/digits-ar.js` | 14 | 21 | 66.7% |
| `static/js/core` | 19 | 19 | 100.0% |

## Least covered scripts

| script | covered/total | percent |
|---|---|---|
| `D:/recovers/data/medical/static/js/base.js` | 0/354 | 0.0% |
| `D:/recovers/data/medical/static/js/pages/radiology/process.js` | 0/342 | 0.0% |
| `D:/recovers/data/medical/static/js/pages/reception/create_visit.js` | 0/315 | 0.0% |
| `D:/recovers/data/medical/static/js/performance.js` | 0/289 | 0.0% |
| `D:/recovers/data/medical/static/js/pages/reception/queue_management.js` | 0/271 | 0.0% |
| `D:/recovers/data/medical/static/js/pages/super_admin/system_backup.js` | 0/245 | 0.0% |
| `D:/recovers/data/medical/static/js/security.js` | 0/209 | 0.0% |
| `D:/recovers/data/medical/static/js/pages/reception/patients.js` | 0/207 | 0.0% |
| `D:/recovers/data/medical/static/js/pages/pharmacy/pos.js` | 0/161 | 0.0% |
| `D:/recovers/data/medical/static/js/pages/doctor/prescription.js` | 0/158 | 0.0% |
| `D:/recovers/data/medical/static/js/pages/doctor/notes.js` | 0/142 | 0.0% |
| `D:/recovers/data/medical/static/js/pages/reception/create_appointment.js` | 0/141 | 0.0% |
| `D:/recovers/data/medical/static/js/pages/manager/unit_control.js` | 0/132 | 0.0% |
| `D:/recovers/data/medical/static/js/pages/super_admin/system_config.js` | 0/118 | 0.0% |
| `D:/recovers/data/medical/static/js/pages/doctor/dashboard.js` | 0/112 | 0.0% |
| `D:/recovers/data/medical/static/js/pages/reception/appointments.js` | 0/111 | 0.0% |
| `D:/recovers/data/medical/static/js/pages/reception/add_patient_to_queue.js` | 0/102 | 0.0% |
| `D:/recovers/data/medical/static/js/events.js` | 0/96 | 0.0% |
| `D:/recovers/data/medical/static/js/pages/super_admin/branding.js` | 0/92 | 0.0% |
| `D:/recovers/data/medical/static/js/pages/doctor/patient_queue.js` | 0/89 | 0.0% |

