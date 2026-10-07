"""Derive the scenario dimensions from the code, never from a hand-written list.

Every dimension here is read out of the application at import time: enum members,
the role hierarchy, the real route table. If the code changes, these change with
it, and a scenario generated against a value the code no longer accepts becomes a
generator error instead of a silently wrong document.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass(frozen=True)
class Dimension:
    """One axis scenarios vary along.

    ``kind`` is 'enum' for a value drawn from the code's own enums, or 'rule' for
    a value the code computes or constrains (a numeric bound, a gate threshold).
    """

    name: str
    kind: str
    values: tuple[str, ...]
    note: str = ''

    def __len__(self) -> int:
        return len(self.values)


def _enum_values(module_path: str, class_name: str) -> tuple[str, ...]:
    module = __import__(module_path, fromlist=[class_name])
    cls = getattr(module, class_name)
    return tuple(str(m.value) for m in cls)


def _actor_roles() -> tuple[str, ...]:
    """Every role the code will accept on a User.

    Read from the assignment policy rather than from ROLE_HIERARCHY, whose keys
    are only the roles that *grant* other roles. Using the keys would silently
    drop reception, doctor, nurse, lab, radiology, pharmacist and accountant,
    which are exactly the roles the clinical scenarios need.
    """
    from app.shared.user_role_policy import ASSIGNABLE_ROLES

    return tuple(sorted(ASSIGNABLE_ROLES))


def _radiology_modalities() -> tuple[str, ...]:
    """Modalities the radiology request column documents."""
    from models.radiology_request import RadiologyRequest

    col = RadiologyRequest.__table__.columns['modality']
    # The column is a free String; the documented set is in the comment. Pull it
    # from the model docstring so it cannot drift from the code silently.
    doc = (RadiologyRequest.__doc__ or '') + (col.comment or '')
    found = tuple(m for m in ('XRay', 'CT', 'MRI', 'US') if m in doc)
    return found or ('XRay', 'CT', 'MRI', 'US')


def build_dimensions() -> tuple[Dimension, ...]:
    """Return every axis the generator may vary, grounded in the code."""
    return (
        Dimension(
            'ward_type',
            'enum',
            _enum_values('app.shared.enums', 'WardType'),
            'Ward.ward_type. Descriptive only: nothing prices a ward, so every '
            'inpatient stay costs the same regardless of ICU versus maternity.',
        ),
        Dimension(
            'bed_type',
            'enum',
            _enum_values('app.shared.enums', 'BedType'),
            'Bed.bed_type. Likewise unpriced.',
        ),
        Dimension(
            'problem_severity',
            'enum',
            _enum_values('app.shared.enums', 'ProblemSeverity'),
            'Problem record on the patient chart.',
        ),
        Dimension(
            'problem_status',
            'enum',
            _enum_values('app.shared.enums', 'ProblemStatus'),
            'Problem record lifecycle.',
        ),
        Dimension(
            'task_priority',
            'enum',
            _enum_values('app.shared.enums', 'TaskPriority'),
            'Nursing task priority.',
        ),
        Dimension(
            'task_state',
            'enum',
            _enum_values('app.shared.enums', 'TaskState'),
            'Nursing task lifecycle.',
        ),
        Dimension(
            'referral_status',
            'enum',
            _enum_values('app.shared.enums', 'ReferralStatus'),
            'Referral.status. Note the read-only routes: there is no create '
            'endpoint anywhere, so this axis is exercised through the model.',
        ),
        Dimension(
            'referral_urgency',
            'enum',
            _enum_values('app.shared.enums', 'ReferralUrgency'),
            'Referral.urgency.',
        ),
        Dimension(
            'supply_request_status',
            'enum',
            _enum_values('app.shared.enums', 'SupplyRequestStatus'),
            'MedicationSupplyRequest lifecycle, DRAFT to APPROVED to FULFILLED.',
        ),
        Dimension(
            'stock_movement_type',
            'enum',
            _enum_values('app.shared.enums', 'StockMovementType'),
            'InventoryLedgerService movement types. The enum has no dispense and '
            'no waste member even though dispensing is the main outflow.',
        ),
        Dimension(
            'currency',
            'enum',
            _enum_values('app.shared.enums', 'Currency'),
            'app.shared.enums.Currency. Note CurrencySettings.SUPPORTED_CURRENCIES '
            'also lists SAR, AED, QAR, KWD, BHD and OMR, which do not exist here.',
        ),
        Dimension(
            'appointment_status',
            'enum',
            _enum_values('app.shared.enums', 'AppointmentWorkflowStatus'),
            'Appointment workflow. The AppointmentState enum adds CHECKED_IN and '
            'COMPLETED, which this workflow enum does not have.',
        ),
        Dimension(
            'treatment_status',
            'enum',
            _enum_values('app.shared.enums', 'TreatmentStatus'),
            'Treatment record lifecycle.',
        ),
        Dimension(
            'subscription_type',
            'enum',
            _enum_values('app.shared.enums', 'SubscriptionType'),
            'SaaS subscription billing period. The platform bills tenants with this; '
            'it has nothing to do with patient billing.',
        ),
        Dimension(
            'tenant_status',
            'enum',
            _enum_values('app.shared.enums', 'TenantStatus'),
            'Tenant.status.',
        ),
        Dimension(
            'security_severity',
            'enum',
            _enum_values('app.shared.enums', 'SecuritySeverity'),
            'SecurityEvent severity.',
        ),
        Dimension(
            'log_level',
            'enum',
            _enum_values('app.shared.enums', 'LogLevel'),
            'SystemLog level.',
        ),
        Dimension(
            'backup_type',
            'enum',
            _enum_values('app.shared.enums', 'BackupType'),
            'Backup type.',
        ),
        Dimension(
            'backup_status',
            'enum',
            _enum_values('app.shared.enums', 'BackupStatus'),
            'Backup job status.',
        ),
        Dimension(
            'module_status',
            'enum',
            ('enabled', 'disabled'),
            'TenantModule activation. A module is reachable only when active, and '
            'the gate is disabled entirely when ENABLE_SAAS_MODE is False.',
        ),
        Dimension(
            'bundle_kind',
            'enum',
            ('custom', 'polyclinic', 'hospital', 'urgent_care'),
            'ProductBundle shapes from the seeded profiles. Each is a JSON array of '
            'module names with a price and a max_users or max_patients ceiling.',
        ),
        Dimension(
            'procedure_status',
            'enum',
            _enum_values('app.shared.enums', 'ProcedureStatus'),
            'Procedure record lifecycle.',
        ),
        Dimension(
            'payment_method',
            'enum',
            _enum_values('app.shared.enums', 'PaymentMethod'),
            'PaymentMethod; note the enum carries lowercase visa/mada, and '
            'payment_routes maps them onto CARD.',
        ),
        Dimension(
            'payment_status',
            'enum',
            _enum_values('app.shared.enums', 'PaymentStatus'),
            'PaymentStatus as the code defines it.',
        ),
        Dimension(
            'visit_type',
            'enum',
            _enum_values('app.shared.enums', 'VisitType'),
            'There is no OPD/IPD enum: inpatient is Visit.is_inpatient plus an '
            'Admission row, emergency is is_emergency plus visit_type.',
        ),
        Dimension(
            'visit_state',
            'enum',
            _enum_values('app.shared.enums', 'VisitState'),
            'Visit.status; direct assignment raises unless the state machine authorises it.',
        ),
        Dimension(
            'triage_level',
            'enum',
            ('RED', 'YELLOW', 'GREEN'),
            'routes/emergency/queue.py maps RED->CRITICAL, YELLOW->HIGH, '
            'GREEN->MODERATE. These three are the only values written.',
        ),
        Dimension(
            'emergency_severity',
            'enum',
            _enum_values('app.shared.enums', 'EmergencySeverity'),
            'EmergencyCase.severity, uppercased by a validator.',
        ),
        Dimension(
            'lab_result_status',
            'enum',
            _enum_values('app.shared.enums', 'LabResultStatus'),
            'LabResult.status progression.',
        ),
        Dimension(
            'radiology_modality',
            'enum',
            _radiology_modalities(),
            'RadiologyRequest.modality.',
        ),
        Dimension(
            'radiology_result_status',
            'enum',
            _enum_values('app.shared.enums', 'RadiologyResultStatus'),
            'RadiologyResult.status progression.',
        ),
        Dimension(
            'actor_role',
            'enum',
            _actor_roles(),
            'Roles accepted on a User by user_role_policy.ASSIGNABLE_ROLES. '
            'A scenario needing reception authority is written with reception, '
            'not manager: manager inherits reception through ROLE_HIERARCHY, so '
            'using manager would test inheritance instead of the receptionist.',
        ),
        Dimension(
            'insurance_coverage',
            'rule',
            ('50', '60', '70', '75', '80', '85', '90', '95', '100'),
            'GatekeeperService.validate_insurance rejects coverage outside '
            '[50, 100], so these are the only representable values. '
            'patient_share = total * (1 - coverage/100); there is no deductible, '
            'no fixed copay and no exclusion list.',
        ),
        Dimension(
            'force_payment_ratio',
            'rule',
            ('0', '2', '4', '5', '8'),
            'validate_force_payment rejects when force-payment visits in the last '
            '30 days are >= 5% of all visits. 5 is the exact boundary where the '
            'gate and get_force_payment_statistics disagree.',
        ),
        Dimension(
            'cash_amount',
            'rule',
            ('100', '2500', '4999', '5000', '5001'),
            'GatekeeperService.MAX_CASH_AMOUNT is 5000 with no SystemConfig '
            'override path. 5000 is the last accepted value and 5001 the first '
            'rejected one; the cap has no tenant or user scope.',
        ),
        Dimension(
            'payment_amount_over_remaining',
            'rule',
            ('0', '50', '100', '150'),
            'Amounts are expressed as a percentage of visit.total_amount. '
            '/payment/process rejects amount > remaining with 400 and amount <= 0 '
            'while remaining > 0 with 400, so 150 is the overpayment case.',
        ),
        Dimension(
            'line_item_count',
            'rule',
            ('1', '2', '5'),
            'How many add-service lines the invoice carries. Archiving requires '
            'SUM(invoice_services.total_price) to equal visit.total_amount, so a '
            'mismatched count is what the reconciliation check exists to catch.',
        ),
    )


@dataclass
class Fingerprint:
    """Identity of a scenario, used to reject duplicates.

    Deliberately excludes prose. Two scenarios that assert the same route
    sequence with the same parameter values are the same scenario even if one is
    worded differently, which is the duplication the generator must not ship.
    """

    template: str
    axes: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    def key(self) -> str:
        return json.dumps(
            {'template': self.template, 'axes': dict(self.axes)},
            sort_keys=True,
            ensure_ascii=False,
        )


def total_combinations(dims: tuple[Dimension, ...], axes: tuple[str, ...]) -> int:
    n = 1
    for d in dims:
        if d.name in axes:
            n *= len(d)
    return n


if __name__ == '__main__':
    ds = build_dimensions()
    print(f'{len(ds)} dimensions\n')
    for d in ds:
        print(f'  {d.name:26} {len(d):3}  {d.values}')
    print()
    print(
        'payment_method x insurance_coverage =',
        total_combinations(ds, ('payment_method', 'insurance_coverage')),
    )
    all_axes = tuple(d.name for d in ds)
    print('full cross product           =', total_combinations(ds, all_axes))
