"""Clinical templates for routes the first matrix did not reach.

Each one here exists because a specific group of state-changing endpoints had no
template at all. The route inventory is the input: the generator reports what is
uncovered, and these are the clusters it named.

Kept separate from templates.py on purpose. templates.py holds the journeys whose
axes are financial or lifecycle enums; these vary over the workflow vocabulary of
one department, which is a different shape of scenario and a different reviewer.
"""

from __future__ import annotations

from templates import (
    ACCOUNTANT,
    DOCTOR,
    EMERGENCY,
    LAB,
    MANAGER,
    NURSE,
    PHARMACY,
    RADIOLOGY,
    RECEPTION,
    TEMPLATES,
    Template,
    _s,
)

CLINICAL_TEMPLATES: tuple[Template, ...] = (
    Template(
        key='LAB_BARCODE_AND_LIS_RECEIPT',
        family='clinical',
        axes=('lab_result_status',),
        observed={'lab_result_status': ('PENDING', 'READY', 'VALIDATED')},
        rule=(
            'The specimen chain is barcode-led. setup_barcode_for_lab_request '
            'registers a barcode when the request is created, scanning advances '
            'the request, and the LIS preview/confirm pair is the bridge from an '
            'external analyser. There is no chain-of-custody model, so the scan '
            'records a state transition rather than who held the tube.'
        ),
        steps=(
            _s(DOCTOR, 'GET|POST /doctor/lab-request/<visit_id>', 'request created with a barcode'),
            _s(LAB, 'POST /lab/barcode/scan/<barcode>', 'specimen scanned against the barcode'),
            _s(LAB, 'GET /lab/lis/preview', 'external results previewed before commit'),
            _s(LAB, 'POST /lab/lis/confirm', 'results confirmed into the request'),
        ),
    ),
    Template(
        key='LAB_QUALITY_CONTROL_AND_REAGENTS',
        family='clinical',
        axes=('lab_result_status',),
        observed={'lab_result_status': ('PENDING', 'READY', 'VALIDATED')},
        rule=(
            'Reagent stock and quality-control entries are separate from the '
            'patient result. get_low_stock_reagents drives the reorder view, and a '
            'QC entry records the control result independently of any patient, so '
            'a failing control does not block result release anywhere in the code.'
        ),
        steps=(
            _s(LAB, 'GET /lab/quality-control', 'control entries listed'),
            _s(LAB, 'GET /lab/reagents', 'reagent stock listed'),
            _s(LAB, 'GET /lab/reagents', 'low-stock reagents surfaced'),
            _s(
                LAB,
                'POST /lab/worklist/request/<request_id>',
                'patient result released regardless of QC state',
            ),
        ),
    ),
    Template(
        key='DOCTOR_PRESCRIPTION_STATE_CHANGES',
        family='clinical',
        axes=('actor_role',),
        observed={'actor_role': ('doctor', 'pharmacist', 'manager', 'reception')},
        rule=(
            'The prescription CHECK constraint allows exactly active, issued, '
            'dispensed and cancelled, while the PrescriptionState enum also '
            'carries draft, partial and expired. A state written from the enum '
            'rather than the constraint is rejected by the database, so the enum '
            'is wider than what the table accepts.'
        ),
        steps=(
            _s(DOCTOR, 'GET|POST /doctor/prescription/<visit_id>', 'prescription created active'),
            _s(DOCTOR, 'POST /doctor/prescription/<visit_id>', 'reissue while active'),
            _s(
                PHARMACY,
                'POST /medication/prescriptions/dispense/<prescription_id>',
                'active to dispensed',
            ),
        ),
    ),
    Template(
        key='EMERGENCY_CASE_RESOLUTION',
        family='clinical',
        axes=('emergency_severity',),
        observed={'emergency_severity': ('LOW', 'MODERATE', 'HIGH', 'CRITICAL')},
        rule=(
            'An emergency case advances through EmergencyStatus and every '
            'transition writes an EmergencyStatusHistory row, which is the only '
            'audit trail the ER keeps. cases/edit amends case data without '
            'requiring a status transition, so an edit is invisible in the history.'
        ),
        steps=(
            _s(EMERGENCY, 'POST /emergency/cases/create', 'case opened with a history row'),
            _s(
                EMERGENCY,
                'POST /emergency/cases/<int:id>/edit',
                'case data amended, no history entry',
            ),
            _s(EMERGENCY, 'POST /emergency/cases/<int:id>/resolve', 'case resolved'),
            _s(EMERGENCY, 'GET /emergency/cases/<int:id>', 'history reviewed'),
        ),
    ),
    Template(
        key='RECEPTION_PATIENT_ADMINISTRATION',
        family='clinical',
        axes=('actor_role',),
        observed={'actor_role': ('reception', 'manager', 'doctor', 'super_admin')},
        rule=(
            'Patient demographics are encrypted at rest: national_id and phone are '
            'AES-GCM with a blind-index hash, names are AES-SIV so they stay '
            'searchable. Duplicate national_id and duplicate phone are both '
            'rejected with 409, so the same person cannot be registered twice '
            'under either identifier.'
        ),
        steps=(
            _s(RECEPTION, 'GET|POST /reception/add_patient', 'created with encrypted identifiers'),
            _s(RECEPTION, 'GET|POST /reception/add_patient', 'duplicate national_id rejected 409'),
            _s(
                RECEPTION,
                'GET|POST /reception/edit_patient/<int:patient_id>',
                'demographics amended',
            ),
            _s(
                RECEPTION,
                'GET /reception/api/smart-patient-search',
                'search resolves through the blind index',
            ),
        ),
    ),
    Template(
        key='APPOINTMENT_NO_SHOW_AND_CANCEL',
        family='clinical',
        axes=('appointment_status',),
        observed={'appointment_status': ('scheduled', 'confirmed', 'no_show', 'cancelled')},
        rule=(
            'Check-in refuses a CANCELLED or NO_SHOW appointment and refuses an '
            'appointment with no department, before the idempotency marker is even '
            'consulted. No-show therefore has to be recorded before the patient '
            'arrives or the slot is silently reusable.'
        ),
        steps=(
            _s(
                RECEPTION,
                'POST /reception/appointments/<int:appointment_id>/no-show',
                'marked NO_SHOW',
            ),
            _s(
                RECEPTION,
                'POST /reception/appointments/<int:appointment_id>/checkin',
                'refused for NO_SHOW',
            ),
            _s(
                RECEPTION,
                'POST /reception/appointments/<int:appointment_id>/cancel',
                'slot cancelled',
            ),
            _s(
                RECEPTION,
                'POST /reception/appointments/<int:appointment_id>/checkin',
                'refused for CANCELLED',
            ),
        ),
    ),
    Template(
        key='MEDICATION_CATALOG_AND_INTERACTIONS',
        family='clinical',
        axes=('actor_role',),
        observed={'actor_role': ('pharmacist', 'manager', 'doctor', 'reception')},
        rule=(
            'A DrugInteraction row is normalised to an ordered pair and its '
            'severity is clamped to LOW, MODERATE or HIGH. The table is one of only '
            'four models in models/ with no tenant_id, so an interaction learned '
            'for one tenant blocks dispensing in every other.'
        ),
        steps=(
            _s(
                PHARMACY,
                'GET|POST /medication/interactions',
                'interaction recorded with a clamped severity',
            ),
            _s(
                PHARMACY,
                'POST /medication/interactions/<int:interaction_id>/toggle',
                'interaction deactivated',
            ),
            _s(
                DOCTOR,
                'GET|POST /doctor/prescription/<visit_id>',
                'screen consults the global interaction table',
            ),
        ),
    ),
    Template(
        key='RADIOLOGY_TEMPLATES_AND_MACROS',
        family='clinical',
        axes=('radiology_modality',),
        observed={'radiology_modality': ('XRay', 'CT', 'MRI', 'US')},
        rule=(
            'Report templates and macros are reporting scaffolding, not '
            'diagnostics. They are per-tenant and editable by radiologists, and '
            'ai-assist consults them for the canned suggestions it returns. Nothing '
            'here validates the report against the study.'
        ),
        steps=(
            _s(RADIOLOGY, 'GET|POST /radiology/api/report-templates', 'template listed or created'),
            _s(RADIOLOGY, 'GET|POST /radiology/api/report-macros', 'macro listed or created'),
            _s(
                RADIOLOGY,
                'POST /radiology/worklist/complete/<request_id>',
                'report written from the template',
            ),
        ),
    ),
    Template(
        key='NURSING_ASSESSMENT_SCALES',
        family='clinical',
        axes=('ward_type',),
        observed={
            'ward_type': ('GENERAL', 'ICU', 'NICU', 'PICU', 'MATERNITY', 'SURGERY', 'ISOLATION')
        },
        rule=(
            'NursingAssessment scores five instruments and assigns a risk band '
            'for each: Braden (severe at 9 and below), Glasgow (severe below 4), '
            'Morse fall (high at 51 and above), pain (high above 6) and Norton '
            '(high at 14 and below). The scales are real and computed; nothing '
            'acts on the band, so a severe score raises no alert.'
        ),
        steps=(
            _s(
                NURSE,
                'GET /nursing-assessment/patient/<int:patient_id>',
                'existing assessments listed',
            ),
            _s(
                NURSE,
                'GET|POST /nursing-assessment/new/<int:patient_id>',
                'scales scored, bands computed',
            ),
            _s(
                NURSE,
                'GET /nursing-assessment/view/<int:assessment_id>',
                'stored assessment reviewed',
            ),
        ),
    ),
    Template(
        key='QUEUE_TICKET_LIFECYCLE',
        family='clinical',
        axes=('task_state',),
        observed={'task_state': ('pending', 'in_progress', 'completed', 'cancelled')},
        rule=(
            'A ticket moves waiting, called, in_progress, completed, skipped or '
            'cancelled. call_next_patient claims atomically with a conditional '
            'UPDATE, but /doctor/call-patient is a plain read-then-write, so two '
            'browser tabs can both claim the same ticket.'
        ),
        steps=(
            _s(RECEPTION, 'GET /reception/queue', 'queue listed, unfiltered by payment'),
            _s(
                RECEPTION,
                'GET /reception/queue/call-next/<int:department_id>',
                'atomic conditional claim',
            ),
            _s(
                RECEPTION,
                'POST /reception/queue/start-treatment/<int:ticket_id>',
                'ticket in_progress',
            ),
            _s(
                RECEPTION,
                'POST /reception/queue/complete-treatment/<int:ticket_id>',
                'ticket completed',
            ),
            _s(
                RECEPTION, 'POST /reception/queue/cancel-ticket/<int:ticket_id>', 'ticket cancelled'
            ),
        ),
    ),
    Template(
        key='DOCTOR_NOTES_AND_TEMPLATES',
        family='clinical',
        axes=('treatment_status',),
        observed={'treatment_status': ('pending', 'active', 'completed', 'cancelled', 'follow_up')},
        rule=(
            'Progress notes are appended as a timestamped labelled block to the '
            'single Visit.notes Text column, not stored as rows, so note history '
            'is unqueryable and note templates live in SystemConfig rather than a '
            'table of their own.'
        ),
        steps=(
            _s(DOCTOR, 'GET|POST /doctor/notes/<visit_id>', 'note appended to Visit.notes'),
            _s(DOCTOR, 'POST /doctor/api/note-templates', 'note template stored in SystemConfig'),
            _s(
                DOCTOR,
                'GET|POST /doctor/save-visit-summary/<visit_id>',
                'summary written, JSON accepted',
            ),
            _s(
                DOCTOR,
                'POST /doctor/end-treatment/<visit_id>',
                'consultation closed, follow-up synced',
            ),
        ),
    ),
    Template(
        key='VISIT_WORKFLOW_STATE_MACHINE',
        family='clinical',
        axes=('visit_state',),
        observed={'visit_state': ('OPEN', 'CHECKED_IN', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')},
        rule=(
            'Visit.status cannot be assigned directly. The model raises ValueError '
            'unless the thread-local state-machine flag is set, and the legal '
            'transitions are fixed: OPEN to CHECKED_IN, CHECKED_IN to IN_PROGRESS, '
            'IN_PROGRESS to COMPLETED, COMPLETED back to OPEN for return-to-treatment, '
            'and CANCELLED is terminal.'
        ),
        steps=(
            _s(DOCTOR, 'POST /doctor/call-patient/<visit_id>', 'ticket claimed'),
            _s(
                DOCTOR,
                'POST /doctor/start-treatment/<visit_id>',
                'OPEN to IN_PROGRESS via the state machine',
            ),
            _s(DOCTOR, 'POST /doctor/end-treatment/<visit_id>', 'IN_PROGRESS to COMPLETED'),
            _s(
                RECEPTION,
                'POST /reception/visits/<int:visit_id>/return-to-treatment',
                'COMPLETED to OPEN, audited',
            ),
        ),
    ),
    Template(
        key='CUSTOM_SERVICE_APPROVAL',
        family='financial',
        axes=('actor_role',),
        observed={'actor_role': ('manager', 'reception', 'accountant', 'super_admin')},
        rule=(
            'A custom service has to be approved before it can be billed, and '
            'approve and reject are manager actions. A ServiceMaster row carries '
            'approved_by and approved_at, so an unapproved service is visible in the '
            'catalogue and unusable in a bill, which is the difference between this '
            'and a temporary service.'
        ),
        steps=(
            _s(MANAGER, 'POST /manager/api/pricing/services', 'custom service created unapproved'),
            _s(
                MANAGER,
                'POST /manager/approve-custom-service/<int:service_id>',
                'approved_by and approved_at set',
            ),
            _s(
                RECEPTION,
                'POST /reception/visits/<int:visit_id>/add-service',
                'approved service billable',
            ),
            _s(
                MANAGER,
                'POST /manager/reject-custom-service/<int:service_id>',
                'alternative rejection path',
            ),
        ),
    ),
    Template(
        key='PROCUREMENT_RECEIVE_AND_LEDGER',
        family='financial',
        axes=('stock_movement_type',),
        observed={
            'stock_movement_type': (
                'purchase',
                'sale',
                'return',
                'adjustment',
                'expired',
                'transfer_in',
                'transfer_out',
            )
        },
        rule=(
            'Receiving a purchase order writes an InventoryLedgerService entry and '
            'posts DR 1300 Inventory against CR 2005 Vendor Payables, and setting '
            'remaining_quantity to zero makes a repeat receive a no-op. There is no '
            'approval workflow on the order itself.'
        ),
        steps=(
            _s(MANAGER, 'POST /procurement/new', 'purchase order raised, no approval step'),
            _s(
                MANAGER,
                'POST /procurement/receive/<int:purchase_id>',
                'stock received, GL journal posted',
            ),
            _s(
                MANAGER,
                'POST /procurement/receive/<int:purchase_id>',
                'repeat receive is idempotent',
            ),
            _s(
                MANAGER,
                'GET /procurement/supplier/<int:supplier_id>/summary',
                'supplier position summarised',
            ),
        ),
    ),
    Template(
        key='PHARMACY_POS_SALE_AND_RETURN',
        family='financial',
        axes=('payment_method', 'stock_movement_type'),
        observed={
            'payment_method': ('CASH', 'CARD', 'WIRE'),
            'stock_movement_type': ('sale', 'return', 'adjustment', 'expired'),
        },
        rule=(
            'pos_sell and PharmacySaleService.create_sale are two entry points to '
            'the same outcome and they disagree on accounting: the service posts '
            'DR 1000 / CR 4100 plus a DR 5000 / CR 1300 cost of goods, while '
            'pos_sell posts nothing, so the same sale reaches revenue or does not '
            'depending on which was called. void_sale likewise posts no reversing '
            'journal.'
        ),
        steps=(
            _s(PHARMACY, 'GET /medication/pos', 'POS opened'),
            _s(
                PHARMACY,
                'POST /medication/pos/sell',
                'sale recorded, stock decremented, no journal',
            ),
            _s(
                ACCOUNTANT,
                'POST /payment/api/pharmacy/returns',
                'return processed, no reversing journal',
            ),
        ),
    ),
)


def add_clinical_templates() -> int:
    """Extend templates.TEMPLATES in place, idempotently. Returns how many were added."""
    existing = {t.key for t in TEMPLATES}
    added = 0
    for t in CLINICAL_TEMPLATES:
        if t.key not in existing:
            TEMPLATES.append(t)
            added += 1
    return added
