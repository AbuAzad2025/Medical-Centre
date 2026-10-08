"""Clinical-ops templates: the diagnostic, pharmacy, inpatient and front-desk routes.

The first matrix covered the financial spine and the visit lifecycle. These
templates cover the rest of the clinical surface that already exists in the
application: the lab catalogue and worklist, radiology ordering and reporting,
the pharmacy inventory, the emergency case machine, inpatient bed management,
and the front-desk record edits.

Every axis declared here is one this template's assertions actually depend on.
A radiology report template does not vary bed type, so the bed axis stays out of
it, and the surgery priority axis is only on the templates where STAT really
bypasses the queue.
"""

from __future__ import annotations

from templates import TEMPLATES, Template, _s

RECEPTION = 'Reception'
DOCTOR = 'Doctor'
LAB = 'Lab'
RADIOLOGY = 'Radiology'
PHARMACY = 'Pharmacy'
EMERGENCY = 'Emergency'
NURSE = 'Nurse'

CLINICAL_OPS_TEMPLATES: tuple[Template, ...] = (
    Template(
        key='LAB_CATALOGUE_AND_WORKLIST',
        family='clinical',
        axes=('lab_order_status',),
        observed={
            'lab_order_status': (
                'ordered',
                'sample_collected',
                'in_progress',
                'results_entered',
                'approved',
                'delivered',
                'cancelled',
            )
        },
        rule=(
            'The lab catalogue and the worklist are separate surfaces: a test is '
            'added to the catalogue, a panel is a named bundle of tests, and only '
            'an ordered request appears on the worklist. /lab/worklist/complete '
            'advances the request while the LabResult.status column records a '
            'second, independent progression, so the two can disagree about '
            'whether a result was validated.'
        ),
        steps=(
            _s(LAB, 'POST /lab/test-catalog/add', 'catalogue test added'),
            _s(LAB, 'POST /lab/test-panels/add', 'panel added as a bundle of tests'),
            _s(LAB, 'POST /lab/test-panels/<int:id>/edit', 'panel edited'),
            _s(LAB, 'POST /lab/worklist/complete/<int:request_id>', 'request advanced'),
        ),
    ),
    Template(
        key='LAB_CATALOGUE_MAINTENANCE',
        family='clinical',
        axes=('currency',),
        observed={'currency': ('ILS', 'EGP', 'USD', 'EUR', 'JOD')},
        rule=(
            'Catalogue edits and deletes are what keep the price list honest. '
            'A deleted test is removed by id, and the price column carries the '
            'currency while the arithmetic in calculate_visit_cost treats every '
            'currency as ILS, so recording a currency here does not change what '
            'a patient is charged.'
        ),
        steps=(
            _s(LAB, 'POST /lab/test-catalog/add', 'test added'),
            _s(LAB, 'POST /lab/test-catalog/<int:id>/edit', 'test price edited'),
            _s(LAB, 'POST /lab/test-catalog/<int:id>/delete', 'test deleted'),
            _s(LAB, 'POST /lab/reagents/add', 'reagent added'),
            _s(LAB, 'POST /lab/reagents/<int:reagent_id>/edit', 'reagent edited'),
        ),
    ),
    Template(
        key='LAB_RESULT_CRITICAL_FLAGGING',
        family='clinical',
        axes=('lab_result_flag', 'lab_result_status'),
        observed={
            'lab_result_flag': ('normal', 'abnormal', 'critical'),
            'lab_result_status': ('PENDING', 'READY', 'VALIDATED'),
        },
        rule=(
            'A result carries both a numeric value and an interpretation, and the '
            'interpretation column is a free String with no CHECK constraint, so '
            '"critical" is a convention rather than a constraint. Validation is '
            'what releases the result to the ordering clinician; an unvalidated '
            'critical result is not alerted on by any route.'
        ),
        steps=(
            _s(DOCTOR, 'POST /reception/visits/create', 'visit priced with a lab test'),
            _s(LAB, 'POST /lab/worklist/complete/<int:request_id>', 'result recorded'),
            _s(LAB, 'POST /api/lab/requests/<int:request_id>/cancel', 'request cancelled'),
            _s(LAB, 'POST /lab/api/fhir/observation', 'observation exported over FHIR'),
        ),
    ),
    Template(
        key='RADIOLOGY_ORDER_TO_REPORT',
        family='clinical',
        axes=('radiology_order_status',),
        observed={
            'radiology_order_status': (
                'ordered',
                'scheduled',
                'in_progress',
                'images_captured',
                'reported',
                'approved',
                'delivered',
                'cancelled',
            )
        },
        rule=(
            'A radiology order moves through eight states while the report and '
            'the result carry their own status, and /api/radiology/results/<id>/'
            'amend writes a second report rather than replacing the first. '
            'DICOMStudy.status is advanced by no route at all, so a study can be '
            'RECEIVED and never reach REPORTED without any code disagreeing.'
        ),
        steps=(
            _s(RADIOLOGY, 'POST /radiology/tests/add', 'radiology test added to catalogue'),
            _s(DOCTOR, 'POST /reception/visits/create', 'visit priced with an imaging test'),
            _s(
                RADIOLOGY, 'POST /api/radiology/requests/<int:request_id>/cancel', 'order cancelled'
            ),
            _s(RADIOLOGY, 'POST /api/radiology/results/<int:result_id>/amend', 'report amended'),
        ),
    ),
    Template(
        key='RADIOLOGY_REPORT_TEMPLATE_LIBRARY',
        family='clinical',
        axes=('print_doc_type',),
        observed={
            'print_doc_type': (
                'invoice',
                'receipt',
                'prescription',
                'queue_ticket',
                'barcode_label',
                'lab_result',
                'radiology_report',
                'emergency_report',
                'report',
                'pharmacy_sale',
            )
        },
        rule=(
            'Report templates and report macros are stored per tenant and injected '
            'into the printed document, so the template library is what decides '
            'which of these document types renders differently. Deleting a '
            'template that a queued report still references leaves the report to '
            'fall back to the default layout without recording that it did so.'
        ),
        steps=(
            _s(RADIOLOGY, 'POST /radiology/api/report-templates', 'report template saved'),
            _s(RADIOLOGY, 'POST /radiology/api/report-macros', 'report macro saved'),
            _s(
                RADIOLOGY,
                'POST /radiology/api/report-templates/<string:template_id>/delete',
                'template deleted',
            ),
            _s(
                RADIOLOGY,
                'POST /radiology/api/report-macros/<string:macro_id>/delete',
                'macro deleted',
            ),
        ),
    ),
    Template(
        key='PHARMACY_CATALOGUE_AND_SUPPLIERS',
        family='clinical',
        axes=('medication_status',),
        observed={'medication_status': ('active', 'inactive', 'discontinued')},
        rule=(
            'The pharmacy catalogue and its suppliers are separate tables, and a '
            'supplier is deleted by id while its purchase history is not. '
            'Medication.status carries three members but the POS dispense check '
            'only looks at inactive, so a discontinued drug is still dispensable '
            'without any route objecting.'
        ),
        steps=(
            _s(PHARMACY, 'POST /medication/add', 'medication added to catalogue'),
            _s(PHARMACY, 'POST /medication/edit/<int:medication_id>', 'medication edited'),
            _s(PHARMACY, 'POST /medication/suppliers/add', 'supplier added'),
            _s(PHARMACY, 'POST /medication/suppliers/<int:supplier_id>/edit', 'supplier edited'),
            _s(
                PHARMACY,
                'POST /medication/suppliers/<int:supplier_id>/delete',
                'supplier deleted',
            ),
        ),
    ),
    Template(
        key='PHARMACY_PURCHASE_AND_DISPENSE',
        family='clinical',
        axes=('stock_movement_type', 'prescription_state'),
        observed={
            'stock_movement_type': (
                'purchase',
                'sale',
                'return',
                'adjustment',
                'expired',
                'transfer_in',
                'transfer_out',
            ),
            'prescription_state': ('draft', 'issued', 'active', 'dispensed', 'partial'),
        },
        rule=(
            'A purchase writes an inventory ledger movement and a dispense writes '
            'another, and the enum has no dispense and no waste member even '
            'though dispensing is the main outflow, so a sale has to be recorded '
            'as a generic movement. A prescription reaches DISPENSED through the '
            'POS charge, which is the only pharmacy route that touches money.'
        ),
        steps=(
            _s(
                PHARMACY,
                'POST /medication/purchases/add',
                'stock received, ledger movement written',
            ),
            _s(PHARMACY, 'POST /medication/pos/charge', 'dispensed, cash collected'),
            _s(
                PHARMACY,
                'POST /medication/api/external-drug-import',
                'drug imported from catalogue',
            ),
        ),
    ),
    Template(
        key='EMERGENCY_CASE_TREATMENT',
        family='clinical',
        axes=('emergency_status',),
        observed={
            'emergency_status': (
                'NEW',
                'WAITING',
                'TRIAGE',
                'RESUSCITATION',
                'TREATMENT',
                'OBSERVATION',
                'IN_PROGRESS',
                'COMPLETED',
                'TRANSFERRED',
            )
        },
        rule=(
            'An emergency case moves through the machine in the enum while the '
            'triage level written by the queue route is a separate RED, YELLOW, '
            'GREEN scale. Nine states are reachable through five routes, and '
            '/emergency/cases/edit writes no history row while moving them, so an '
            'edited case has no record of what it was before.'
        ),
        steps=(
            _s(
                EMERGENCY, 'POST /emergency/start-treatment/<int:emergency_id>', 'treatment started'
            ),
            _s(EMERGENCY, 'POST /emergency/treatment/<int:emergency_id>', 'treatment record added'),
            _s(
                EMERGENCY, 'POST /emergency/radiology-request/<int:emergency_id>', 'imaging ordered'
            ),
            _s(
                EMERGENCY,
                'POST /emergency/prescription/<int:emergency_id>',
                'emergency prescription',
            ),
            _s(EMERGENCY, 'POST /emergency/api/ems/intake', 'EMS prehospital intake recorded'),
        ),
    ),
    Template(
        key='EMERGENCY_QUEUE_TO_ADMISSION',
        family='clinical',
        axes=('triage_level',),
        observed={'triage_level': ('RED', 'YELLOW', 'GREEN')},
        rule=(
            'Triage RED maps to a CRITICAL emergency severity and is the only '
            'level that reaches RESUSCITATION without a wait. A case that '
            'stabilises becomes an Admission, and the admission type is recorded '
            'separately from the emergency severity, so the same clinical '
            'picture can be filed under two different admission types. The '
            'admission type is deliberately not an axis here: the generator takes '
            'a full cross product, and pairing RED with ELECTIVE or GREEN with '
            'EMERGENCY would assert a clinical pairing the code never enforces.'
        ),
        steps=(
            _s(EMERGENCY, 'POST /emergency/api/ems/intake', 'case triaged'),
            _s(EMERGENCY, 'POST /emergency/start-treatment/<int:emergency_id>', 'stabilised'),
            _s(RECEPTION, 'POST /reception/visits/create', 'inpatient visit opened'),
        ),
    ),
    Template(
        key='INPATIENT_BED_AND_ADMISSION',
        family='clinical',
        axes=('bed_status', 'admission_status', 'discharge_type'),
        observed={
            'bed_status': ('AVAILABLE', 'OCCUPIED', 'RESERVED', 'CLEANING', 'OUT_OF_ORDER'),
            'admission_status': ('ADMITTED', 'DISCHARGED', 'TRANSFERRED', 'DECEASED'),
            'discharge_type': ('HOME', 'TRANSFER', 'DEATH', 'AGAINST_ADVICE'),
        },
        rule=(
            'Bed, room and ward are three separate tables and none of them prices '
            'anything, so an ICU stay and a general stay cost the same. Bed '
            'availability has to subtract OUT_OF_ORDER explicitly because it is '
            'not an occupancy. DISCHARGED and DECEASED both release the bed '
            'through the same path, and only the discharge type distinguishes them.'
        ),
        steps=(
            _s(NURSE, 'POST /bed/api/admissions/admit', 'admission opened and a bed assigned'),
            _s(
                NURSE,
                'POST /bed/api/admissions/<int:admission_id>/discharge',
                'bed released on discharge',
            ),
            _s(NURSE, 'POST /nurse/api/protocols', 'nursing protocol recorded'),
            _s(NURSE, 'POST /handover/open', 'shift handover opened'),
        ),
    ),
    Template(
        key='INPATIENT_SURGERY_SCHEDULING',
        family='clinical',
        axes=('surgery_type', 'surgery_priority', 'surgery_status'),
        observed={
            'surgery_type': ('ELECTIVE', 'EMERGENCY', 'URGENT'),
            'surgery_priority': ('NORMAL', 'URGENT', 'STAT'),
            'surgery_status': ('SCHEDULED', 'CONFIRMED', 'IN_PROGRESS', 'COMPLETED', 'DELAYED'),
        },
        rule=(
            'The operating room is read-only: there is no create route and no '
            'writer for a Surgery row, so this journey is exercised through the '
            'model and the read endpoints only. STAT is the only priority that '
            'bypasses the queue, and DELAYED is a member no route can write.'
        ),
        steps=(
            _s(DOCTOR, 'POST /reception/visits/create', 'surgical visit priced'),
            _s(DOCTOR, 'POST /doctor/notes/<int:visit_id>', 'operative note recorded'),
            _s(NURSE, 'POST /handover/open', 'theatre handover opened'),
        ),
    ),
    Template(
        key='DIAGNOSIS_AND_PROBLEM_LIST',
        family='clinical',
        axes=('diagnosis_type', 'diagnosis_status', 'problem_type'),
        observed={
            'diagnosis_type': ('PRIMARY', 'SECONDARY', 'ADMITTING', 'DISCHARGE'),
            'diagnosis_status': ('ACTIVE', 'RESOLVED', 'CHRONIC', 'RELAPSE'),
            'problem_type': ('DIAGNOSIS', 'SYMPTOM', 'COMPLAINT', 'FUNCTIONAL_LIMITATION'),
        },
        rule=(
            'A diagnosis and a problem are different rows with different axes: '
            'diagnosis_type and diagnosis_status belong to the coded diagnosis '
            'while problem_type and severity belong to the problem list. '
            '/reception/api/patients/<patient_id>/problems/<problem_id>/toggle '
            'flips a problem between active and resolved from the front desk, '
            'which is the only write to the problem list outside the chart.'
        ),
        steps=(
            _s(DOCTOR, 'POST /doctor/notes/<int:visit_id>', 'diagnosis recorded'),
            _s(DOCTOR, 'POST /doctor/diagnosis/<int:visit_id>', 'coded diagnosis recorded'),
            _s(
                RECEPTION,
                'POST /reception/api/patients/<int:patient_id>/problems/<int:problem_id>/toggle',
                'problem toggled from the front desk',
            ),
        ),
    ),
    Template(
        key='FRONT_DESK_RECORD_CORRECTION',
        family='clinical',
        axes=('visit_archive_status',),
        observed={'visit_archive_status': ('ACTIVE', 'ARCHIVED')},
        rule=(
            'Reception can edit a patient, edit a visit, transfer a visit and '
            'delete a patient. These are corrections to records that already '
            'exist, and each of them is a write to a table the clinical chart '
            'also reads, so the front desk can change a value the chart treats as '
            'settled. Archiving is the only irreversible one.'
        ),
        steps=(
            _s(
                RECEPTION,
                'POST /reception/edit_patient/<int:patient_id>',
                'patient demographics corrected',
            ),
            _s(RECEPTION, 'POST /reception/edit_visit/<int:visit_id>', 'visit corrected'),
            _s(
                RECEPTION,
                'POST /reception/visits/<int:visit_id>/transfer',
                'visit transferred to another department',
            ),
            _s(
                RECEPTION,
                'POST /reception/delete_patient/<int:patient_id>',
                'patient record deleted',
            ),
        ),
    ),
    Template(
        key='APPOINTMENT_LIFECYCLE',
        family='clinical',
        axes=('appointment_state',),
        observed={
            'appointment_state': (
                'SCHEDULED',
                'CONFIRMED',
                'CHECKED_IN',
                'DONE',
                'COMPLETED',
                'CANCELLED',
                'NO_SHOW',
            )
        },
        rule=(
            'An appointment becomes a visit through a conversion, and the '
            'appointment state machine and the visit state machine disagree on the '
            'name of a checked-in appointment: AppointmentState has CHECKED_IN '
            'while AppointmentWorkflowStatus has checked_in and neither is '
            'constrained by a CHECK. Editing an appointment is a reception write, '
            'so a booked slot can be moved after the patient has arrived.'
        ),
        steps=(
            _s(RECEPTION, 'POST /reception/create_appointment', 'appointment booked'),
            _s(
                RECEPTION,
                'POST /reception/edit_appointment/<int:appointment_id>',
                'appointment rescheduled',
            ),
            _s(
                RECEPTION,
                'POST /reception/online-bookings/checkin',
                'online booking converted on arrival',
            ),
            _s(RECEPTION, 'POST /reception/visits/create', 'visit opened from the appointment'),
        ),
    ),
    Template(
        key='ONLINE_BOOKING_CONVERSION',
        family='clinical',
        axes=('booking_state',),
        observed={'booking_state': ('pending', 'confirmed', 'cancelled', 'converted', 'expired')},
        rule=(
            'A public booking is a row with no patient attached until it is '
            'converted. /booking/register is the public write and '
            '/reception/online-bookings/checkin is the staff write, and both end '
            'at the same place: a real Patient and a real Visit. A booking that '
            'expires without conversion leaves a public row holding a name and a '
            'phone number and nothing else.'
        ),
        steps=(
            _s(RECEPTION, 'POST /booking/create', 'public booking submitted'),
            _s(RECEPTION, 'POST /booking/register', 'booking registered'),
            _s(
                RECEPTION,
                'POST /reception/online-bookings/checkin',
                'booking converted at the desk',
            ),
            _s(RECEPTION, 'POST /booking/cancel/<int:booking_id>', 'booking cancelled'),
        ),
    ),
    Template(
        key='QUEUE_TICKET_OPERATIONS',
        family='clinical',
        axes=('queue_state',),
        observed={
            'queue_state': ('waiting', 'called', 'in_progress', 'completed', 'skipped', 'cancelled')
        },
        rule=(
            'Skipping and returning a ticket are two routes over one column, and '
            'return-to-queue is the only way a skipped patient gets seen without '
            'a new ticket, so a patient can end up with two live rows if the '
            'guard does not treat SKIPPED as terminal. Emergency debt approval is '
            'the one queue write that admits an unpaid patient, which is exactly '
            'the gate the payment path refuses.'
        ),
        steps=(
            _s(RECEPTION, 'POST /reception/queue/skip-patient/<int:ticket_id>', 'ticket skipped'),
            _s(
                RECEPTION,
                'POST /reception/queue/return-to-queue/<int:ticket_id>',
                'ticket returned to the queue',
            ),
            _s(
                RECEPTION,
                'POST /reception/queue/save-settings/<int:department_id>',
                'queue settings saved',
            ),
            _s(
                RECEPTION,
                'POST /reception/queue/approve-emergency-debt/<int:ticket_id>',
                'emergency debt admitted despite the payment gate',
            ),
        ),
    ),
    Template(
        key='STAFF_SCHEDULE_AND_ABSENCE',
        family='clinical',
        axes=('staff_schedule_status', 'actor_role'),
        observed={
            'staff_schedule_status': ('scheduled', 'present', 'absent', 'leave', 'late'),
            'actor_role': ('reception', 'nurse', 'doctor', 'lab'),
        },
        rule=(
            'The reception and manager schedule endpoints are two separate writes '
            'to attendance, and the status column is a free String with no CHECK '
            'constraint, so LATE and ABSENT are a convention. Marking a clinician '
            'absent does not cancel their appointments, which is why the '
            'appointment list can name a doctor who is not in the building.'
        ),
        steps=(
            _s(RECEPTION, 'POST /reception/staff/schedule', 'shift scheduled'),
            _s(RECEPTION, 'POST /reception/staff/absence', 'absence recorded'),
            _s(RECEPTION, 'POST /manager/staff/schedule', 'manager schedule override'),
            _s(RECEPTION, 'POST /manager/staff/absence', 'manager absence override'),
        ),
    ),
    Template(
        key='SPECIALTY_FORM_LIFECYCLE',
        family='clinical',
        axes=('workflow_status',),
        observed={'workflow_status': ('active', 'completed', 'cancelled', 'transferred')},
        rule=(
            'A specialty form is versioned, and publishing a version is a '
            'separate write from editing it, so a form can be edited after it is '
            'published without republishing. Filling a form records the answers '
            'against a visit, which is the only place a structured '
            'disease-specific history is captured at all.'
        ),
        steps=(
            _s(DOCTOR, 'POST /specialty-forms/new', 'form drafted'),
            _s(
                DOCTOR,
                'POST /specialty-forms/<int:form_id>/versions/<int:version_id>/edit',
                'version edited',
            ),
            _s(
                DOCTOR,
                'POST /specialty-forms/<int:form_id>/versions/<int:version_id>/publish',
                'version published',
            ),
            _s(DOCTOR, 'POST /specialty-forms/<int:form_id>/fill', 'form filled against the visit'),
        ),
    ),
    Template(
        key='PATIENT_EDUCATION_MATERIAL',
        family='clinical',
        axes=('print_doc_type',),
        observed={
            'print_doc_type': (
                'invoice',
                'receipt',
                'prescription',
                'queue_ticket',
                'barcode_label',
                'lab_result',
                'radiology_report',
                'emergency_report',
                'report',
                'pharmacy_sale',
            )
        },
        rule=(
            'Patient-education material is authored, edited and then assigned to '
            'a patient, and the assignment is what puts an instruction in front '
            'of a person rather than on a shelf. Assigning is the only write that '
            'records that a patient was told something, and it records no '
            'confirmation that they read it.'
        ),
        steps=(
            _s(DOCTOR, 'POST /patient-education/new', 'material authored'),
            _s(DOCTOR, 'POST /patient-education/edit/<int:material_id>', 'material edited'),
            _s(DOCTOR, 'POST /patient-education/assign', 'material assigned to the patient'),
        ),
    ),
    Template(
        key='AI_IMAGING_TRIAGE',
        family='clinical',
        axes=('radiology_modality',),
        observed={'radiology_modality': ('XRay', 'CT', 'MRI', 'US')},
        rule=(
            'An AI request is raised against an imaging study and reviewed by a '
            'human, and the modality column is a free String, so the request can '
            'name a modality the study did not use. The review route is the only '
            'place a clinician can reject the suggestion, so until it is called '
            'the finding is advisory with no record of who has seen it.'
        ),
        steps=(
            _s(DOCTOR, 'POST /reception/visits/create', 'visit priced with an imaging study'),
            _s(RADIOLOGY, 'POST /ai-imaging/request', 'AI read requested'),
            _s(
                RADIOLOGY,
                'POST /ai-imaging/<int:ai_id>/review',
                'clinician reviewed the suggestion',
            ),
        ),
    ),
    Template(
        key='BARCODE_AND_QUEUE_LABELLING',
        family='clinical',
        axes=('print_doc_type',),
        observed={
            'print_doc_type': (
                'invoice',
                'receipt',
                'prescription',
                'queue_ticket',
                'barcode_label',
                'lab_result',
                'radiology_report',
                'emergency_report',
                'report',
                'pharmacy_sale',
            )
        },
        rule=(
            'A barcode scan is the front door to the queue and it resolves a '
            'patient from a printed label rather than from a search box, which is '
            'the only place a scan can create a queue ticket without a visit '
            'being opened first. The scan route is the only barcode write, so a '
            'label that does not resolve is a silent no-op at the desk.'
        ),
        steps=(
            _s(RECEPTION, 'GET /barcode/api/scan', 'label resolved to a patient'),
            _s(RECEPTION, 'POST /barcode/api/scan', 'scan recorded'),
            _s(RECEPTION, 'POST /reception/queue/add-patient', 'ticket raised from the scan'),
        ),
    ),
)


def add_clinical_ops_templates() -> int:
    """Extend templates.TEMPLATES in place, idempotently. Returns how many were added."""
    existing = {t.key for t in TEMPLATES}
    added = 0
    for t in CLINICAL_OPS_TEMPLATES:
        if t.key not in existing:
            TEMPLATES.append(t)
            added += 1
    return added
