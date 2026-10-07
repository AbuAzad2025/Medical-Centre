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


EXACT, SHAPES = _load_routes()
VERBS = r'(?:GET|POST|PUT|DELETE|PATCH)'
API_LINE = re.compile(rf'^(?:(?P<verb>{VERBS})(?:\|{VERBS})*)?\s+(?P<path>\S+)$')


@dataclass(frozen=True)
class Step:
    department: str
    api: str
    assertion: str


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

    def __post_init__(self):
        from dimensions import build_dimensions

        by_name = {d.name: d for d in build_dimensions()}
        object.__setattr__(
            self,
            'axis_values',
            {name: by_name[name].values for name in self.axes if name in by_name},
        )

    def validate(self) -> list[str]:
        """Every api, and every observed enum member, must match the real code."""
        problems = []
        for step in self.steps:
            m = API_LINE.match(step.api)
            if not m:
                problems.append(f'{self.key}: unparseable api {step.api!r}')
                continue
            shape = re.sub(r'<[^>]*>|\{[^}]*\}', '{}', m.group('path'))
            if shape not in SHAPES:
                problems.append(f'{self.key}: no route {m.group("path")}')

        for axis in self.axes:
            if axis not in self.observed:
                problems.append(f'{self.key}: declares axis {axis} but observes nothing on it')
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
                    'POST /api/lab/results/<id>/amend',
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
                    'POST /radiology/results/<id>/second-review',
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
                    'POST /bed/api/admissions/<id>/transfer',
                    'BedTransfer recorded with no approval step',
                ),
                _s(
                    NURSE,
                    'POST /bed/api/admissions/<id>/discharge',
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
                    'POST /reception/visits/<id>/add-service',
                    'price taken from the catalog, never the client',
                ),
                _s(
                    RECEPTION,
                    'POST /reception/visits/<id>/archive',
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
                    'POST /payment/payments/<id>/refund',
                    'request created; over-refund blocked',
                ),
                _s(ACCOUNTANT, 'POST /accountant/refunds/<id>/approve', 'TypeError, HTTP 500'),
                _s(ACCOUNTANT, 'POST /payment/refund-requests/<id>/approve', 'the working path'),
                _s(
                    ACCOUNTANT,
                    'POST /payment/refund-requests/<id>/execute',
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
                    'POST /reception/appointments/<id>/checkin',
                    'Visit created OPEN/PENDING, appointment CONFIRMED',
                ),
                _s(
                    RECEPTION,
                    'POST /reception/appointments/<id>/checkin',
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
                    'POST /reception/api/patients/<id>/problems/add',
                    'problem recorded with severity and status',
                ),
                _s(
                    RECEPTION,
                    'POST /reception/api/patients/<id>/allergies/add',
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
                    NURSE, 'POST /nurse/tasks/<id>/status', 'task advanced through its state ladder'
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
                _s(NURSE, 'GET /bed/room/<id>', 'room and its beds'),
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
                    'POST /reception/visits/<id>/add-service',
                    'lines appended to the invoice',
                ),
                _s(
                    RECEPTION,
                    'POST /payment/process/<visit_id>',
                    'overpayment beyond remaining refused 400',
                ),
                _s(
                    RECEPTION,
                    'POST /reception/visits/<id>/archive',
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
                    'POST /emergency/emergency-treatment/<emergency_id>',
                    'treatment started',
                ),
                _s(
                    EMERGENCY,
                    'POST /emergency/lab-request/<visit_id>',
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
                    'POST /reception/visits/<id>/send-to-accounting',
                    'invoice created; claims require one',
                ),
                _s(ACCOUNTANT, 'POST /api/claims', 'claim DRAFT, but share amounts are inverted'),
                _s(ACCOUNTANT, 'POST /api/claims/<id>/submit', 'SUBMITTED'),
                _s(
                    ACCOUNTANT,
                    'POST /api/claims/<id>/adjudicate',
                    'approved_amount typed in, no fee schedule',
                ),
                _s(ACCOUNTANT, 'POST /api/claims/<id>/settle', 'SETTLED'),
                _s(
                    ACCOUNTANT,
                    'POST /api/claims/<id>/payout',
                    'payout recorded with no GL entry, so 1105 stays open',
                ),
            ),
            expected_status='PAID',
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
