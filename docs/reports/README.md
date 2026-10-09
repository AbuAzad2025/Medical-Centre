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

