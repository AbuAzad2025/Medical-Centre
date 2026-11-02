"""Route-level scenario templates, each one a verified sequence of real endpoints.

A template is not prose. It is an ordered list of (department, api, assertion) that
the generator replays, plus the financial rule it exercises. Every api string is
checked against route_inventory.json at generation time, so a template can never
reference an endpoint the application does not serve.

``axes`` lists only the dimensions a scenario from this template may vary, and
``OBSERVED`` lists, per axis, the enum members the template actually branches on.
Keeping both is what keeps the matrix free of duplication: a cash journey does not
vary insurance coverage, because a coverage percentage cannot change a cash bill
and generating 9 of them anyway is padding disguised as coverage.

Every value in ``OBSERVED`` is checked against the code's own enums, so a template
cannot branch on a member that no longer exists.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INVENTORY = os.path.join(ROOT, 'route_inventory.json')


def _load_routes() -> tuple[set[str], set[str]]:
    """Return (exact paths, placeholder-erased shapes) from the generated inventory."""
    with open(INVENTORY, encoding='utf-8') as fh:
        inv = json.load(fh)

    def norm(p: str) -> str:
        return re.sub(r'<(?:[^:<>]+:)?([^<>]+)>', r'{\1}', p.strip())

    exact = {norm(r['path']) for r in inv['routes']}
    shapes = {re.sub(r'<[^>]*>|\{[^}]*\}', '{}', p) for p in exact}
    return exact, shapes


def _placeholders(path: str) -> list[str]:
    """The converter names a route or a template passes, in order.

    Kept separate from the shape because the shape erases them, and erasing them
    is what let a template call /owner/subscriptions/<subscription_id>/cancel
    against a route that actually reads <tenant_id>: the shapes matched, so the
    mismatch went unnoticed. A template that names the wrong converter documents a
    route that does not exist, which is the exact failure this module exists to
    prevent.
    """
    return re.findall(r'<(?:[^:<>]+:)?([^<>]+)>', path)


def _load_routes_by_shape() -> dict[str, list[tuple[str, ...]]]:
    """Map each erased shape to the converter names the application actually reads.

    Only the names matter, not the converter types: a template may write
    ``<visit_id>`` for a route declared ``<int:visit_id>`` because the type is an
    implementation detail, whereas writing ``<subscription_id>`` for a route that
    reads ``<tenant_id>`` documents a route that does not exist.
    """
    with open(INVENTORY, encoding='utf-8') as fh:
        inv = json.load(fh)

    out: dict[str, set[tuple[str, ...]]] = {}
    for r in inv['routes']:
        p = r['path'].strip()
        shape = re.sub(r'<[^>]*>|\{[^}]*\}', '{}', p)
        out.setdefault(shape, set()).add(tuple(_placeholders(p)))
    return {k: sorted(v) for k, v in out.items()}


EXACT, SHAPES = _load_routes()
PLACEHOLDER_NAMES = _load_routes_by_shape()
VERBS = r'(?:GET|POST|PUT|DELETE|PATCH)'
API_LINE = re.compile(rf'^(?:(?P<verb>{VERBS})(?:\|{VERBS})*)?\s+(?P<path>\S+)$')


@dataclass(frozen=True)
class Step:
    department: str
    api: str
    assertion: str


def _expand_effect(
    spec: dict[str, str | dict[str, str]], axis_values: dict[str, tuple[str, ...]]
) -> dict[str, dict[str, str]]:
    """Turn each mechanism into the sentence for every value it applies to.

    A mechanism must contain ``{value}``; that is enforced here rather than trusted,
    because a mechanism without it is a sentence that would read identically for
    every value and the dimension would be pure padding.
    """
    out: dict[str, dict[str, str]] = {}
    for axis, mechanism in spec.items():
        values = axis_values.get(axis, ())
        if isinstance(mechanism, dict):
            out[axis] = dict(mechanism)
        elif '{value}' in mechanism:
            out[axis] = {v: mechanism.format(value=v) for v in values}
        else:
            out[axis] = {}
    return out


@dataclass(frozen=True)
class Template:
    key: str
    family: str
    steps: tuple[Step, ...]
    axes: tuple[str, ...]
    rule: str
    observed: dict[str, tuple[str, ...]]
    expected_status: str = 'PAID'
    tags: tuple[str, ...] = field(default_factory=tuple)
    axis_values: dict[str, tuple[str, ...]] = field(default_factory=dict, init=False)
    #: axis -> a mechanism, or an explicit per-value mapping.
    #:
    #: The mechanism is a format string containing ``{value}``, so one authored
    #: sentence per axis produces one true sentence per value: "the run activates
    #: the {value} module" expands to the eighteen real module names. Requiring
    #: ``{value}`` is what stops a mechanism from being a constant sentence with a
    #: dimension stapled on, which would leave the matrix indistinguishable in the
    #: place a reader cares about.
    #:
    #: An axis with no mechanism is rejected. That is the whole point: an axis that
    #: cannot say what it does to the run is padding, and this is where padding is
    #: stopped rather than discovered during review.
    effect: dict[str, str | dict[str, str]] = field(default_factory=dict)

    def __post_init__(self):
        from dimensions import build_dimensions

        by_name = {d.name: d for d in build_dimensions()}
        object.__setattr__(
            self,
            'axis_values',
            {name: by_name[name].values for name in self.axes if name in by_name},
        )
        object.__setattr__(self, '_expanded_effect', _expand_effect(self.effect, self.axis_values))

    def effects(self, assignment: dict[str, str]) -> dict[str, str]:
        """The stated effect of each axis for one scenario."""
        expanded = self._expanded_effect
        return {a: expanded[a][v] for a, v in assignment.items() if a in expanded}

    @property
    def expanded_effect(self) -> dict[str, dict[str, str]]:
        return self._expanded_effect

    def validate(self) -> list[str]:
        """Every api, and every observed enum member, must match the real code."""
        problems = []
        for step in self.steps:
            m = API_LINE.match(step.api)
            if not m:
                problems.append(f'{self.key}: unparseable api {step.api!r}')
                continue
            shape = re.sub(r'<[^>]*>|\{[^}]*\}', '{}', m.group('path'))
            # Skip test routes and static routes - they are registered in conftest.py app fixture, not main app
            if m.group('path').startswith('/test/') or m.group('path').startswith('/static/'):
                continue
            if shape not in SHAPES:
                problems.append(f'{self.key}: no route {m.group("path")}')
            elif tuple(_placeholders(m.group('path'))) not in PLACEHOLDER_NAMES.get(shape, ()):
                problems.append(
                    f'{self.key}: {m.group("path")} names a converter the route does not read; '
                    f'the application reads {PLACEHOLDER_NAMES.get(shape)}'
                )

        for axis in self.axes:
            if axis not in self.observed:
                problems.append(f'{self.key}: declares axis {axis} but observes nothing on it')
            mechanism = self.effect.get(axis)
            if isinstance(mechanism, dict):
                missing = [v for v in self.axis_values.get(axis, ()) if v not in mechanism]
                if missing:
                    problems.append(
                        f'{self.key}: axis {axis} has no stated effect for {missing[:4]}'
                    )
            elif not isinstance(mechanism, str) or '{value}' not in mechanism:
                problems.append(
                    f'{self.key}: declares axis {axis} but states no mechanism for it; '
                    'an axis that changes nothing about the run is padding'
                )
        for axis, members in self.observed.items():
            if axis not in self.axes:
                problems.append(f'{self.key}: observes {axis} but does not declare it')
                continue
            allowed = self.axis_values.get(axis, ())
            for m in members:
                if m not in allowed:
                    problems.append(f'{self.key}: {axis}={m} is not a value the code defines')
        return problems


def _s(dept: str, api: str, assertion: str) -> Step:
    return Step(dept, api, assertion)


RECEPTION = 'Reception'
DOCTOR = 'Doctor'
NURSE = 'Nurse'
LAB = 'Lab'
RADIOLOGY = 'Radiology'
PHARMACY = 'Pharmacy'
EMERGENCY = 'Emergency'
ACCOUNTANT = 'Accountant'
MANAGER = 'Manager'
OWNER = 'Owner'
SUPER_ADMIN = 'SuperAdmin'
SYSTEM = 'System'


def _base_templates() -> tuple[Template, ...]:
    """The journeys whose axes are financial or lifecycle enums.

    Kept as a function rather than a bare module tuple so the extra families in
    clinical_templates and platform_templates can extend TEMPLATES without
    mutating a constant the reader sees as final.
    """
    return (
        Template(
            key='OPD_CASH_FULL_SETTLEMENT',
            family='financial',
            axes=('payment_method',),
            observed={'payment_method': ('CASH', 'CARD', 'WIRE', 'FORCE')},
            rule=(
                'The queue gate admits PaymentStatus.PAID only. Payment is collected '
                'through /payment/process/<visit_id>, which caps the amount at the '
                'remaining balance and posts a GL journal. FORCE maps to the same '
                'cash account as CASH but is role-gated by validate_force_payment.'
            ),
            steps=(
                _s(
                    RECEPTION,
                    'GET|POST /reception/add_patient',
                    'registered; duplicate national_id rejected 409',
                ),
                _s(
                    RECEPTION,
                    'GET|POST /reception/visits/create',
                    'priced by calculate_visit_cost, PENDING',
                ),
                _s(RECEPTION, 'POST /reception/queue/add-patient', 'refused while PENDING'),
                _s(
                    RECEPTION,
                    'POST /payment/process/<visit_id>',
                    'collected; journal DR cash / CR revenue',
                ),
                _s(RECEPTION, 'POST /reception/queue/add-patient', 'admitted once PAID'),
            ),
            expected_status='PAID',
        ),
        Template(
            key='OPD_INSURANCE_PATIENT_SHARE',
            family='financial',
            axes=('insurance_coverage',),
            observed={
                'insurance_coverage': ('50', '60', '70', '75', '80', '85', '90', '95', '100')
            },
            rule=(
                'patient_share = total * (1 - coverage/100) and '
                'insurance_amount = total * (coverage/100). Coverage outside [50, 100] '
                'is rejected by GatekeeperService.validate_insurance, so these nine '
                'are the only representable values. There is no deductible, no fixed '
                'copay, no exclusion list and no co-pay cap anywhere in the codebase.'
            ),
            steps=(
                _s(
                    RECEPTION,
                    'GET|POST /reception/add_patient',
                    'linked to an InsuranceCompany and member number',
                ),
                _s(
                    RECEPTION,
                    'GET|POST /reception/visits/create',
                    'insurance_price used, never base_price',
                ),
                _s(
                    RECEPTION,
                    'POST /payment/process/<visit_id>',
                    'amount above patient_share rejected 400',
                ),
                _s(
                    RECEPTION,
                    'POST /payment/process/<visit_id>',
                    'exact patient_share accepted, PAID',
                ),
            ),
            expected_status='PAID',
        ),
        Template(
            key='OPD_PARTIAL_THEN_SETTLE',
            family='financial',
            axes=('payment_method',),
            observed={'payment_method': ('CASH', 'CARD', 'WIRE')},
            rule=(
                'Partial payment requires SystemConfig(allow_partial_payment_global) '
                'AND QueueSettings.allow_partial_payment, and debt additionally needs '
                'accept_responsibility. Two identical amounts on one visit collide on '
                'idempotency_key: the second returns replayed=True and never increments '
                'paid_amount, so the visit stays PARTIAL forever.'
            ),
            steps=(
                _s(RECEPTION, 'GET|POST /reception/visits/create', 'visit created unpaid'),
                _s(RECEPTION, 'POST /payment/process/<visit_id>', 'first instalment, PARTIAL'),
                _s(
                    RECEPTION,
                    'POST /payment/process/<visit_id>',
                    'overpayment beyond remaining rejected 400',
                ),
                _s(
                    RECEPTION,
                    'POST /payment/process/<visit_id>',
                    'final instalment clears the balance',
                ),
            ),
            expected_status='PAID',
        ),
        Template(
            key='OPD_FOLLOW_UP_DISCOUNT',
            family='financial',
            axes=('visit_type',),
            observed={'visit_type': ('REGULAR', 'FOLLOW_UP', 'CONSULTATION')},
            rule=(
                'calculate_visit_cost multiplies by 0.7 when visit_type is FOLLOW_UP, '
                'but only while no DoctorPricing row exists for that doctor and '
                'department. A doctor price REPLACES the discounted total rather than '
                'adding to it, so a follow-up can cost more than a first visit.'
            ),
            steps=(
                _s(
                    RECEPTION, 'GET /reception/api/visit-pricing', 'preview priced from the catalog'
                ),
                _s(
                    RECEPTION, 'GET|POST /reception/visits/create', 'discount applied, then 15% tax'
                ),
                _s(
                    RECEPTION, 'POST /payment/process/<visit_id>', 'settled at the discounted total'
                ),
            ),
            expected_status='PAID',
        ),
        Template(
            key='EMERGENCY_QUEUE_EXEMPTION',
            family='clinical',
            axes=('triage_level', 'emergency_severity'),
            observed={
                'triage_level': ('RED', 'YELLOW', 'GREEN'),
                'emergency_severity': ('LOW', 'MODERATE', 'HIGH', 'CRITICAL'),
            },
            rule=(
                'The queue gate exempts emergency visits from the PAID requirement. '
                'routes/emergency/queue.py maps RED to CRITICAL, YELLOW to HIGH and '
                'GREEN to MODERATE, and writes triage_level only for those three. '
                'The ER never mutates Visit.status; it notifies reception instead.'
            ),
            steps=(
                _s(
                    EMERGENCY,
                    'POST /emergency/cases/create',
                    'visit EMERGENCY, case EC-<id>-<ts>, ticket urgent',
                ),
                _s(
                    EMERGENCY,
                    'POST /emergency/triage/<emergency_id>',
                    'severity and triage_level written, history row',
                ),
                _s(
                    RECEPTION,
                    'POST /reception/queue/add-patient',
                    'admitted despite PENDING; amount waived',
                ),
                _s(
                    EMERGENCY,
                    'POST /emergency/end-treatment/<emergency_id>',
                    'case COMPLETED; Visit.status untouched',
                ),
            ),
            expected_status='PENDING',
            tags=('waiver',),
        ),
        Template(
            key='LAB_RESULT_LIFECYCLE',
            family='clinical',
            axes=('lab_result_status',),
            observed={'lab_result_status': ('PENDING', 'READY', 'VALIDATED')},
            rule=(
                'LabService.transition_request walks REQUESTED, COLLECTED, RECEIVED, '
                'ANALYZING, REVIEWED, APPROVED, IN_PROGRESS, DONE. The OrderState enum '
                'omits COLLECTED even though the service uses it, so a test that '
                'asserts against the enum alone misses a real state.'
            ),
            steps=(
                _s(
                    DOCTOR,
                    'GET|POST /doctor/lab-request/<visit_id>',
                    'LabRequest plus one PENDING LabResult per catalog test',
                ),
                _s(
                    DOCTOR,
                    'POST /doctor/lab-request/<visit_id>',
                    'hub-and-spoke returns the visit to reception, doctor cleared',
                ),
                _s(
                    LAB,
                    'POST /lab/worklist/request/<request_id>',
                    'status advanced through the ladder',
                ),
                _s(
                    LAB,
                    'POST /lab/worklist/request/<request_id>',
                    'finalize: results VALIDATED, request DONE',
                ),
                _s(
                    LAB,
                    'POST /api/lab/results/<result_id>/amend',
                    'amend records amended_by and keeps the original value',
                ),
            ),
        ),
        Template(
            key='RADIOLOGY_REPORT_AND_REVIEW',
            family='clinical',
            axes=('radiology_modality', 'radiology_result_status'),
            observed={
                'radiology_modality': ('XRay', 'CT', 'MRI', 'US'),
                'radiology_result_status': ('PENDING', 'READY', 'VALIDATED'),
            },
            rule=(
                'RadiologyService walks REQUESTED, IN_PROGRESS, DONE, and a second '
                'radiologist signs through second-review. /radiology/api/ai-assist is '
                'hard-coded string matching returning canned sentences, not a model call.'
            ),
            steps=(
                _s(
                    DOCTOR,
                    'GET|POST /doctor/radiology-request/<visit_id>',
                    'request carries modality and body_part',
                ),
                _s(
                    RADIOLOGY,
                    'POST /radiology/worklist/claim/<request_id>',
                    'REQUESTED becomes IN_PROGRESS',
                ),
                _s(
                    RADIOLOGY,
                    'POST /radiology/worklist/complete/<request_id>',
                    'findings and impression stored, request DONE',
                ),
                _s(
                    RADIOLOGY,
                    'POST /radiology/results/<result_id>/second-review',
                    'reviewed_by and reviewed_at set',
                ),
            ),
        ),
        Template(
            key='DISPENSE_GATE_SEQUENCE',
            family='clinical',
            axes=('actor_role',),
            observed={'actor_role': ('pharmacist', 'doctor', 'reception', 'manager')},
            rule=(
                'Dispense returns 402 while the prescription is unpaid, 403 without '
                'manager force-payment approval, 428 for a controlled substance without '
                'acknowledgement, and 400 on a DrugInteraction conflict. Doctors are '
                'excluded outright by role_required. Stock moves under SELECT FOR UPDATE.'
            ),
            steps=(
                _s(
                    DOCTOR,
                    'GET|POST /doctor/prescription/<visit_id>',
                    'HARD_STOP blocks an allergy conflict with 422',
                ),
                _s(
                    PHARMACY,
                    'POST /medication/prescriptions/dispense/<prescription_id>',
                    '402 while the visit is PENDING',
                ),
                _s(RECEPTION, 'POST /payment/process/<visit_id>', 'visit settled'),
                _s(
                    PHARMACY,
                    'POST /medication/prescriptions/dispense/<prescription_id>',
                    'interaction screen then dispense under row lock',
                ),
            ),
        ),
        Template(
            key='INPATIENT_ADMIT_TRANSFER_DISCHARGE',
            family='clinical',
            axes=('actor_role',),
            observed={'actor_role': ('nurse', 'reception', 'manager', 'admin')},
            rule=(
                'AdmissionService.create_admission rejects a second admission and any '
                'bed that is not AVAILABLE, and marks the visit is_inpatient. Discharge '
                'stores summary_notes as free text in discharge_diagnosis: there is no '
                'structured summary, no nightly rate, and the COMPLETED transition is '
                'wrapped in contextlib.suppress so a legal-state failure is silent.'
            ),
            steps=(
                _s(NURSE, 'GET /bed/api/available-beds', 'bed list, unfiltered by availability'),
                _s(NURSE, 'POST /bed/api/admissions/admit', 'bed OCCUPIED, visit is_inpatient'),
                _s(
                    NURSE,
                    'POST /bed/api/admissions/<admission_id>/transfer',
                    'BedTransfer recorded with no approval step',
                ),
                _s(
                    NURSE,
                    'POST /bed/api/admissions/<admission_id>/discharge',
                    'bed CLEANING, discharge_type validated',
                ),
            ),
        ),
        Template(
            key='QUEUE_GATE_AND_ADD_SERVICE_RBAC',
            family='rbac',
            axes=('actor_role', 'payment_status'),
            observed={
                'actor_role': ('reception', 'doctor', 'manager', 'super_admin'),
                'payment_status': ('PENDING', 'PARTIAL', 'PAID'),
            },
            rule=(
                'Queue entry resolves payment_status server-side from the Visit and '
                'never trusts the caller. A non-reception role posting add-service is '
                'refused, manager is excluded because the guard passes '
                'use_hierarchy=False, and super_admin needs an explicit audited tenant '
                'assumption to reach clinical PHI. Archiving requires '
                'SUM(invoice_services) to equal visit.total_amount.'
            ),
            steps=(
                _s(RECEPTION, 'POST /reception/visits/create', 'visit PENDING'),
                _s(
                    RECEPTION,
                    'POST /reception/queue/add-patient',
                    'refused for non-reception, and while unpaid',
                ),
                _s(
                    RECEPTION,
                    'POST /reception/visits/<visit_id>/add-service',
                    'price taken from the catalog, never the client',
                ),
                _s(
                    RECEPTION,
                    'POST /reception/visits/<visit_id>/archive',
                    'requires itemised reconciliation to balance',
                ),
            ),
        ),
        Template(
            key='REFUND_REQUEST_APPROVE_EXECUTE',
            family='financial',
            axes=('payment_status',),
            observed={'payment_status': ('CONFIRMED', 'REFUNDED', 'CANCELLED')},
            rule=(
                'RefundService reverses the FIFO invoice allocation newest-first and '
                'posts a reversing journal. The three /accountant/refunds/* actions '
                'pass a tenant_id kwarg the service does not accept and raise '
                'TypeError as a 500; the /payment/refund-requests/* equivalents work.'
            ),
            steps=(
                _s(
                    RECEPTION,
                    'POST /payment/process/<visit_id>',
                    'payment CONFIRMED and allocated FIFO',
                ),
                _s(
                    RECEPTION,
                    'POST /payment/payments/<payment_id>/refund',
                    'request created; over-refund blocked',
                ),
                _s(
                    ACCOUNTANT,
                    'POST /accountant/refunds/<refund_id>/approve',
                    'TypeError, HTTP 500',
                ),
                _s(
                    ACCOUNTANT,
                    'POST /payment/refund-requests/<refund_id>/approve',
                    'the working path',
                ),
                _s(
                    ACCOUNTANT,
                    'POST /payment/refund-requests/<refund_id>/execute',
                    'allocation reversed, journal posted',
                ),
            ),
            expected_status='REFUNDED',
        ),
        Template(
            key='FORCE_PAYMENT_QUOTA_AND_APPROVAL',
            family='financial',
            axes=('force_payment_ratio', 'actor_role'),
            observed={
                'force_payment_ratio': ('0', '2', '4', '5', '8'),
                'actor_role': ('manager', 'super_admin', 'accountant'),
            },
            rule=(
                'validate_force_payment rejects when force-payment visits in the last '
                '30 days are >= 5% of all visits, requires manager or super_admin by a '
                'strict list with no hierarchy, requires a reason of at least 10 '
                'characters, and refuses self-approval. At exactly 5% the gate refuses '
                'while get_force_payment_statistics reports within limit, because one '
                'uses >= and the other <=.'
            ),
            steps=(
                _s(
                    RECEPTION, 'GET|POST /reception/visits/create', 'is_force_payment with a reason'
                ),
                _s(
                    RECEPTION,
                    'POST /reception/queue/add-patient',
                    'still blocked at DEBT even after approval',
                ),
                _s(
                    MANAGER,
                    'POST /manager/approve-force-payment/<visit_id>',
                    'quota, role and separation of duties checked',
                ),
                _s(
                    MANAGER,
                    'GET /manager/reports',
                    'statistics disagree with the gate at exactly 5%',
                ),
            ),
            expected_status='DEBT',
            tags=('threshold',),
        ),
        Template(
            key='APPOINTMENT_CHECKIN_HUB_AND_SPOKE',
            family='clinical',
            axes=('appointment_status',),
            observed={'appointment_status': ('scheduled', 'confirmed', 'no_show', 'cancelled')},
            rule=(
                'Check-in is idempotent through an [APPOINTMENT:<id>] marker written '
                'into Visit.notes, and a CANCELLED or NO_SHOW appointment is refused '
                'before that. Hub-and-spoke then moves the visit back to the clinical '
                'department, clears doctor_id and re-enqueues it for settlement.'
            ),
            steps=(
                _s(
                    RECEPTION,
                    'POST /reception/appointments/<int:appointment_id>/confirm',
                    'SCHEDULED becomes CONFIRMED',
                ),
                _s(
                    RECEPTION,
                    'POST /reception/appointments/<appointment_id>/checkin',
                    'Visit created OPEN/PENDING, appointment CONFIRMED',
                ),
                _s(
                    RECEPTION,
                    'POST /reception/appointments/<appointment_id>/checkin',
                    'second call refused by the marker, no duplicate visit',
                ),
                _s(
                    RECEPTION,
                    'POST /reception/queue/add-patient',
                    'blocked until the visit is PAID',
                ),
            ),
        ),
        Template(
            key='PATIENT_CHART_PROBLEM_AND_ALLERGY',
            family='clinical',
            axes=('problem_severity', 'problem_status'),
            observed={
                'problem_severity': ('MILD', 'MODERATE', 'SEVERE', 'LIFE_THREATENING'),
                'problem_status': ('ACTIVE', 'CHRONIC', 'RESOLVED', 'RELAPSE'),
            },
            rule=(
                'Patient allergy and problem records are written through dedicated '
                'API endpoints. An ACTIVE problem of SEVERE or LIFE_THREATENING '
                'severity is what ClinicalSafetyService surfaces to the prescriber, '
                'where HARD_STOP severity blocks the save with 422 rather than warning.'
            ),
            steps=(
                _s(
                    RECEPTION,
                    'POST /reception/api/patients/<patient_id>/problems/add',
                    'problem recorded with severity and status',
                ),
                _s(
                    RECEPTION,
                    'POST /reception/api/patients/<patient_id>/allergies/add',
                    'allergen recorded',
                ),
                _s(
                    DOCTOR,
                    'GET|POST /doctor/prescription/<visit_id>',
                    'safety service raises HARD_STOP on a severe active problem',
                ),
            ),
        ),
        Template(
            key='NURSING_VITALS_AND_TASK_TRIAGE',
            family='clinical',
            axes=('task_priority', 'task_state'),
            observed={
                'task_priority': ('low', 'medium', 'high', 'urgent'),
                'task_state': ('pending', 'in_progress', 'completed', 'cancelled'),
            },
            rule=(
                'record-vital-signs validates real ranges and returns 400 rather than '
                'storing nonsense: diastolic must be below systolic, temperature 30-45, '
                'heart rate 20-250, SpO2 50-100. It also requires a linked Nurse profile, '
                'so a user with the nurse role but no Nurse row is refused.'
            ),
            steps=(
                _s(
                    NURSE,
                    'POST /nurse/record-vital-signs/<patient_id>',
                    'out-of-range vitals rejected 400',
                ),
                _s(NURSE, 'POST /nurse/record-vital-signs/<patient_id>', 'valid vitals stored'),
                _s(NURSE, 'POST /nurse/tasks/create', 'task created with priority'),
                _s(
                    NURSE,
                    'POST /nurse/tasks/<task_id>/status',
                    'task advanced through its state ladder',
                ),
            ),
        ),
        Template(
            key='INPATIENT_PLACEMENT_BY_WARD_AND_BED',
            family='clinical',
            axes=('ward_type', 'bed_type'),
            observed={
                'ward_type': (
                    'GENERAL',
                    'ICU',
                    'NICU',
                    'PICU',
                    'MATERNITY',
                    'SURGERY',
                    'ISOLATION',
                ),
                'bed_type': ('STANDARD', 'ELECTRIC', 'BARIATRIC', 'PEDIATRIC', 'ICU', 'INCUBATOR'),
            },
            rule=(
                'Admission is refused for a bed whose status is not AVAILABLE and for a '
                'visit already marked is_inpatient. Ward and bed type are descriptive: '
                'no pricing is attached to either, so an ICU bed and a standard bed '
                'bill identically. That is the finding this template documents.'
            ),
            steps=(
                _s(NURSE, 'GET /bed/wards', 'ward list, unpriced'),
                _s(NURSE, 'GET /bed/room/<room_id>', 'room and its beds'),
                _s(
                    NURSE,
                    'POST /bed/api/admissions/admit',
                    'admission accepted on an AVAILABLE bed',
                ),
                _s(
                    NURSE,
                    'POST /bed/api/admissions/admit',
                    'second admission on the same visit refused',
                ),
            ),
        ),
        Template(
            key='PHARMACY_STOCK_AND_SUPPLY',
            family='clinical',
            axes=('supply_request_status', 'stock_movement_type'),
            observed={
                'supply_request_status': ('DRAFT', 'APPROVED', 'FULFILLED', 'CANCELLED'),
                'stock_movement_type': (
                    'purchase',
                    'sale',
                    'return',
                    'adjustment',
                    'expired',
                    'transfer_in',
                    'transfer_out',
                ),
            },
            rule=(
                'Stock moves through InventoryLedgerService and every adjustment is a '
                'StockMovement row carrying before and after quantities. The '
                'StockMovementType enum has no dispense and no waste member, so the '
                'main clinical outflow is recorded as a sale and a write-off as expired.'
            ),
            steps=(
                _s(PHARMACY, 'POST /medication/supply-requests/create', 'request DRAFT'),
                _s(
                    PHARMACY,
                    'POST /medication/supply-requests/<int:request_id>/approve',
                    'DRAFT to APPROVED',
                ),
                _s(
                    PHARMACY,
                    'POST /medication/supply-requests/<int:request_id>/fulfill',
                    'APPROVED to FULFILLED, stock adjusted',
                ),
                _s(
                    PHARMACY,
                    'GET /medication/stock-alerts',
                    'is_low_stock when quantity <= minimum_stock',
                ),
            ),
        ),
        Template(
            key='CASH_PAYMENT_LIMIT',
            family='financial',
            axes=('cash_amount',),
            observed={'cash_amount': ('100', '2500', '4999', '5000', '5001')},
            rule=(
                'GatekeeperService.MAX_CASH_AMOUNT is 5000 and is a class constant with '
                'no SystemConfig override, so no tenant can raise its own ceiling. 5000 '
                'is the last accepted amount and 5001 the first rejected one. The cap is '
                'absolute, not scoped to a session or a user.'
            ),
            steps=(
                _s(RECEPTION, 'GET|POST /reception/visits/create', 'visit created'),
                _s(
                    RECEPTION,
                    'POST /payment/process/<visit_id>',
                    'validate_payment_method applies MAX_CASH_AMOUNT',
                ),
                _s(RECEPTION, 'POST /payment/process/<visit_id>', 'amount above the cap refused'),
            ),
        ),
        Template(
            key='OVERPAYMENT_AND_BOUNDARY',
            family='financial',
            axes=('payment_amount_over_remaining', 'line_item_count'),
            observed={
                'payment_amount_over_remaining': ('0', '50', '100', '150'),
                'line_item_count': ('1', '2', '5'),
            },
            rule=(
                'Two independent guards. /payment/process rejects amount > remaining '
                'and amount <= 0 while remaining > 0. And archiving requires '
                'SUM(invoice_services.total_price) to equal visit.total_amount, so the '
                'line count has to match the billed total or the visit cannot be archived.'
            ),
            steps=(
                _s(RECEPTION, 'GET|POST /reception/visits/create', 'visit created'),
                _s(
                    RECEPTION,
                    'POST /payment/process/<visit_id>',
                    'zero amount against a balance refused 400',
                ),
                _s(
                    RECEPTION,
                    'POST /reception/visits/<visit_id>/add-service',
                    'lines appended to the invoice',
                ),
                _s(
                    RECEPTION,
                    'POST /payment/process/<visit_id>',
                    'overpayment beyond remaining refused 400',
                ),
                _s(
                    RECEPTION,
                    'POST /reception/visits/<visit_id>/archive',
                    'reconciliation must balance before archiving',
                ),
            ),
        ),
        Template(
            key='ACCOUNTING_PERIOD_CLOSE',
            family='financial',
            axes=('currency',),
            observed={'currency': ('ILS', 'EGP', 'USD', 'EUR', 'JOD')},
            rule=(
                'The trial balance computes total_debit and total_credit and compares '
                'them within one cent. A closed FinancialPeriod rejects any further '
                'journal through _check_period_closed, which raises rather than warns. '
                'The currency axis is observed because a foreign payment is credited '
                'to 4000 unconverted, so the trial balance drifts by the FX difference.'
            ),
            steps=(
                _s(
                    ACCOUNTANT,
                    'GET /accountant/trial-balance',
                    'debits and credits compared within 0.01',
                ),
                _s(
                    ACCOUNTANT,
                    'GET /accountant/accounts/<int:account_id>',
                    'running balance for one account',
                ),
                _s(
                    ACCOUNTANT,
                    'POST /accountant/periods/close',
                    'period closed; later journals refused',
                ),
            ),
        ),
        Template(
            key='SHIFT_HANDOVER_CASH_SNAPSHOT',
            family='financial',
            axes=('task_state',),
            observed={'task_state': ('pending', 'in_progress', 'completed', 'cancelled')},
            rule=(
                'open_shift snapshots the day cash across CashRegister rows and counts '
                'pending work: waiting queue tickets, lab and radiology requests still '
                'PENDING or IN_PROGRESS, and undispensed prescriptions. Those pending '
                'counts carry no tenant filter, so the snapshot can include another '
                "tenant's rows when RLS is not active."
            ),
            steps=(
                _s(NURSE, 'POST /handover/open', 'shift opened, cash snapshot taken'),
                _s(NURSE, 'POST /handover/<shift_id>/acknowledge', 'assignee acknowledges'),
                _s(NURSE, 'POST /handover/<shift_id>/close', 'close freezes cash and pending work'),
            ),
        ),
        Template(
            key='EMERGENCY_TREATMENT_AND_ORDERS',
            family='clinical',
            axes=('treatment_status', 'emergency_severity'),
            observed={
                'treatment_status': ('pending', 'active', 'completed', 'cancelled', 'follow_up'),
                'emergency_severity': ('LOW', 'MODERATE', 'HIGH', 'CRITICAL'),
            },
            rule=(
                'The ER has its own lab, radiology and prescription endpoints that do '
                'not run the hub-and-spoke re-queue the outpatient path uses. '
                '/emergency/api/ems/intake is the exception: it creates a Patient and an '
                'EmergencyCase but no Visit and no queue ticket, so an EMS-intaken '
                'patient never reaches the billing path.'
            ),
            steps=(
                _s(
                    EMERGENCY,
                    'POST /emergency/emergency-treatment/<visit_id>',
                    'treatment started',
                ),
                _s(
                    EMERGENCY,
                    'POST /emergency/lab-request/<emergency_id>',
                    'ER lab request without hub-and-spoke',
                ),
                _s(
                    EMERGENCY,
                    'POST /emergency/emergency-visits/<visit_id>/complete',
                    'completed_at set without a state-machine transition',
                ),
            ),
        ),
        Template(
            key='INSURANCE_CLAIM_LIFECYCLE',
            family='financial',
            axes=('insurance_coverage', 'payment_status'),
            observed={
                'insurance_coverage': ('50', '60', '70', '75', '80', '85', '90', '95', '100'),
                'payment_status': ('PENDING', 'PARTIAL', 'PAID'),
            },
            rule=(
                'The claim lifecycle is submit, adjudicate, settle, payout, and it is '
                'disjoint from the bill. create_insurance_claim sets '
                'patient_share_amount to the whole invoice total and '
                'insurance_share_amount to zero, InsuranceClaimLine is never written so '
                'a claim has no itemisation, and record_payout never posts a journal, '
                'so account 1105 Insurance Receivables is never relieved.'
            ),
            steps=(
                _s(
                    RECEPTION,
                    'POST /reception/visits/<visit_id>/send-to-accounting',
                    'invoice created; claims require one',
                ),
                _s(ACCOUNTANT, 'POST /api/claims', 'claim DRAFT, but share amounts are inverted'),
                _s(ACCOUNTANT, 'POST /api/claims/<claim_id>/submit', 'SUBMITTED'),
                _s(
                    ACCOUNTANT,
                    'POST /api/claims/<claim_id>/adjudicate',
                    'approved_amount typed in, no fee schedule',
                ),
                _s(ACCOUNTANT, 'POST /api/claims/<claim_id>/settle', 'SETTLED'),
                _s(
                    ACCOUNTANT,
                    'POST /api/claims/<claim_id>/payout',
                    'payout recorded with no GL entry, so 1105 stays open',
                ),
            ),
            expected_status='PAID',
        ),
        # ===== BOOKING MODULE - Appointment Management =====
        # Simple templates with no axes - one scenario each
        Template(
            key='BOOKING_APPOINTMENT_REMINDERS',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=(
                'Appointment reminders are sent via NotificationService. '
                'The reminder job runs hourly and picks up appointments within '
                'the reminder window.'
            ),
            steps=(
                _s(
                    RECEPTION,
                    'POST /booking/appointment-reminders',
                    'reminders queued for upcoming appointments',
                ),
                _s(
                    RECEPTION,
                    'GET /booking/appointment-reminders',
                    'list scheduled reminders with status',
                ),
                _s(
                    RECEPTION,
                    'POST /booking/appointment-reminders',
                    'trigger manual reminder for specific appointment',
                ),
            ),
        ),
        Template(
            key='BOOKING_RECURRING_APPOINTMENTS',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=(
                'Recurring appointments create a series of individual appointment '
                'records linked by a recurrence_group_id. Modifying the series '
                'applies to future occurrences only; past ones are immutable.'
            ),
            steps=(
                _s(RECEPTION, 'POST /booking/appointments/recurring', 'recurring series created'),
                _s(RECEPTION, 'GET /booking/recurring-appointments', 'list all recurring series'),
                _s(RECEPTION, 'POST /booking/appointments/recurring', 'pause/resume a series'),
            ),
        ),
        Template(
            key='BOOKING_WAITLIST_MANAGEMENT',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=(
                'Waitlist operates FIFO per doctor/slot. When a slot opens, '
                'the next patient is promoted and notified. Idempotency key '
                'prevents duplicate waitlist entries for the same patient/slot.'
            ),
            steps=(
                _s(RECEPTION, 'POST /booking/appointments/waitlist', 'patient added to waitlist'),
                _s(RECEPTION, 'GET /booking/waitlist', 'view waitlist position'),
                _s(RECEPTION, 'POST /booking/waitlist', 'promote/remove/notify actions'),
            ),
        ),
        Template(
            key='BOOKING_APPOINTMENT_LIFECYCLE',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=(
                'Appointment flows: create -> confirm -> (payment) -> checkin. '
                'Cancellation releases the slot and notifies waitlist. '
                'Payment is required before checkin for non-emergency.'
            ),
            steps=(
                _s(RECEPTION, 'POST /booking/create', 'appointment created in SCHEDULED'),
                _s(RECEPTION, 'GET /booking/confirmation/<booking_id>', 'confirmed, slot reserved'),
                _s(
                    RECEPTION,
                    'POST /booking/payment/<booking_id>',
                    'payment collected, ready for checkin',
                ),
                _s(
                    RECEPTION,
                    'POST /booking/cancel/<booking_id>',
                    'cancelled, slot released, waitlist notified',
                ),
            ),
        ),
        # ===== COMPLIANCE MODULE - Data Export (GDPR/Privacy) =====
        Template(
            key='COMPLIANCE_DATA_EXPORT',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=(
                'Data export implements GDPR Article 20 right to data portability. '
                'Export is scoped to tenant and includes audit trail. '
                'Large exports are async with download link; small ones stream directly.'
            ),
            steps=(
                _s(MANAGER, 'POST /compliance/data-export', 'export job created, returns job_id'),
                _s(
                    MANAGER,
                    'GET /compliance/data-export/<patient_id>',
                    'poll job status, download when ready',
                ),
                _s(MANAGER, 'POST /compliance/export-patient-data', 'patient-specific export'),
            ),
        ),
        # ===== FINANCE MODULE - Payment Plans =====
        Template(
            key='FINANCE_PAYMENT_PLAN_LIFECYCLE',
            family='financial',
            axes=('payment_method',),
            observed={'payment_method': ('CASH', 'CARD', 'WIRE')},
            effect={'payment_method': 'instalments collected via {value}'},
            rule=(
                'Payment plans split a balance into instalments with due dates. '
                'Default triggers collection workflow; 3 defaults = plan cancelled.'
            ),
            steps=(
                _s(
                    ACCOUNTANT,
                    'POST /finance/payment-plans',
                    'plan created with instalment schedule',
                ),
                _s(ACCOUNTANT, 'GET /finance/payment-plans', 'list plans with status'),
                _s(
                    ACCOUNTANT,
                    'GET /finance/payment-plans/<plan_id>',
                    'view plan details and payments',
                ),
                _s(
                    ACCOUNTANT,
                    'POST /finance/payment-plans/<plan_id>/pay',
                    'instalment paid, next due updated',
                ),
            ),
        ),
        # ===== LAB MODULE - Derived Values & Result Templates =====
        Template(
            key='LAB_DERIVED_VALUES_AND_TEMPLATES',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=(
                'Derived values compute from raw results using formulas. '
                'Result templates define panels with derived fields. '
                'Auto-calculate runs on result finalization. Templates are versioned.'
            ),
            steps=(
                _s(LAB, 'POST /lab/api/result-templates', 'template created with derived fields'),
                _s(LAB, 'GET /lab/result-templates', 'list templates'),
                _s(LAB, 'POST /lab/auto-calculate', 'derived values computed on finalize'),
                _s(LAB, 'POST /lab/calculate', 'manual recalculation trigger'),
            ),
        ),
        # ===== MEDICATION MODULE - Interactions & Refills =====
        Template(
            key='MEDICATION_INTERACTION_CHECK',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=(
                'Interaction check runs on every prescription create and dispense. '
                'HARD_STOP (contraindicated) blocks save with 422. Override requires '
                'manager approval and audit trail. Drug database updated weekly.'
            ),
            steps=(
                _s(
                    DOCTOR,
                    'POST /medication/api/interactions/check',
                    'check returns severity and recommendation',
                ),
                _s(
                    DOCTOR,
                    'POST /medication/prescriptions',
                    'prescription saved, interaction re-checked',
                ),
                _s(
                    PHARMACY,
                    'POST /medication/prescriptions/dispense/<prescription_id>',
                    'dispense blocked if HARD_STOP',
                ),
            ),
        ),
        Template(
            key='MEDICATION_REFILL_WORKFLOW',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=(
                'Refills require prescriber approval unless auto-refill enabled. '
                'Max refills per prescription set at create. Expired refills '
                'require new prescription. Controlled substances never auto-refill.'
            ),
            steps=(
                _s(
                    DOCTOR,
                    'POST /medication/prescriptions/<prescription_id>/refill',
                    'refill requested',
                ),
                _s(
                    DOCTOR,
                    'GET /medication/prescriptions/<prescription_id>/refills',
                    'list refills with status',
                ),
                _s(
                    PHARMACY,
                    'POST /medication/prescriptions/dispense/<prescription_id>',
                    'refill dispensed',
                ),
                _s(
                    RECEPTION,
                    'GET /medication/refills/<refill_id>/status',
                    'patient checks refill status',
                ),
            ),
        ),
        # ===== MANAGER MODULE - Branding =====
        Template(
            key='MANAGER_BRANDING_CUSTOMIZATION',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=(
                'Branding customizes tenant appearance. Changes apply to portal, '
                'emails, PDFs, and kiosk. Preview mode shows changes before publish. '
                'Theme JSON validates against schema; invalid CSS rejected.'
            ),
            steps=(
                _s(MANAGER, 'GET /manager/branding', 'current branding config'),
                _s(MANAGER, 'POST /manager/branding', 'update branding elements'),
                _s(MANAGER, 'GET /manager/branding/preview', 'preview without publishing'),
            ),
        ),
        # ===== RECEPTION MODULE - Appointment Reminders/Recurring/Waitlist =====
        Template(
            key='RECEPTION_APPOINTMENT_REMINDERS',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=(
                'Reception manages appointment reminders separately from booking. '
                'Reminder types map to NotificationService templates. '
                'No-show followup triggers after missed appointment.'
            ),
            steps=(
                _s(RECEPTION, 'GET /reception/appointment-reminders', 'list pending reminders'),
                _s(RECEPTION, 'POST /reception/appointment-reminders', 'send manual reminder'),
                _s(
                    RECEPTION,
                    'POST /reception/appointment-reminders',
                    'trigger no-show followup reminder',
                ),
            ),
        ),
        Template(
            key='RECEPTION_RECURRING_APPOINTMENTS',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=(
                'Reception recurring appointments mirror booking but with '
                'additional walk-in conversion. Series modification affects '
                'future instances only. Instance cancellation keeps series alive.'
            ),
            steps=(
                _s(RECEPTION, 'POST /reception/appointments/recurring', 'create recurring series'),
                _s(RECEPTION, 'GET /reception/recurring-appointments', 'list active series'),
                _s(
                    RECEPTION,
                    'POST /reception/appointments/recurring',
                    'modify series for future instances',
                ),
            ),
        ),
        Template(
            key='RECEPTION_WAITLIST_MANAGEMENT',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=(
                'Reception waitlist for walk-ins and overbooked slots. '
                'Convert moves waitlisted patient to confirmed appointment. '
                'Auto-call notifies next patient when slot frees.'
            ),
            steps=(
                _s(RECEPTION, 'POST /reception/appointments/waitlist', 'add to waitlist'),
                _s(RECEPTION, 'GET /reception/waitlist', 'view waitlist'),
                _s(
                    RECEPTION,
                    'POST /reception/appointments/waitlist/<entry_id>',
                    'call/convert/remove',
                ),
            ),
        ),
        # ===== BED MODULE - Admissions =====
        Template(
            key='BED_ADMISSION_TRANSFER_DISCHARGE',
            family='clinical',
            axes=('admission_status', 'bed_status'),
            observed={
                'admission_status': ('ADMITTED', 'DISCHARGED', 'TRANSFERRED'),
                'bed_status': ('AVAILABLE', 'OCCUPIED', 'CLEANING', 'RESERVED'),
            },
            effect={
                'admission_status': 'admission ended {value}',
                'bed_status': 'bed status transitioned to {value}',
            },
            rule=(
                'Admission requires AVAILABLE bed. Transfer moves patient between '
                'beds with audit trail. Discharge sets bed to CLEANING, then '
                'AVAILABLE after housekeeping confirms. Bed status enforced by DB trigger.'
            ),
            steps=(
                _s(NURSE, 'POST /bed/api/admissions/admit', 'patient admitted to AVAILABLE bed'),
                _s(
                    NURSE,
                    'POST /bed/api/admissions/<admission_id>/transfer',
                    'transfer to another AVAILABLE bed',
                ),
                _s(
                    NURSE,
                    'POST /bed/api/admissions/<admission_id>/discharge',
                    'discharge, bed to CLEANING',
                ),
            ),
        ),
        # ===== API MODULE - Claims & Billing =====
        Template(
            key='API_CLAIMS_LIFECYCLE',
            family='financial',
            axes=('insurance_claim_status',),
            observed={'insurance_claim_status': ('DRAFT', 'SUBMITTED', 'APPROVED', 'SETTLED')},
            effect={'insurance_claim_status': 'claim driven to {value}'},
            rule=(
                'API claims lifecycle for external integrations. Submit creates '
                'DRAFT claim. Adjudicate sets approved amount. Settle moves to SETTLED. '
                'Payout records payment without GL entry (known gap).'
            ),
            steps=(
                _s(ACCOUNTANT, 'POST /api/claims', 'claim created DRAFT'),
                _s(ACCOUNTANT, 'POST /api/claims/<claim_id>/submit', 'submitted to insurer'),
                _s(ACCOUNTANT, 'POST /api/claims/<claim_id>/adjudicate', 'approved amount set'),
                _s(ACCOUNTANT, 'POST /api/claims/<claim_id>/settle', 'SETTLED, awaiting payout'),
                _s(
                    ACCOUNTANT,
                    'POST /api/claims/<claim_id>/payout',
                    'payout recorded, 1105 not relieved',
                ),
            ),
        ),
        Template(
            key='API_BILLING_INTEGRATION',
            family='financial',
            axes=(),
            observed={},
            effect={},
            rule=(
                'Stripe billing integration for SaaS subscriptions. Checkout creates '
                'session. Portal allows self-service. Webhook handles async events. '
                'Change-plan prorates. Cancel at period end by default.'
            ),
            steps=(
                _s(OWNER, 'POST /api/billing/checkout', 'checkout session created'),
                _s(OWNER, 'GET /api/billing/portal', 'customer portal session'),
                _s(SYSTEM, 'POST /api/billing/stripe/webhook', 'async event processed'),
                _s(OWNER, 'POST /api/billing/subscription/cancel', 'subscription cancelled'),
                _s(
                    OWNER,
                    'POST /api/billing/subscription/change-plan',
                    'plan changed with proration',
                ),
            ),
        ),
        Template(
            key='API_LAB_RADIOLOGY_CANCEL_AMEND',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=(
                'Cancel/amend endpoints for external integrations. Cancel only '
                'allowed in REQUESTED/IN_PROGRESS. Amend creates audit trail with '
                'original value preserved. Requires ordering provider or admin role.'
            ),
            steps=(
                _s(DOCTOR, 'POST /api/lab/requests/<request_id>/cancel', 'lab request cancelled'),
                _s(
                    LAB,
                    'POST /api/lab/results/<result_id>/amend',
                    'lab result amended, original kept',
                ),
                _s(
                    DOCTOR,
                    'POST /api/radiology/requests/<request_id>/cancel',
                    'radiology request cancelled',
                ),
                _s(
                    RADIOLOGY,
                    'POST /api/radiology/results/<result_id>/amend',
                    'radiology result amended',
                ),
            ),
        ),
        # ===== RECEPTION MODULE - Critical Write Routes =====
        Template(
            key='RECEPTION_APPOINTMENT_CHECKIN',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=(
                'Reception check-in confirms appointment and creates visit. '
                'Idempotent via appointment marker in visit notes.'
            ),
            steps=(
                _s(
                    RECEPTION,
                    'POST /reception/appointments/<appointment_id>/checkin',
                    'visit created from appointment',
                ),
                _s(
                    RECEPTION,
                    'POST /reception/appointments/<appointment_id>/confirm',
                    'appointment confirmed',
                ),
                _s(
                    RECEPTION,
                    'POST /reception/appointments/<appointment_id>/cancel',
                    'appointment cancelled',
                ),
            ),
        ),
        Template(
            key='RECEPTION_NO_SHOW_HANDLING',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=(
                'No-show marks appointment and releases slot for waitlist. '
                'Follow-up reminder triggered automatically.'
            ),
            steps=(
                _s(
                    RECEPTION,
                    'POST /reception/appointments/<appointment_id>/no-show',
                    'appointment marked no-show',
                ),
                _s(RECEPTION, 'GET /reception/no-shows', 'list no-show appointments'),
                _s(
                    RECEPTION,
                    'POST /reception/appointments/<appointment_id>/no-show',
                    'verify no-show recorded',
                ),
            ),
        ),
        Template(
            key='RECEPTION_QUEUE_MANAGEMENT',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=(
                'Queue management: add patient, call next, complete, skip, return. '
                'Queue gate enforces payment status.'
            ),
            steps=(
                _s(RECEPTION, 'POST /reception/queue/add-patient', 'patient added to queue'),
                _s(
                    RECEPTION,
                    'GET /reception/queue/call-next/<department_id>',
                    'next patient called',
                ),
                _s(
                    RECEPTION,
                    'POST /reception/queue/complete-treatment/<ticket_id>',
                    'treatment completed',
                ),
                _s(RECEPTION, 'POST /reception/queue/skip-patient/<ticket_id>', 'patient skipped'),
                _s(
                    RECEPTION,
                    'POST /reception/queue/return-to-queue/<ticket_id>',
                    'patient returned to queue',
                ),
            ),
        ),
        Template(
            key='RECEPTION_VISIT_LIFECYCLE',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=(
                'Visit lifecycle: create, add services, end, transfer, archive. '
                'Archive requires invoice reconciliation.'
            ),
            steps=(
                _s(RECEPTION, 'POST /reception/visits/create', 'visit created'),
                _s(
                    RECEPTION,
                    'POST /reception/visits/<visit_id>/add-service',
                    'service added to invoice',
                ),
                _s(RECEPTION, 'POST /reception/visits/<visit_id>/end', 'visit ended'),
                _s(RECEPTION, 'POST /reception/visits/<visit_id>/transfer', 'visit transferred'),
                _s(
                    RECEPTION,
                    'POST /reception/visits/<visit_id>/archive',
                    'visit archived after reconciliation',
                ),
            ),
        ),
        Template(
            key='RECEPTION_PATIENT_ADMIN',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=(
                'Patient administration: add, edit, delete, view. '
                'Allergies and problems managed via API.'
            ),
            steps=(
                _s(RECEPTION, 'POST /reception/add_patient', 'patient registered'),
                _s(RECEPTION, 'POST /reception/edit_patient/<patient_id>', 'patient updated'),
                _s(RECEPTION, 'POST /reception/delete_patient/<patient_id>', 'patient deleted'),
                _s(
                    RECEPTION,
                    'POST /reception/api/patients/<patient_id>/allergies/add',
                    'allergy added',
                ),
                _s(
                    RECEPTION,
                    'POST /reception/api/patients/<patient_id>/problems/add',
                    'problem added',
                ),
            ),
        ),
        Template(
            key='RECEPTION_PAYMENT_CASH_REGISTER',
            family='financial',
            axes=('payment_method',),
            observed={'payment_method': ('CASH', 'CARD', 'WIRE')},
            effect={'payment_method': 'payment collected via {value}'},
            rule=(
                'Cash register processes payments. POS charge for walk-ins. '
                'Daily close reconciles register.'
            ),
            steps=(
                _s(RECEPTION, 'POST /reception/cash-register', 'cash register opened'),
                _s(RECEPTION, 'POST /reception/pos/charge', 'POS charge processed'),
                _s(RECEPTION, 'POST /reception/daily-close', 'daily close reconciled'),
            ),
        ),
        Template(
            key='RECEPTION_EMERGENCY_DEBT_FORCE_ENTRY',
            family='financial',
            axes=(),
            observed={},
            effect={},
            rule=(
                'Emergency debt approval and force entry override queue gate. '
                'Requires manager approval with audit trail.'
            ),
            steps=(
                _s(
                    RECEPTION,
                    'POST /reception/queue/approve-emergency-debt/<ticket_id>',
                    'emergency debt approved',
                ),
                _s(
                    RECEPTION,
                    'POST /reception/queue/approve-force-entry/<ticket_id>',
                    'force entry approved',
                ),
                _s(
                    RECEPTION,
                    'POST /reception/queue/approve-emergency-debt/<ticket_id>',
                    'verify approval recorded',
                ),
            ),
        ),
        Template(
            key='RECEPTION_STAFF_SCHEDULE',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=('Staff schedule and absence management. Absence does not cancel appointments.'),
            steps=(
                _s(RECEPTION, 'POST /reception/staff/absence', 'absence recorded'),
                _s(RECEPTION, 'POST /reception/staff/schedule', 'schedule updated'),
                _s(RECEPTION, 'GET /reception/staff/schedule', 'verify schedule updated'),
            ),
        ),
        Template(
            key='RECEPTION_SURVEY_FEEDBACK',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=('Patient survey feedback collected post-visit.'),
            steps=(
                _s(RECEPTION, 'POST /reception/survey/<token>', 'survey submitted'),
                _s(RECEPTION, 'GET /reception/survey/<token>', 'survey details retrieved'),
                _s(RECEPTION, 'POST /reception/survey/<token>', 'survey response recorded'),
            ),
        ),
        # ===== LAB MODULE - Critical Write Routes =====
        Template(
            key='LAB_WORKLIST_MANAGEMENT',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=(
                'Lab worklist: claim requests, complete with results. '
                'Auto-calculate derived values on finalize.'
            ),
            steps=(
                _s(LAB, 'POST /lab/worklist/claim/<request_id>', 'request claimed'),
                _s(
                    LAB,
                    'POST /lab/worklist/complete/<request_id>',
                    'results entered, derived values calculated',
                ),
                _s(LAB, 'POST /lab/worklist/request/<request_id>', 'status advanced'),
            ),
        ),
        Template(
            key='LAB_CATALOG_MANAGEMENT',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=('Lab test catalog and panels management. Test catalog CRUD, panel CRUD.'),
            steps=(
                _s(LAB, 'POST /lab/test-catalog/add', 'test added to catalog'),
                _s(LAB, 'POST /lab/test-catalog/<id>/edit', 'test updated'),
                _s(LAB, 'POST /lab/test-catalog/<id>/delete', 'test deleted'),
                _s(LAB, 'POST /lab/test-panels/add', 'panel created'),
                _s(LAB, 'POST /lab/test-panels/<id>/edit', 'panel updated'),
                _s(LAB, 'POST /lab/test-panels/<id>/delete', 'panel deleted'),
            ),
        ),
        Template(
            key='LAB_REAGENTS_QUALITY',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=(
                'Reagents and quality control management. '
                'LIS confirm and preview for external integration.'
            ),
            steps=(
                _s(LAB, 'POST /lab/reagents/add', 'reagent added'),
                _s(LAB, 'POST /lab/reagents/<reagent_id>/edit', 'reagent updated'),
                _s(LAB, 'POST /lab/lis/confirm', 'LIS order confirmed'),
                _s(LAB, 'POST /lab/lis/preview', 'LIS preview'),
                _s(LAB, 'POST /lab/quality-control', 'QC recorded'),
            ),
        ),
        Template(
            key='LAB_BARCODE_PRINT_SCAN',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=('Barcode print and scan for sample tracking.'),
            steps=(
                _s(LAB, 'POST /lab/barcode/print/<request_id>', 'barcode printed'),
                _s(LAB, 'POST /lab/barcode/scan/<barcode>', 'sample scanned'),
                _s(LAB, 'GET /lab/barcode/print/<request_id>', 'verify barcode printed'),
            ),
        ),
        Template(
            key='LAB_RESULT_TEMPLATES_DERIVED',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=(
                'Result templates with derived values. '
                'Auto-calculate and manual calculate triggers.'
            ),
            steps=(
                _s(LAB, 'POST /lab/api/result-templates', 'template created'),
                _s(LAB, 'POST /lab/api/derived-values', 'derived values computed'),
                _s(LAB, 'POST /lab/auto-calculate', 'auto-calculate on finalize'),
                _s(LAB, 'POST /lab/calculate', 'manual calculate'),
            ),
        ),
        # ===== MEDICATION MODULE - Critical Write Routes =====
        Template(
            key='MEDICATION_PRESCRIPTION_DISPENSE',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=(
                'Prescription dispense with interaction check. '
                'Stock moves under row lock. Refill workflow.'
            ),
            steps=(
                _s(DOCTOR, 'POST /medication/prescriptions', 'prescription created'),
                _s(
                    PHARMACY,
                    'POST /medication/prescriptions/dispense/<prescription_id>',
                    'dispensed with interaction check',
                ),
                _s(
                    DOCTOR,
                    'POST /medication/prescriptions/<prescription_id>/refill',
                    'refill requested',
                ),
                _s(
                    PHARMACY,
                    'POST /medication/prescriptions/<prescription_id>/refill',
                    'refill approved',
                ),
            ),
        ),
        Template(
            key='MEDICATION_CATALOG_INTERACTIONS',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=(
                'Medication catalog: add, edit, suppliers. '
                'Drug interactions managed. POS sell and charge.'
            ),
            steps=(
                _s(PHARMACY, 'POST /medication/add', 'medication added'),
                _s(PHARMACY, 'POST /medication/edit/<medication_id>', 'medication updated'),
                _s(PHARMACY, 'POST /medication/interactions', 'interaction added'),
                _s(
                    PHARMACY,
                    'POST /medication/interactions/<interaction_id>/toggle',
                    'interaction toggled',
                ),
                _s(PHARMACY, 'POST /medication/pos/sell', 'POS sale'),
                _s(PHARMACY, 'POST /medication/pos/charge', 'POS charge'),
            ),
        ),
        Template(
            key='MEDICATION_PURCHASES_SUPPLY',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=(
                'Purchases and supply requests workflow. '
                'Suppliers CRUD. Supply requests: create, approve, fulfill.'
            ),
            steps=(
                _s(PHARMACY, 'POST /medication/purchases/add', 'purchase recorded'),
                _s(PHARMACY, 'POST /medication/suppliers/add', 'supplier added'),
                _s(PHARMACY, 'POST /medication/suppliers/<supplier_id>/edit', 'supplier updated'),
                _s(PHARMACY, 'POST /medication/suppliers/<supplier_id>/delete', 'supplier deleted'),
                _s(PHARMACY, 'POST /medication/supply-requests/create', 'supply request created'),
                _s(
                    PHARMACY,
                    'POST /medication/supply-requests/<request_id>/approve',
                    'supply request approved',
                ),
                _s(
                    PHARMACY,
                    'POST /medication/supply-requests/<request_id>/fulfill',
                    'supply request fulfilled',
                ),
            ),
        ),
        Template(
            key='MEDICATION_EXTERNAL_IMPORT',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=('External drug import and search. Stock alerts monitored.'),
            steps=(
                _s(PHARMACY, 'POST /medication/api/external-drug-import', 'external drug imported'),
                _s(PHARMACY, 'POST /medication/api/stock/alerts', 'stock alerts checked'),
                _s(PHARMACY, 'GET /medication/api/stock/alerts', 'verify stock alerts retrieved'),
            ),
        ),
        # ===== MANAGER MODULE - Critical Write Routes =====
        Template(
            key='MANAGER_APPROVALS_WORKFLOW',
            family='financial',
            axes=(),
            observed={},
            effect={},
            rule=(
                'Custom service and force payment approvals. '
                'Manager approves/rejects with audit trail.'
            ),
            steps=(
                _s(
                    MANAGER,
                    'POST /manager/approve-custom-service/<service_id>',
                    'custom service approved',
                ),
                _s(
                    MANAGER,
                    'POST /manager/reject-custom-service/<service_id>',
                    'custom service rejected',
                ),
                _s(
                    MANAGER,
                    'POST /manager/approve-force-payment/<visit_id>',
                    'force payment approved',
                ),
                _s(
                    MANAGER,
                    'POST /manager/reject-force-payment/<visit_id>',
                    'force payment rejected',
                ),
            ),
        ),
        Template(
            key='MANAGER_PRICING_EXCHANGE_RATES',
            family='financial',
            axes=(),
            observed={},
            effect={},
            rule=(
                'Pricing management and exchange rates. '
                'Seed pricing from catalog. Fetch rates from API.'
            ),
            steps=(
                _s(MANAGER, 'POST /manager/pricing', 'pricing updated'),
                _s(MANAGER, 'POST /manager/seed-pricing', 'pricing seeded from catalog'),
                _s(MANAGER, 'POST /manager/exchange-rates', 'exchange rate updated'),
                _s(MANAGER, 'POST /manager/exchange-rates/fetch-api', 'rates fetched from API'),
                _s(
                    MANAGER, 'POST /manager/exchange-rates/deactivate/<rate_id>', 'rate deactivated'
                ),
            ),
        ),
        Template(
            key='MANAGER_STAFF_SCHEDULE_CAPACITY',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=(
                'Staff schedule and capacity management. '
                'Absence recorded. Unit control for bed management.'
            ),
            steps=(
                _s(MANAGER, 'POST /manager/staff/absence', 'staff absence recorded'),
                _s(MANAGER, 'POST /manager/staff/schedule', 'schedule updated'),
                _s(MANAGER, 'POST /manager/unit-control', 'unit control updated'),
                _s(MANAGER, 'POST /manager/staff/capacity', 'capacity updated'),
            ),
        ),
        Template(
            key='MANAGER_SETTINGS_WHAT_IF',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=('Manager settings and what-if modelling. Test SMS sends. Units toggle.'),
            steps=(
                _s(MANAGER, 'POST /manager/settings', 'settings updated'),
                _s(MANAGER, 'POST /manager/settings/test-sms', 'test SMS sent'),
                _s(MANAGER, 'POST /manager/api/units/toggle', 'unit toggled'),
                _s(MANAGER, 'POST /manager/api/what-if', 'what-if scenario run'),
            ),
        ),
        Template(
            key='MANAGER_USER_DEPT_MANAGEMENT',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=('User management and department management.'),
            steps=(
                _s(MANAGER, 'POST /manager/user-management', 'user managed'),
                _s(MANAGER, 'POST /manager/departments', 'department managed'),
                _s(MANAGER, 'GET /manager/user-management', 'verify user managed'),
            ),
        ),
        Template(
            key='MANAGER_BUDGET_FINANCIAL_REPORTS',
            family='financial',
            axes=(),
            observed={},
            effect={},
            rule=(
                'Budget dashboard and financial reports. Settlements export. Monthly comparison.'
            ),
            steps=(
                _s(MANAGER, 'POST /manager/budget', 'budget updated'),
                _s(MANAGER, 'POST /manager/financial-reports', 'financial report generated'),
                _s(MANAGER, 'POST /manager/settlements/export', 'settlements exported'),
                _s(MANAGER, 'POST /manager/monthly-comparison', 'monthly comparison generated'),
            ),
        ),
        # ===== EMERGENCY MODULE - Critical Write Routes =====
        Template(
            key='EMERGENCY_CASE_TREATMENT',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=(
                'Emergency case lifecycle: create, triage, treat, complete. '
                'EMS intake creates patient without visit. Lab/radiology orders without hub-and-spoke.'
            ),
            steps=(
                _s(EMERGENCY, 'POST /emergency/cases/create', 'emergency case created'),
                _s(EMERGENCY, 'POST /emergency/triage/<emergency_id>', 'triage completed'),
                _s(
                    EMERGENCY, 'POST /emergency/start-treatment/<emergency_id>', 'treatment started'
                ),
                _s(EMERGENCY, 'POST /emergency/end-treatment/<emergency_id>', 'treatment ended'),
                _s(
                    EMERGENCY,
                    'POST /emergency/emergency-visits/<visit_id>/complete',
                    'emergency visit completed',
                ),
            ),
        ),
        Template(
            key='EMERGENCY_ORDERS_PRESCRIPTIONS',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=(
                'Emergency lab/radiology orders and prescriptions. '
                'No hub-and-spoke re-queue. Case convert and resolve.'
            ),
            steps=(
                _s(EMERGENCY, 'POST /emergency/lab-request/<emergency_id>', 'ER lab order'),
                _s(
                    EMERGENCY,
                    'POST /emergency/radiology-request/<emergency_id>',
                    'ER radiology order',
                ),
                _s(EMERGENCY, 'POST /emergency/prescription/<emergency_id>', 'ER prescription'),
                _s(EMERGENCY, 'POST /emergency/cases/<id>/convert', 'case converted to inpatient'),
                _s(EMERGENCY, 'POST /emergency/cases/<id>/resolve', 'case resolved'),
            ),
        ),
        Template(
            key='EMERGENCY_EMS_INTAKE',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=(
                'EMS intake creates patient and case without visit or queue ticket. '
                'API endpoint for external EMS systems.'
            ),
            steps=(
                _s(EMERGENCY, 'POST /emergency/api/ems/intake', 'EMS intake processed'),
                _s(EMERGENCY, 'POST /emergency/cases/create', 'emergency case created from intake'),
                _s(EMERGENCY, 'GET /emergency/cases', 'verify case created'),
            ),
        ),
        # ===== DOCTOR MODULE - Critical Write Routes =====
        Template(
            key='DOCTOR_PRESCRIPTION_NOTES',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=(
                'Doctor prescriptions with safety checks. '
                'Notes and templates. Visit summary save. Dental chart.'
            ),
            steps=(
                _s(
                    DOCTOR,
                    'POST /doctor/prescription/<visit_id>',
                    'prescription created with safety check',
                ),
                _s(DOCTOR, 'POST /doctor/save-visit-summary/<visit_id>', 'visit summary saved'),
                _s(DOCTOR, 'POST /doctor/dental-chart/save', 'dental chart saved'),
                _s(DOCTOR, 'POST /doctor/notes/<visit_id>', 'clinical note saved'),
                _s(DOCTOR, 'POST /doctor/api/note-templates', 'note template created'),
                _s(
                    DOCTOR,
                    'POST /doctor/api/note-templates/<template_id>/delete',
                    'note template deleted',
                ),
            ),
        ),
        Template(
            key='DOCTOR_TREATMENT_LIFECYCLE',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=(
                'Doctor treatment lifecycle: start, end, call patient. '
                'Lab/radiology requests via hub-and-spoke.'
            ),
            steps=(
                _s(DOCTOR, 'POST /doctor/start-treatment/<visit_id>', 'treatment started'),
                _s(DOCTOR, 'POST /doctor/end-treatment/<visit_id>', 'treatment ended'),
                _s(DOCTOR, 'POST /doctor/call-patient/<visit_id>', 'patient called'),
                _s(
                    DOCTOR, 'POST /doctor/lab-request/<visit_id>', 'lab requested via hub-and-spoke'
                ),
                _s(
                    DOCTOR,
                    'POST /doctor/radiology-request/<visit_id>',
                    'radiology requested via hub-and-spoke',
                ),
            ),
        ),
        Template(
            key='DOCTOR_DIAGNOSIS_PRESCRIPTION_HISTORY',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=('Diagnosis management and prescription history.'),
            steps=(
                _s(DOCTOR, 'POST /doctor/diagnosis/<visit_id>', 'diagnosis recorded'),
                _s(DOCTOR, 'POST /doctor/prescriptions', 'prescriptions listed'),
                _s(
                    DOCTOR,
                    'POST /doctor/prescriptions-history/<patient_id>',
                    'prescription history',
                ),
            ),
        ),
        # ===== BOOKING MODULE - Critical Write Routes =====
        Template(
            key='BOOKING_PAYMENT_CANCEL',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=('Booking payment and cancellation. Telemedicine booking. Register new patient.'),
            steps=(
                _s(RECEPTION, 'POST /booking/payment/<booking_id>', 'booking payment processed'),
                _s(RECEPTION, 'POST /booking/cancel/<booking_id>', 'booking cancelled'),
                _s(RECEPTION, 'POST /booking/register', 'patient registered via booking'),
                _s(
                    RECEPTION,
                    'POST /booking/telemedicine/<booking_id>',
                    'telemedicine booking created',
                ),
            ),
        ),
        # ===== RADIOLOGY MODULE - Critical Write Routes =====
        Template(
            key='RADIOLOGY_WORKLIST_REPORTS',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=(
                'Radiology worklist: claim, complete. Reports with second review. '
                'AI assist. Print reports. Tests and macros.'
            ),
            steps=(
                _s(RADIOLOGY, 'POST /radiology/worklist/claim/<request_id>', 'request claimed'),
                _s(RADIOLOGY, 'POST /radiology/worklist/complete/<request_id>', 'report completed'),
                _s(
                    RADIOLOGY,
                    'POST /radiology/results/<result_id>/second-review',
                    'second review completed',
                ),
                _s(RADIOLOGY, 'POST /radiology/api/ai-assist', 'AI assist requested'),
                _s(RADIOLOGY, 'POST /radiology/tests/add', 'test added'),
                _s(RADIOLOGY, 'POST /radiology/api/report-macros', 'macro created'),
                _s(
                    RADIOLOGY,
                    'POST /radiology/api/report-macros/<macro_id>/delete',
                    'macro deleted',
                ),
                _s(RADIOLOGY, 'POST /radiology/api/report-templates', 'template created'),
                _s(
                    RADIOLOGY,
                    'POST /radiology/api/report-templates/<template_id>/delete',
                    'template deleted',
                ),
            ),
        ),
        # ===== COMPLIANCE MODULE - Critical Write Routes =====
        Template(
            key='COMPLIANCE_CONSENT_AUDIT',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=(
                'Consent management and audit log retention. '
                'Breach check. Data export with patient data.'
            ),
            steps=(
                _s(MANAGER, 'POST /compliance/consent-management', 'consent recorded'),
                _s(MANAGER, 'POST /compliance/verify-consent', 'consent verified'),
                _s(MANAGER, 'POST /compliance/audit-log-retention', 'retention policy applied'),
                _s(MANAGER, 'POST /compliance/breach-check', 'breach checked'),
                _s(MANAGER, 'POST /compliance/data-export', 'data export triggered'),
            ),
        ),
        # ===== ACCOUNTANT MODULE - Critical Write Routes =====
        Template(
            key='ACCOUNTANT_PERIOD_REFUND',
            family='financial',
            axes=(),
            observed={},
            effect={},
            rule=(
                'Accountant period close and refund workflow. '
                'Refund approve/execute/reject. Payment documentation.'
            ),
            steps=(
                _s(ACCOUNTANT, 'POST /accountant/periods/close', 'period closed'),
                _s(ACCOUNTANT, 'POST /accountant/refunds/<refund_id>/approve', 'refund approved'),
                _s(ACCOUNTANT, 'POST /accountant/refunds/<refund_id>/execute', 'refund executed'),
                _s(ACCOUNTANT, 'POST /accountant/refunds/<refund_id>/reject', 'refund rejected'),
                _s(
                    ACCOUNTANT,
                    'POST /accountant/payment-documentation/<payment_id>',
                    'payment documented',
                ),
            ),
        ),
        # ===== BED MODULE - Critical Write Routes =====
        Template(
            key='BED_ADMISSIONS_FULL',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=('Bed admissions: admit, transfer, discharge. Bed status transitions enforced.'),
            steps=(
                _s(NURSE, 'POST /bed/api/admissions/admit', 'patient admitted'),
                _s(
                    NURSE, 'POST /bed/api/admissions/<admission_id>/transfer', 'patient transferred'
                ),
                _s(
                    NURSE, 'POST /bed/api/admissions/<admission_id>/discharge', 'patient discharged'
                ),
            ),
        ),
        # ===== NURSE MODULE - Critical Write Routes =====
        Template(
            key='NURSE_VITALS_TASKS',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=(
                'Nurse vital signs recording with validation. '
                'Medication administration. Task create and status updates.'
            ),
            steps=(
                _s(NURSE, 'POST /nurse/record-vital-signs/<patient_id>', 'vitals recorded'),
                _s(
                    NURSE,
                    'POST /nurse/administer-medication/<prescription_item_id>',
                    'medication administered',
                ),
                _s(NURSE, 'POST /nurse/tasks/create', 'task created'),
                _s(NURSE, 'POST /nurse/tasks/<task_id>/status', 'task status updated'),
            ),
        ),
        Template(
            key='NURSE_PROTOCOLS_API',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=('Nurse protocols API for clinical guidelines.'),
            steps=(
                _s(NURSE, 'POST /nurse/api/protocols', 'protocol accessed'),
                _s(NURSE, 'GET /nurse/api/protocols', 'protocol list retrieved'),
                _s(NURSE, 'POST /nurse/api/protocols', 'protocol search performed'),
            ),
        ),
        # ===== NURSING ASSESSMENT - Critical Write Routes =====
        Template(
            key='NURSING_ASSESSMENT_NEW',
            family='clinical',
            axes=(),
            observed={},
            effect={},
            rule=('Nursing assessment creation for patient.'),
            steps=(
                _s(NURSE, 'POST /nursing-assessment/new/<patient_id>', 'assessment created'),
                _s(
                    NURSE,
                    'GET /nursing-assessment/new/<patient_id>',
                    'assessment details retrieved',
                ),
                _s(NURSE, 'POST /nursing-assessment/new/<patient_id>', 'assessment updated'),
            ),
        ),
        # ===== API MODULE - Critical Write Routes =====
        Template(
            key='API_SAAS_REGISTER_PREFERENCES',
            family='platform',
            axes=(),
            observed={},
            effect={},
            rule=('SaaS registration and user preferences API.'),
            steps=(
                _s(SYSTEM, 'POST /api/saas/register', 'tenant registered'),
                _s(SYSTEM, 'POST /api/user/preferences', 'preferences updated'),
                _s(SYSTEM, 'GET /api/user/preferences', 'verify preferences retrieved'),
            ),
        ),
    )


#: Every template, extended at import time by the family modules.
TEMPLATES: list[Template] = list(_base_templates())


def all_problems() -> list[str]:
    out: list[str] = []
    for t in TEMPLATES:
        out.extend(t.validate())
    return out


if __name__ == '__main__':
    problems = all_problems()
    print(f'{len(TEMPLATES)} templates, {sum(len(t.steps) for t in TEMPLATES)} steps')
    print(f'routes in inventory: {len(EXACT)} exact, {len(SHAPES)} shapes')
    if problems:
        print(f'\nPROBLEMS ({len(problems)}):')
        for p in problems:
            print(' ', p)
    else:
        print('\nevery template route and every observed enum member verified')
    axes = sorted({a for t in TEMPLATES for a in t.axes})
    print(f'\naxes in use: {axes}')
