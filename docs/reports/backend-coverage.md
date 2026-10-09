# Backend coverage

Produced by `pytest-cov` over `app`, `routes`, `services`, `models` and
`utils`, combined across the CI shards. Regenerate with
`python tools/reports/coverage_report.py`.

| measure | covered | statements | percent |
|---|---|---|---|
| covered lines / statements | 31,619 | 45,942 | 68.8% |

## By package

| package | covered | statements | percent |
|---|---|---|---|
| `routes` | 11,637 | 19,853 | 58.6% |
| `utils` | 603 | 871 | 69.2% |
| `services` | 8,081 | 11,163 | 72.4% |
| `app` | 5,952 | 7,916 | 75.2% |
| `models` | 5,346 | 6,139 | 87.1% |

## Least covered modules

Where the missing statements are, because a low percentage on a large
module is worth more attention than the same percentage on a small one.

| module | covered/total | percent |
|---|---|---|
| `app/modules/workflows/notifications_integration.py` | 0/29 | 0.0% |
| `app/modules/workflows/radiology.py` | 0/19 | 0.0% |
| `models/relationships_map.py` | 0/1 | 0.0% |
| `services/ai_validator.py` | 10/117 | 8.5% |
| `routes/accountant/__init__.py` | 57/287 | 19.9% |
| `services/file_service.py` | 41/200 | 20.5% |
| `services/report_scope_service.py` | 15/70 | 21.4% |
| `routes/manager/__init__.py` | 56/247 | 22.7% |
| `services/shift_handover_service.py` | 24/101 | 23.8% |
| `routes/nursing_assessment_routes.py` | 32/127 | 25.2% |
| `routes/medication_routes/__init__.py` | 55/215 | 25.6% |
| `services/hl7_mllp_service.py` | 34/126 | 27.0% |
| `services/ihe_pix_pdq_service.py` | 22/80 | 27.5% |
| `routes/mfa_routes.py` | 38/137 | 27.7% |
| `services/clinical_context_service.py` | 9/31 | 29.0% |
| `routes/backup_restore_routes.py` | 17/58 | 29.3% |
| `routes/emergency/cases.py` | 82/271 | 30.3% |
| `routes/super_admin/system.py` | 107/347 | 30.8% |
| `routes/lab/lis_import.py` | 13/42 | 31.0% |
| `routes/lab/fhir.py` | 53/171 | 31.0% |

