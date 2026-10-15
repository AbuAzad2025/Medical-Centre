# Repository summary

One screen of what is actually measured in this repository. Every figure
below is read from a generated artefact; none of it is typed by hand, and
the generators are in `tools/reports/`.

## The three things worth knowing

| measure | current | detail |
|---|---|---|
| Backend Python statements | not measured here | `docs/reports/backend-coverage.md` |
| Frontend JavaScript statements | 0.5% | `docs/reports/frontend-coverage.md` — narrow measurement, see that file |
| State-changing routes reached by the scenario matrix | 100.0% | `docs/scenarios/generated/README.md` |

## Frontend — biggest gaps (by statement coverage)

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

## Frontend-Backend Template Matching

| metric | value |
|---|---|
| Frontend pages matched | 6/81 (7.4%) |
| Orphaned backend templates | 65 |
| Templates with missing frontend coverage | 64 |

See `docs/reports/frontend-backend-matching.md` for detailed cross-reference.

## Scenario matrix

| measure | count |
|---|---|
| generated | 2,491 |
| hand-written and audited | 40 |
| total | 2,531 |
| templates | 212 |
| code-derived axes | 84 |
| state-changing routes reached | 326/326 |

Families:

| family | scenarios |
|---|---|
| `clinical` | 1,122 |
| `financial` | 481 |
| `platform` | 484 |
| `rbac` | 404 |

## Why scenario count and coverage are different numbers

The matrix holds 2,531 scenarios and reaches
100.0% of the state-changing routes. Those two numbers are
not supposed to track each other, and the difference is deliberate: scenarios
multiply over a dimension, so a journey with a genuine five-value state
machine yields five scenarios while still touching one route. Conversely a
route can be reached by a single scenario. Counting scenarios to claim
coverage is the padding the matrix refuses to do, which is why every axis is
required to state what it changes and where its value comes from.

