"""Read-journey templates: the screens a clinician or operator actually opens.

The matrix began with state-changing routes, on the reasoning that a GET cannot
corrupt anything. That reasoning is wrong for a clinical system: a read that
returns the wrong patient, the wrong price or a stale queue is a safety defect,
not a cosmetic one. 354 read-only routes were undocumented as a result.

A read journey is still a journey. Every template here performs a write and then
reads what it wrote, because that is the only way to assert something specific
about a list or a detail view: a GET against an empty table proves nothing about
how the row is rendered. A template that only chained three GETs would assert
nothing that a single GET does not already assert, so none of them does.

The axes are the ones a read view genuinely filters on: the role whose decorator
gates the page, and the state of the row being displayed. Varying a read view by
the state it is displaying is real coverage, because the list query branches on
it; varying it by a field the list never reads would not be, and that is not done
here.
"""

from __future__ import annotations

from templates import TEMPLATES, Template, _s

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
PATIENT = 'Patient'

READ_TEMPLATES: tuple[Template, ...] = (
    # ── reception ────────────────────────────────────────────────────────
    Template(
        key='READ_RECEPTION_FRONT_DESK_DASHBOARDS',
        family='clinical',
        axes=('actor_role',),
        observed={
            'actor_role': (
                'super_admin',
                'owner',
                'admin',
                'manager',
                'reception',
                'doctor',
                'nurse',
                'lab',
                'radiology',
                'pharmacist',
                'accountant',
            )
        },
        rule=(
            'Reception has three dashboards rather than one: the landing page, the '
            'reception dashboard and the visits list. They are separate reads of the '
            'same tables, so they can disagree, and a dashboard that counts what the '
            'list does not show is the classic reconciliation argument at a desk. '
            'Which role sees which of them is the decorator, not the query.'
        ),
        steps=(
            _s(
                RECEPTION,
                'POST /reception/visits/create',
                'visit created so the views have a row to show',
            ),
            _s(RECEPTION, 'GET /reception/', 'landing page reached'),
            _s(RECEPTION, 'GET /reception/dashboard', 'dashboard counted'),
            _s(RECEPTION, 'GET /reception/visits', 'list rendered'),
            _s(RECEPTION, 'GET /reception/patients', 'patient list rendered'),
            _s(RECEPTION, 'GET /reception/appointments', 'appointment list rendered'),
        ),
    ),
    Template(
        key='READ_RECEPTION_QUEUE_DISPLAYS',
        family='clinical',
        axes=('queue_state',),
        observed={
            'queue_state': ('waiting', 'called', 'in_progress', 'completed', 'skipped', 'cancelled')
        },
        rule=(
            'The waiting board, the calls board and the snapshot are three reads over '
            'one QueueManagement table, and the waiting board is what a patient reads '
            'off a wall while the calls board is what a clinician reads at a desk. '
            'They filter differently, so a ticket in one is not necessarily in the '
            'other, which is the whole argument for having both.'
        ),
        steps=(
            _s(RECEPTION, 'POST /reception/queue/add-patient', 'ticket raised'),
            _s(RECEPTION, 'GET /reception/display/waiting', 'wall board rendered'),
            _s(RECEPTION, 'GET /reception/display/calls', 'calls board rendered'),
            _s(RECEPTION, 'GET /reception/api/queue-snapshot', 'snapshot read'),
            _s(RECEPTION, 'GET /reception/api/queue-status-all', 'every department read'),
            _s(RECEPTION, 'GET /reception/api/queue-wait-metrics', 'wait metrics read'),
        ),
    ),
    Template(
        key='READ_RECEPTION_LOOKUP_AND_DETAIL',
        family='clinical',
        axes=('visit_state',),
        observed={'visit_state': ('OPEN', 'CHECKED_IN', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')},
        rule=(
            'Opening a patient, a visit and an appointment are three separate detail '
            'reads with three separate id spaces, so a front desk can be looking at the '
            'right patient and the wrong visit. The export is a fourth read of the same '
            'data with no PHI guard on it, which is why it is a separate concern from '
            'the list it mirrors.'
        ),
        steps=(
            _s(RECEPTION, 'POST /reception/visits/create', 'visit created'),
            _s(RECEPTION, 'GET /reception/view_patient/<int:patient_id>', 'patient chart opened'),
            _s(RECEPTION, 'GET /reception/view_visit/<int:visit_id>', 'visit detail opened'),
            _s(
                RECEPTION,
                'GET /reception/view_appointment/<int:appointment_id>',
                'appointment opened',
            ),
            _s(RECEPTION, 'GET /reception/export/visits', 'visit export read'),
        ),
    ),
    Template(
        key='READ_RECEPTION_LOOKUP_APIS',
        family='clinical',
        axes=('actor_role',),
        observed={'actor_role': ('reception', 'manager', 'admin', 'doctor')},
        rule=(
            'The autocomplete endpoints back the patient, doctor and service pickers, '
            'so they decide what a clinician can select rather than what they can see. '
            'Each one is tenant scoped independently, which means a picker can offer a '
            'department the desk is not entitled to book into.'
        ),
        steps=(
            _s(RECEPTION, 'GET /reception/api/doctors', 'doctor picker populated'),
            _s(RECEPTION, 'GET /reception/api/department-staff', 'department staff read'),
            _s(
                RECEPTION,
                'GET /reception/api/department-services',
                'services for the department read',
            ),
            _s(RECEPTION, 'GET /reception/api/available-times', 'available slots read'),
            _s(
                RECEPTION,
                'GET /reception/api/patient-queue-position/<int:patient_id>/<int:department_id>',
                'queue position read',
            ),
        ),
    ),
    Template(
        key='READ_RECEPTION_PRINTABLES',
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
            'Reception prints an invoice and a prescription, and the doctor prints the '
            'same two documents from the other console. Each print route renders its '
            'own template with its own set of permitted fields, so the same invoice '
            'can look different to a patient depending on which desk printed it.'
        ),
        steps=(
            _s(RECEPTION, 'POST /reception/visits/create', 'visit created'),
            _s(RECEPTION, 'GET /reception/print_invoice/<int:invoice_id>', 'invoice printed'),
            _s(
                RECEPTION,
                'GET /reception/print_prescription/<int:prescription_id>',
                'prescription printed',
            ),
            _s(RECEPTION, 'GET /reception/print_receipt/<int:visit_id>', 'receipt printed'),
        ),
    ),
    Template(
        key='READ_RECEPTION_FOLLOW_UP_AND_PAYMENT_LISTS',
        family='financial',
        axes=('payment_status',),
        observed={
            'payment_status': (
                'PENDING',
                'PAID',
                'PARTIAL',
                'DEBT',
                'EMERGENCY_DEBT',
                'CONFIRMED',
                'REFUNDED',
                'CANCELLED',
            )
        },
        rule=(
            'The payments list and the follow-up list are the two desks that reconcile '
            'at end of day, and both filter on a status column the write path owns. A '
            'visit left in DEBT and one left in EMERGENCY_DEBT both appear unpaid to '
            'the patient and different to the queue, which admits neither.'
        ),
        steps=(
            _s(RECEPTION, 'POST /reception/visits/create', 'visit created'),
            _s(RECEPTION, 'GET /reception/payments', 'payments list read'),
            _s(RECEPTION, 'GET /reception/follow-ups', 'follow-up list read'),
        ),
    ),
    # ── doctor ───────────────────────────────────────────────────────────
    Template(
        key='READ_DOCTOR_WORK_LISTS',
        family='clinical',
        axes=('actor_role',),
        observed={'actor_role': ('doctor', 'admin', 'manager', 'super_admin')},
        rule=(
            'The doctor work list is read three ways: the dashboard, the dashboard for '
            'a specific doctor, and the today-visits endpoint the dashboard polls. '
            'dashboard-for-doctor takes a doctor id as a path parameter rather than '
            'reading the session, so one doctor can read another doctor list.'
        ),
        steps=(
            _s(DOCTOR, 'POST /doctor/start-treatment/<int:visit_id>', 'visit in the work list'),
            _s(DOCTOR, 'GET /doctor/dashboard', 'own dashboard read'),
            _s(DOCTOR, 'GET /doctor/dashboard/<int:doctor_id>', 'another doctor dashboard read'),
            _s(DOCTOR, 'GET /doctor/api/dashboard-stats', 'counters read'),
            _s(DOCTOR, 'GET /doctor/api/today-visits', 'today list read'),
            _s(DOCTOR, 'GET /doctor/visits', 'visit list read'),
        ),
    ),
    Template(
        key='READ_DOCTOR_PATIENT_CHART',
        family='clinical',
        axes=('visit_state',),
        observed={'visit_state': ('OPEN', 'CHECKED_IN', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')},
        rule=(
            'The chart is assembled from six separate reads over four tables: the '
            'visit detail, the patient timeline, the medical history, the prescription '
            'history and the radiology results. They have no shared snapshot, so a '
            'chart can show a prescription written after the visit it belongs to was '
            'closed, and nothing on the page indicates which read is older.'
        ),
        steps=(
            _s(DOCTOR, 'POST /doctor/notes/<int:visit_id>', 'note written'),
            _s(DOCTOR, 'GET /doctor/view_patient/<int:visit_id>', 'chart opened'),
            _s(DOCTOR, 'GET /doctor/patient-details/<int:visit_id>', 'visit detail read'),
            _s(DOCTOR, 'GET /doctor/visit-summary/<int:visit_id>', 'summary read'),
            _s(DOCTOR, 'GET /doctor/medical-history/<int:patient_id>', 'history read'),
            _s(DOCTOR, 'GET /doctor/patient-timeline/<int:patient_id>', 'timeline read'),
            _s(
                DOCTOR,
                'GET /doctor/prescriptions-history/<int:patient_id>',
                'prescription history read',
            ),
            _s(DOCTOR, 'GET /doctor/radiology-results/<int:patient_id>', 'radiology results read'),
        ),
    ),
    Template(
        key='READ_DOCTOR_ORDER_AND_RESULT_LISTS',
        family='clinical',
        axes=('lab_result_status',),
        observed={'lab_result_status': ('PENDING', 'READY', 'VALIDATED')},
        rule=(
            'The order lists and the result list are separated by direction: lab-requests '
            'and radiology-requests show what this doctor asked for, prescriptions shows '
            'what was issued, and the results route is per patient rather than per '
            'order. A request that was never resulted therefore has no row in the list '
            'a clinician would check for it.'
        ),
        steps=(
            _s(DOCTOR, 'POST /doctor/lab-request/<int:visit_id>', 'lab requested'),
            _s(DOCTOR, 'POST /doctor/radiology-request/<int:visit_id>', 'imaging requested'),
            _s(DOCTOR, 'POST /doctor/prescription/<int:visit_id>', 'prescription issued'),
            _s(DOCTOR, 'GET /doctor/lab-requests', 'lab orders read'),
            _s(DOCTOR, 'GET /doctor/radiology-requests', 'imaging orders read'),
            _s(DOCTOR, 'GET /doctor/prescriptions', 'prescriptions read'),
        ),
    ),
    Template(
        key='READ_DOCTOR_RECORDS_AND_PATIENTS',
        family='clinical',
        axes=('actor_role',),
        observed={'actor_role': ('doctor', 'nurse', 'reception', 'manager', 'admin')},
        rule=(
            'medical-records and patients are two read surfaces over the Patient table, '
            'one clinical and one administrative, and the patient search endpoint backs '
            'both. A result set built for a clinical chart and one built for a '
            'administrative list can legitimately differ, and the difference is where '
            'a wrong-patient read hides.'
        ),
        steps=(
            _s(DOCTOR, 'POST /doctor/notes/<int:visit_id>', 'note written'),
            _s(DOCTOR, 'GET /doctor/api/patient-search', 'search endpoint exercised'),
            _s(DOCTOR, 'GET /doctor/patients', 'patient list read'),
            _s(DOCTOR, 'GET /doctor/medical-records', 'record list read'),
        ),
    ),
    # ── nursing ──────────────────────────────────────────────────────────
    Template(
        key='READ_NURSING_WORK_LISTS',
        family='clinical',
        axes=('task_state',),
        observed={'task_state': ('pending', 'in_progress', 'completed', 'cancelled')},
        rule=(
            'The nursing task list filters on the task status while the ward and vital '
            'signs pages filter on the bed and the patient, so a completed task '
            'disappears from the work list while the observations it produced are still '
            'on the chart. The reports page is a third read of the same work with an '
            'aggregate rather than a list.'
        ),
        steps=(
            _s(NURSE, 'POST /nurse/tasks/create', 'task raised'),
            _s(NURSE, 'GET /nurse/tasks', 'task list read'),
            _s(NURSE, 'GET /nurse/wards', 'wards read'),
            _s(NURSE, 'GET /nurse/vitals', 'vitals list read'),
            _s(NURSE, 'GET /nurse/vital-signs', 'vital signs page read'),
            _s(NURSE, 'GET /nurse/reports', 'aggregate read'),
        ),
    ),
    Template(
        key='READ_NURSING_PATIENT_SURFACES',
        family='clinical',
        axes=('actor_role',),
        observed={'actor_role': ('nurse', 'doctor', 'manager', 'admin')},
        rule=(
            'patient-care, patient-monitoring and medications are three reads scoped to '
            'the nurse role, and medications is the only one that reads the pharmacy '
            'tables. An administration that is MISSED or LATE is not visible on any of '
            'the three, because those states live on the eMAR table, which no route '
            'reaches.'
        ),
        steps=(
            _s(NURSE, 'POST /nurse/record-vital-signs/<int:patient_id>', 'observation recorded'),
            _s(NURSE, 'GET /nurse/patient-care', 'care plan read'),
            _s(NURSE, 'GET /nurse/patient-monitoring', 'monitoring read'),
            _s(NURSE, 'GET /nurse/medications', 'medication list read'),
            _s(NURSE, 'GET /nurse/patients', 'nurse patient list read'),
        ),
    ),
    # ── lab ──────────────────────────────────────────────────────────────
    Template(
        key='READ_LAB_WORKLIST_AND_RESULTS',
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
            'The worklist and the results list are different questions: the worklist is '
            'what is outstanding and the results list is what has been produced, and a '
            'request moves between them without a shared status. The API worklist is the '
            'third read, written for the analyser integration rather than the '
            'technologist, so it can show a request the screen does not.'
        ),
        steps=(
            _s(LAB, 'POST /lab/worklist/complete/<int:request_id>', 'request advanced'),
            _s(LAB, 'GET /lab/worklist', 'technologist worklist read'),
            _s(LAB, 'GET /lab/api/worklist', 'integration worklist read'),
            _s(LAB, 'GET /lab/requests', 'request list read'),
            _s(LAB, 'GET /lab/results', 'result list read'),
        ),
    ),
    Template(
        key='READ_LAB_CATALOGUE_AND_QUALITY',
        family='clinical',
        axes=('currency',),
        observed={'currency': ('ILS', 'EGP', 'USD', 'EUR', 'JOD')},
        rule=(
            'The test catalogue and the panel catalogue are administration rather than '
            'clinical work, but they decide what a clinician can order, and the price '
            'column carries a currency that the visit pricing arithmetic ignores. The '
            'quality page is the only read that shows whether a result could be trusted '
            'at all.'
        ),
        steps=(
            _s(LAB, 'POST /lab/test-catalog/add', 'catalogue test added'),
            _s(LAB, 'POST /lab/test-panels/add', 'panel added'),
            _s(LAB, 'GET /lab/test-catalog/', 'catalogue read'),
            _s(LAB, 'GET /lab/test-panels/', 'panels read'),
            _s(LAB, 'GET /lab/api/test-catalog', 'catalogue API read'),
            _s(LAB, 'GET /lab/quality', 'quality page read'),
            _s(LAB, 'GET /lab/reports', 'lab report read'),
        ),
    ),
    Template(
        key='READ_LAB_PRINTABLES',
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
            'A lab request prints in three forms: a barcode label for the analyser, a '
            'plain request sheet, and a PDF of the same sheet. They are separate routes '
            'over one request id, so a barcode can be printed against a request whose '
            'sheet has already been superseded.'
        ),
        steps=(
            _s(LAB, 'POST /lab/worklist/complete/<int:request_id>', 'request advanced'),
            _s(LAB, 'GET /lab/barcode/print/<int:request_id>', 'barcode label printed'),
            _s(LAB, 'GET /lab/print_request/<int:id>', 'request sheet printed'),
            _s(LAB, 'GET /lab/print_request/<int:id>/pdf', 'request sheet printed as PDF'),
            _s(LAB, 'GET /lab/api/fhir/observation/lab/<int:result_id>', 'observation read'),
        ),
    ),
    # ── radiology ────────────────────────────────────────────────────────
    Template(
        key='READ_RADIOLOGY_WORKLIST_AND_REPORTS',
        family='clinical',
        axes=('radiology_result_status',),
        observed={'radiology_result_status': ('PENDING', 'READY', 'VALIDATED')},
        rule=(
            'The radiologist reads a worklist and writes a report; everything after that '
            'is read from the reports list rather than the worklist. A report that is '
            'READY but not VALIDATED appears in both, so a clinician can act on a '
            'report the imaging department has not released.'
        ),
        steps=(
            _s(RADIOLOGY, 'POST /api/radiology/results/<int:result_id>/amend', 'report written'),
            _s(
                RADIOLOGY, 'GET /radiology/worklist/request/<int:request_id>', 'single request read'
            ),
            _s(RADIOLOGY, 'GET /radiology/api/worklist', 'worklist API read'),
            _s(RADIOLOGY, 'GET /radiology/requests', 'request list read'),
            _s(RADIOLOGY, 'GET /radiology/results', 'result list read'),
            _s(RADIOLOGY, 'GET /radiology/reports', 'report list read'),
            _s(RADIOLOGY, 'GET /radiology/quality', 'quality page read'),
        ),
    ),
    Template(
        key='READ_RADIOLOGY_PRINTABLES_AND_FILES',
        family='clinical',
        axes=('radiology_modality',),
        observed={'radiology_modality': ('XRay', 'CT', 'MRI', 'US')},
        rule=(
            'The report PDF and the image download are two reads of the same study with '
            'different authorisation: a report can be printed before the images are '
            'released, and the file route is the only place a DICOM object leaves the '
            'application, so it is the read with the widest blast radius.'
        ),
        steps=(
            _s(RADIOLOGY, 'POST /api/radiology/results/<int:result_id>/amend', 'report written'),
            _s(
                RADIOLOGY,
                'GET /radiology/print_report/<int:radiology_scan_id>/pdf',
                'report PDF printed',
            ),
            _s(RADIOLOGY, 'GET /radiology/files/<int:file_id>', 'image file read'),
            _s(
                RADIOLOGY,
                'GET /radiology/api/fhir/imagingstudy/<int:result_id>',
                'imaging study read',
            ),
            _s(
                RADIOLOGY,
                'GET /radiology/api/fhir/diagnosticreport/radiology/<int:result_id>',
                'diagnostic report read',
            ),
        ),
    ),
    # ── pharmacy ─────────────────────────────────────────────────────────
    Template(
        key='READ_PHARMACY_CATALOGUE_AND_STOCK',
        family='clinical',
        axes=('medication_status',),
        observed={'medication_status': ('active', 'inactive', 'discontinued')},
        rule=(
            'The pharmacy reads four separate inventories: the drug catalogue, the '
            'suppliers, the purchases and the supply requests. Only the first has a '
            'status that gates dispensing, so a discontinued drug still appears on the '
            'purchase list where it can be reordered.'
        ),
        steps=(
            _s(PHARMACY, 'POST /medication/add', 'drug added'),
            _s(PHARMACY, 'POST /medication/suppliers/add', 'supplier added'),
            _s(PHARMACY, 'POST /medication/purchases/add', 'stock received'),
            _s(PHARMACY, 'GET /medication/list', 'catalogue read'),
            _s(PHARMACY, 'GET /medication/suppliers', 'suppliers read'),
            _s(PHARMACY, 'GET /medication/purchases', 'purchases read'),
            _s(PHARMACY, 'GET /medication/supply-requests', 'supply requests read'),
            _s(PHARMACY, 'GET /medication/supply-requests/<int:request_id>', 'single request read'),
        ),
    ),
    Template(
        key='READ_PHARMACY_SALES_AND_PRESCRIPTIONS',
        family='financial',
        axes=('journal_source_type',),
        observed={
            'journal_source_type': (
                'visit',
                'invoice',
                'payment',
                'pharmacy_sale',
                'expense',
                'refund',
                'procurement',
            )
        },
        rule=(
            'A pharmacy sale is its own ledger source, so the sales list and the visit '
            'payments list are two reconciliations that meet at the same cash account. '
            'The totals and report endpoints aggregate the sales stream on its own, '
            'which is why a reconciliation between the two can be non-zero for a '
            'period where both are individually correct.'
        ),
        steps=(
            _s(PHARMACY, 'POST /medication/pos/charge', 'sale recorded'),
            _s(PHARMACY, 'GET /medication/sales/<int:sale_id>', 'sale detail read'),
            _s(PHARMACY, 'GET /medication/sales/api/list', 'sale list API read'),
            _s(PHARMACY, 'GET /medication/sales/api/totals', 'sale totals read'),
            _s(PHARMACY, 'GET /medication/sales/api/report', 'sale report read'),
            _s(PHARMACY, 'GET /medication/prescriptions', 'prescriptions read'),
            _s(PHARMACY, 'GET /medication/consumption-report', 'consumption read'),
        ),
    ),
    Template(
        key='READ_PHARMACY_RECEIPTS',
        family='financial',
        axes=('payment_method',),
        observed={'payment_method': ('CASH', 'CARD', 'visa', 'mada', 'WIRE', 'INSURANCE', 'FORCE')},
        rule=(
            'A sale receipt and a printed sale receipt are two routes over one sale, and '
            'they render from different templates, so the printed receipt is not '
            'guaranteed to match what the detail view showed at the till.'
        ),
        steps=(
            _s(PHARMACY, 'POST /medication/pos/charge', 'sale recorded'),
            _s(PHARMACY, 'GET /medication/sales/<int:sale_id>/receipt', 'receipt read'),
            _s(PHARMACY, 'GET /medication/sales/<int:sale_id>/print', 'receipt printed'),
        ),
    ),
    # ── emergency ────────────────────────────────────────────────────────
    Template(
        key='READ_EMERGENCY_TRIAGE_AND_QUEUE',
        family='clinical',
        axes=('triage_level',),
        observed={'triage_level': ('RED', 'YELLOW', 'GREEN')},
        rule=(
            'The triage list, the waiting queue and the patient queue are three reads '
            'over one EmergencyCase plus its queue ticket, and they order by different '
            'columns: triage orders by severity, the waiting queue by arrival, and the '
            'patient queue by the ticket. A case can therefore appear in a different '
            'position on each screen at the same moment.'
        ),
        steps=(
            _s(
                EMERGENCY, 'POST /emergency/start-treatment/<int:emergency_id>', 'case in treatment'
            ),
            _s(EMERGENCY, 'GET /emergency/triage', 'triage list read'),
            _s(EMERGENCY, 'GET /emergency/queue', 'waiting queue read'),
            _s(EMERGENCY, 'GET /emergency/patient-queue', 'patient queue read'),
            _s(EMERGENCY, 'GET /emergency/cases', 'case list read'),
            _s(EMERGENCY, 'GET /emergency/emergency-visits', 'visit list read'),
        ),
    ),
    Template(
        key='READ_EMERGENCY_CASE_DETAIL',
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
            'The case detail, the patient detail and the printed report are three reads '
            'of one emergency, and the case edit route that moves the status writes no '
            'history row, so a completed case and a transferred case look identical in '
            'the record apart from the status the current reader happened to load.'
        ),
        steps=(
            _s(EMERGENCY, 'POST /emergency/start-treatment/<int:emergency_id>', 'case advanced'),
            _s(EMERGENCY, 'GET /emergency/patient-details/<int:emergency_id>', 'case detail read'),
            _s(EMERGENCY, 'GET /emergency/emergency-report/<int:emergency_id>', 'report read'),
            _s(
                EMERGENCY,
                'GET /emergency/print-emergency-report/<int:emergency_id>',
                'report printed',
            ),
            _s(EMERGENCY, 'GET /emergency/reports', 'report list read'),
        ),
    ),
    Template(
        key='READ_EMERGENCY_PATIENT_CONTEXT',
        family='clinical',
        axes=('actor_role',),
        observed={'actor_role': ('doctor', 'nurse', 'reception', 'manager', 'admin')},
        rule=(
            'In emergency the patient history, the lab results, the radiology results '
            'and the prescription history are four separate reads assembled into one '
            'page, and each is scoped to the patient rather than to the emergency. That '
            'is correct for continuity of care and it is also the shape of the '
            'wrong-patient read.'
        ),
        steps=(
            _s(
                EMERGENCY,
                'POST /emergency/prescription/<int:emergency_id>',
                'emergency prescription',
            ),
            _s(EMERGENCY, 'GET /emergency/medical-history/<int:patient_id>', 'history read'),
            _s(EMERGENCY, 'GET /emergency/lab-results/<int:patient_id>', 'lab results read'),
            _s(EMERGENCY, 'GET /emergency/radiology-results/<int:patient_id>', 'radiology read'),
            _s(
                EMERGENCY,
                'GET /emergency/prescriptions-history/<int:patient_id>',
                'prescriptions read',
            ),
            _s(EMERGENCY, 'GET /emergency/patients', 'emergency patient list read'),
        ),
    ),
    # ── accounting ───────────────────────────────────────────────────────
    Template(
        key='READ_ACCOUNTANT_DASHBOARDS_AND_REPORTS',
        family='financial',
        axes=('invoice_status',),
        observed={'invoice_status': ('DRAFT', 'ISSUED', 'POSTED', 'PAID', 'VOID')},
        rule=(
            'The accountant console is built from one read per report rather than one '
            'report with a parameter: daily and monthly audit are separate endpoints, '
            'and financial-report and financial are separate again. They aggregate the '
            'same tables with different date boundaries, so a figure can be correct on '
            'one page and contradicted by the page next to it.'
        ),
        steps=(
            _s(ACCOUNTANT, 'POST /payment/process/<visit_id>', 'payment posted to the ledger'),
            _s(ACCOUNTANT, 'GET /accountant/', 'console landing read'),
            _s(ACCOUNTANT, 'GET /accountant/dashboard', 'dashboard read'),
            _s(ACCOUNTANT, 'GET /accountant/daily-summary', 'daily summary read'),
            _s(ACCOUNTANT, 'GET /accountant/audit/daily', 'daily audit read'),
            _s(ACCOUNTANT, 'GET /accountant/audit/monthly', 'monthly audit read'),
            _s(ACCOUNTANT, 'GET /accountant/financial', 'financial page read'),
            _s(ACCOUNTANT, 'GET /accountant/financial-report', 'financial report read'),
        ),
    ),
    Template(
        key='READ_ACCOUNTANT_ACCOUNTS_AND_PATIENT_BALANCES',
        family='financial',
        axes=('journal_source_type',),
        observed={
            'journal_source_type': (
                'visit',
                'invoice',
                'payment',
                'pharmacy_sale',
                'expense',
                'refund',
                'procurement',
            )
        },
        rule=(
            'The accounts list and the trial balance are reads over the chart of '
            'accounts, and the patient-accounts page is a read over balances that are '
            'not an account type at all. The ERP export is the only route that leaves '
            'the application with the whole ledger, and it is a GET, so it needs no '
            'confirmation and writes no audit row of its own.'
        ),
        steps=(
            _s(ACCOUNTANT, 'POST /payment/process/<visit_id>', 'journal posted'),
            _s(ACCOUNTANT, 'GET /accountant/accounts', 'chart of accounts read'),
            _s(ACCOUNTANT, 'GET /accountant/accounts/<int:account_id>', 'ledger read'),
            _s(ACCOUNTANT, 'GET /accountant/trial-balance', 'trial balance read'),
            _s(ACCOUNTANT, 'GET /accountant/patient-accounts', 'patient balances read'),
            _s(ACCOUNTANT, 'GET /accountant/invoices', 'invoice list read'),
            _s(ACCOUNTANT, 'GET /accountant/open-invoices', 'open invoice list read'),
            _s(ACCOUNTANT, 'GET /accountant/api/erp/export', 'ledger exported'),
        ),
    ),
    Template(
        key='READ_PAYMENT_CONSOLE',
        family='financial',
        axes=('payment_method',),
        observed={'payment_method': ('CASH', 'CARD', 'visa', 'mada', 'WIRE', 'INSURANCE', 'FORCE')},
        rule=(
            'The payment console reports are separate reads: the dashboard, the history '
            'and the payment reports endpoint. The methods endpoint is the one that '
            'decides what the POS offers, and it lists the enum rather than what the '
            'ledger will accept, which is how an unavailable method reaches a till.'
        ),
        steps=(
            _s(ACCOUNTANT, 'POST /payment/process/<visit_id>', 'payment recorded'),
            _s(ACCOUNTANT, 'GET /payment/', 'console landing read'),
            _s(ACCOUNTANT, 'GET /payment/dashboard', 'dashboard read'),
            _s(ACCOUNTANT, 'GET /payment/history', 'history read'),
            _s(ACCOUNTANT, 'GET /payment/methods', 'offered methods read'),
            _s(ACCOUNTANT, 'GET /payment/reports', 'payment reports read'),
            _s(
                ACCOUNTANT,
                'GET /payment/api/pos/prescriptions/<int:prescription_id>/lookup',
                'POS lookup read',
            ),
        ),
    ),
    Template(
        key='READ_FINANCE_OPS_AND_SLOW_QUERIES',
        family='financial',
        axes=('actor_role',),
        observed={'actor_role': ('accountant', 'manager', 'admin', 'owner', 'super_admin')},
        rule=(
            'The finance console adds invoice and payment lists to the accountant pages '
            'with a different set of filters, and the slow-query report is the only read '
            'in the system that reports on the application itself. Its weekly detail is '
            'a third read with its own id space, so a report id and a query id are not '
            'interchangeable.'
        ),
        steps=(
            _s(ACCOUNTANT, 'POST /finance/visits/<int:visit_id>/archive', 'visit archived'),
            _s(ACCOUNTANT, 'GET /finance/', 'finance console read'),
            _s(ACCOUNTANT, 'GET /finance/dashboard', 'dashboard read'),
            _s(ACCOUNTANT, 'GET /finance/invoices', 'invoice list read'),
            _s(ACCOUNTANT, 'GET /finance/payments', 'payment list read'),
            _s(ACCOUNTANT, 'GET /finance/audit', 'audit page read'),
            _s(ACCOUNTANT, 'GET /finance/slow-queries', 'slow queries read'),
            _s(ACCOUNTANT, 'GET /finance/slow-queries/weekly', 'weekly report read'),
        ),
    ),
    # ── manager ──────────────────────────────────────────────────────────
    Template(
        key='READ_MANAGER_REPORT_CENTRE',
        family='financial',
        axes=('report_execution_state',),
        observed={
            'report_execution_state': ('pending', 'running', 'completed', 'failed', 'cancelled')
        },
        rule=(
            'The manager report surface is many endpoints over one reporting layer: '
            'analytics, the KPI dashboard, the reports centre, the drill-down and the '
            'monthly comparison. Each is a separate read, so the same period can be '
            'summarised differently on each, and the drill-down takes its report type '
            'as a path parameter rather than a validated value.'
        ),
        steps=(
            _s(MANAGER, 'POST /report-builder/templates', 'report template saved'),
            _s(MANAGER, 'GET /manager/analytics', 'analytics read'),
            _s(MANAGER, 'GET /manager/kpi-dashboard', 'KPI dashboard read'),
            _s(MANAGER, 'GET /manager/reports-center', 'reports centre read'),
            _s(MANAGER, 'GET /manager/drill-down/<report_type>', 'drill-down read'),
            _s(MANAGER, 'GET /manager/monthly-comparison', 'period comparison read'),
            _s(MANAGER, 'GET /manager/financial-reports', 'financial reports read'),
        ),
    ),
    Template(
        key='READ_MANAGER_STAFF_AND_DEPARTMENTS',
        family='financial',
        axes=('actor_role',),
        observed={
            'actor_role': (
                'super_admin',
                'owner',
                'admin',
                'manager',
                'reception',
                'doctor',
                'nurse',
                'lab',
                'radiology',
                'pharmacist',
                'accountant',
            )
        },
        rule=(
            'Staff capacity and user management are two reads over the same roster with '
            'different questions: capacity counts scheduled hours against the roster, '
            'and user management lists accounts. The self-service page is the third, '
            'and it is scoped to the manager rather than the tenant, so a manager sees '
            'their own requests and nobody else can.'
        ),
        steps=(
            _s(MANAGER, 'POST /manager/staff/schedule', 'shift scheduled'),
            _s(MANAGER, 'GET /manager/staff', 'roster read'),
            _s(MANAGER, 'GET /manager/staff/capacity', 'capacity read'),
            _s(MANAGER, 'GET /manager/user-management', 'user management read'),
            _s(MANAGER, 'GET /manager/departments', 'departments read'),
            _s(MANAGER, 'GET /manager/self-service', 'self-service read'),
            _s(MANAGER, 'GET /manager/settlements/export', 'settlements exported'),
        ),
    ),
    Template(
        key='READ_MANAGER_PRICING_AND_SATISFACTION',
        family='financial',
        axes=('currency',),
        observed={'currency': ('ILS', 'EGP', 'USD', 'EUR', 'JOD')},
        rule=(
            'The pricing page is what a manager changes a price on and the unit-control '
            'page is what changes how that price is displayed, so a display unit change '
            'can make an unchanged price read as a changed one. The satisfaction '
            'dashboard reads the survey table, which is populated by the only public '
            'write in the application.'
        ),
        steps=(
            _s(MANAGER, 'POST /manager/seed-pricing', 'price list seeded'),
            _s(MANAGER, 'POST /manager/api/units/toggle', 'display unit changed'),
            _s(MANAGER, 'GET /manager/pricing', 'pricing page read'),
            _s(MANAGER, 'GET /manager/unit-control', 'unit control read'),
            _s(MANAGER, 'GET /manager/custom-service-approvals', 'custom service approvals read'),
            _s(MANAGER, 'GET /manager/patient-satisfaction', 'satisfaction dashboard read'),
        ),
    ),
    # ── patient portal ───────────────────────────────────────────────────
    Template(
        key='READ_PATIENT_PORTAL_RECORDS',
        family='rbac',
        axes=('actor_role',),
        observed={
            'actor_role': (
                'super_admin',
                'owner',
                'admin',
                'manager',
                'reception',
                'doctor',
                'nurse',
                'lab',
                'radiology',
                'pharmacist',
                'accountant',
            )
        },
        rule=(
            'The portal is a patient-facing read surface over the same records a '
            'clinician sees, with no field-level masking in the read itself. Every page '
            'therefore has to rely on the linked identity to decide what to return, '
            'which makes the link-account write the security boundary for all twelve of '
            'these routes.'
        ),
        steps=(
            _s(PATIENT, 'POST /portal/link-account', 'portal login joined to a patient'),
            _s(PATIENT, 'GET /portal/', 'portal landing read'),
            _s(PATIENT, 'GET /portal/dashboard', 'dashboard read'),
            _s(PATIENT, 'GET /portal/medical-records', 'records read'),
            _s(PATIENT, 'GET /portal/lab-results', 'lab results read'),
            _s(PATIENT, 'GET /portal/radiology-results', 'radiology read'),
            _s(PATIENT, 'GET /portal/prescriptions', 'prescriptions read'),
            _s(PATIENT, 'GET /portal/vaccinations', 'vaccinations read'),
        ),
    ),
    Template(
        key='READ_PATIENT_PORTAL_BILLS_AND_BOOKING',
        family='financial',
        axes=('invoice_status',),
        observed={'invoice_status': ('DRAFT', 'ISSUED', 'POSTED', 'PAID', 'VOID')},
        rule=(
            'The portal bills page is the patient-facing view of the same invoice rows '
            'the accountant console reads, and it is the only place a patient can see a '
            'VOID invoice, because the accountant open-invoice list filters it out. The '
            'booking portal is a separate identity: a public booking has no patient '
            'until it is converted.'
        ),
        steps=(
            _s(PATIENT, 'POST /portal/link-account', 'portal login joined to a patient'),
            _s(ACCOUNTANT, 'POST /payment/process/<visit_id>', 'invoice settled'),
            _s(PATIENT, 'GET /portal/bills', 'bills read'),
            _s(PATIENT, 'GET /portal/documents', 'documents read'),
            _s(RECEPTION, 'POST /booking/create', 'public booking made'),
            _s(RECEPTION, 'GET /booking/confirmation/<int:booking_id>', 'confirmation read'),
        ),
    ),
    # ── public booking ───────────────────────────────────────────────────
    Template(
        key='READ_BOOKING_SLOT_AVAILABILITY',
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
            'Slot availability is read three times by the booking flow: available '
            'doctors, available times, and the smart-slots endpoint that combines them '
            'into a suggestion. Each is computed independently from the Appointment '
            'table, so the combination can offer a slot that the plain availability '
            'endpoint already knows is taken.'
        ),
        steps=(
            _s(RECEPTION, 'POST /reception/create_appointment', 'appointment booked'),
            _s(RECEPTION, 'GET /booking/api/available-doctors', 'doctors read'),
            _s(RECEPTION, 'GET /booking/api/available-times', 'times read'),
            _s(RECEPTION, 'GET /booking/api/smart-slots', 'suggestion read'),
            _s(RECEPTION, 'GET /booking/dashboard', 'booking dashboard read'),
            _s(
                RECEPTION,
                'GET /booking/telemedicine/<int:booking_id>',
                'teleconsultation room read',
            ),
        ),
    ),
    # ── clinical coding ──────────────────────────────────────────────────
    Template(
        key='READ_CLINICAL_CODING_LOOKUPS',
        family='clinical',
        axes=('diagnosis_type',),
        observed={'diagnosis_type': ('PRIMARY', 'SECONDARY', 'ADMITTING', 'DISCHARGE')},
        rule=(
            'The coding tables are reference data rather than patient data, but the '
            'patient-diagnoses and patient-procedures routes attach codes to a record, '
            'and they are the only place a coded diagnosis can be read back. A code '
            'that exists in the reference table but was never written to the encounter '
            'is therefore invisible here.'
        ),
        steps=(
            _s(DOCTOR, 'POST /doctor/diagnosis/<int:visit_id>', 'coded diagnosis written'),
            _s(DOCTOR, 'GET /clinical-coding/icd10', 'ICD-10 list read'),
            _s(DOCTOR, 'GET /clinical-coding/icd10/<int:id>', 'ICD-10 detail read'),
            _s(DOCTOR, 'GET /clinical-coding/api/icd10/search', 'ICD-10 search read'),
            _s(DOCTOR, 'GET /clinical-coding/cpt', 'CPT list read'),
            _s(DOCTOR, 'GET /clinical-coding/api/cpt/search', 'CPT search read'),
            _s(
                DOCTOR,
                'GET /clinical-coding/patient/<int:patient_id>/diagnoses',
                'patient diagnoses read',
            ),
            _s(
                DOCTOR,
                'GET /clinical-coding/patient/<int:patient_id>/procedures',
                'patient procedures read',
            ),
        ),
    ),
    # ── quality and security ─────────────────────────────────────────────
    Template(
        key='READ_QUALITY_DASHBOARD',
        family='clinical',
        axes=('log_level',),
        observed={'log_level': ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')},
        rule=(
            'Quality incidents and quality audits are two different records with two '
            'different lifecycles, and neither has a write route in the application: '
            'they are populated from outside. The dashboard is therefore a read over '
            'tables this codebase cannot change, which is why its coverage here is a '
            'rendering assertion rather than a behavioural one.'
        ),
        steps=(
            _s(SUPER_ADMIN, 'GET /quality/dashboard', 'quality dashboard read'),
            _s(
                DOCTOR,
                'POST /doctor/notes/<int:visit_id>',
                'the clinical event the metrics aggregate',
            ),
            _s(SUPER_ADMIN, 'GET /quality/incidents', 'incidents read'),
            _s(SUPER_ADMIN, 'GET /quality/audits', 'audits read'),
            _s(SUPER_ADMIN, 'GET /quality/api/quality-metrics', 'metrics API read'),
        ),
    ),
    Template(
        key='READ_SECURITY_SURFACES',
        family='rbac',
        axes=('security_event_type',),
        observed={
            'security_event_type': (
                'login_failed',
                'password_changed',
                'permission_denied',
                'suspicious_activity',
                'data_breach',
                'unauthorized_access',
            )
        },
        rule=(
            'The sessions page is the only read that lists live sessions, and it is '
            'therefore the read an operator uses to find a session that force_logout '
            'would have closed. The signatures and password-policy pages are reference '
            'reads, and the policy page is what a UI would validate against even though '
            'the server validates separately.'
        ),
        steps=(
            _s(SUPER_ADMIN, 'POST /auth/login', 'session opened'),
            _s(SUPER_ADMIN, 'GET /security/sessions', 'sessions read'),
            _s(SUPER_ADMIN, 'GET /security/password-policy', 'password policy read'),
            _s(SUPER_ADMIN, 'GET /security/signatures', 'signature page read'),
        ),
    ),
    # ── what-if and integrations ─────────────────────────────────────────
    Template(
        key='READ_WHAT_IF_SCENARIO_MODELLING',
        family='financial',
        axes=('payment_method',),
        observed={'payment_method': ('CASH', 'CARD', 'visa', 'mada', 'WIRE', 'INSURANCE', 'FORCE')},
        rule=(
            'A what-if scenario is a stored projection, so the list and the detail are '
            'two reads of a saved model rather than a computation. The projection is '
            'recomputed from the current assumptions when it is read, which means the '
            'same scenario id can return a different figure after an assumption is '
            'revoked.'
        ),
        steps=(
            _s(MANAGER, 'POST /what-if/new', 'scenario modelled'),
            _s(MANAGER, 'GET /what-if/', 'scenario list read'),
            _s(MANAGER, 'GET /what-if/<int:scenario_id>', 'scenario detail read'),
        ),
    ),
    Template(
        key='READ_FHIR_AND_INTEROPERABILITY_SURFACES',
        family='clinical',
        axes=('hl7_message_type',),
        observed={'hl7_message_type': ('ADT', 'ORM', 'ORU', 'SIU', 'VXU')},
        rule=(
            'The FHIR reads on the reception blueprint serve five different resource '
            'types from one id space per type, so a request that mixes them is not '
            'possible by construction. Each returns a single resource with no bundle '
            'and no search, so an integrator that needs a list has to know the ids.'
        ),
        steps=(
            _s(RECEPTION, 'POST /reception/visits/create', 'visit created to expose a resource'),
            _s(
                RECEPTION,
                'GET /reception/api/fhir/patient/<int:patient_id>',
                'patient resource read',
            ),
            _s(
                RECEPTION,
                'GET /reception/api/fhir/encounter/<int:visit_id>',
                'encounter resource read',
            ),
            _s(
                RECEPTION,
                'GET /reception/api/fhir/appointment/<int:appointment_id>',
                'appointment resource read',
            ),
            _s(
                RECEPTION,
                'GET /reception/api/fhir/practitioner/<int:user_id>',
                'practitioner resource read',
            ),
            _s(
                RECEPTION,
                'GET /reception/api/fhir/organization/<int:department_id>',
                'organization resource read',
            ),
        ),
    ),
    # ── owner console ────────────────────────────────────────────────────
    Template(
        key='READ_OWNER_TENANT_DIRECTORY',
        family='platform',
        axes=('tenant_status',),
        observed={
            'tenant_status': (
                'active',
                'suspended',
                'pending',
                'trial',
                'expired',
                'cancelled',
                'deleted',
            )
        },
        rule=(
            'The owner console reads tenants three ways: the human list, the API list, '
            'and the per-tenant usage page. The limits and modules endpoints are reads '
            'too, which is unusual: they return the same rows the entitlement write '
            'touches, so a limit displayed here is a live configuration value and not a '
            'derived one.'
        ),
        steps=(
            _s(OWNER, 'POST /owner/tenants/create', 'tenant created'),
            _s(OWNER, 'GET /owner/tenants/', 'tenant list read'),
            _s(OWNER, 'GET /owner/api/tenants', 'tenant API list read'),
            _s(OWNER, 'GET /owner/api/tenants/<int:tenant_id>/limits', 'limits read'),
            _s(OWNER, 'GET /owner/api/tenants/<int:tenant_id>/modules', 'entitlement read'),
            _s(OWNER, 'GET /owner/tenant-usage/<int:tenant_id>', 'usage read'),
            _s(OWNER, 'GET /owner/users-list', 'user list read'),
        ),
    ),
    Template(
        key='READ_OWNER_PLATFORM_OBSERVABILITY',
        family='platform',
        axes=('log_level',),
        observed={'log_level': ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')},
        rule=(
            'The observability reads split across four tables that no route relates to '
            'each other: the audit log, the error audit log, the error log and the '
            'system log. The monitoring page is the only read that joins them, so a '
            'count on the dashboard cannot be reconciled against any single list it was '
            'built from.'
        ),
        steps=(
            _s(OWNER, 'POST /owner/tenants/create', 'tenant activity to observe'),
            _s(OWNER, 'GET /owner/monitoring', 'monitoring read'),
            _s(OWNER, 'GET /owner/audit-logs', 'audit log read'),
            _s(OWNER, 'GET /owner/error-audit-logs', 'error audit log read'),
            _s(OWNER, 'GET /owner/error-logs', 'error log read'),
            _s(OWNER, 'GET /owner/system-stats', 'system stats read'),
            _s(OWNER, 'GET /owner/resource-usage', 'resource usage read'),
            _s(OWNER, 'GET /owner/tasks', 'tasks read'),
        ),
    ),
    Template(
        key='READ_OWNER_BILLING_AND_VAULT',
        family='platform',
        axes=('subscription_type',),
        observed={'subscription_type': ('perpetual', 'monthly', 'yearly')},
        rule=(
            'The billing page, the payment vault and the cards vault are three reads of '
            'the platform side of money, and they are tenant revenue rather than '
            'patient money. The cards vault is a GET that returns stored payment '
            'instruments, which makes it the single highest-value read on this console '
            'and the one whose audit is only the list it appears in.'
        ),
        steps=(
            _s(OWNER, 'POST /owner/subscriptions/<int:tenant_id>/renew', 'subscription renewed'),
            _s(OWNER, 'GET /owner/billing', 'billing page read'),
            _s(OWNER, 'GET /owner/payment-vault', 'payment vault read'),
            _s(OWNER, 'GET /owner/cards-vault', 'cards vault read'),
            _s(OWNER, 'GET /owner/resource-usage', 'usage read'),
        ),
    ),
    Template(
        key='READ_OWNER_CONFIGURATION_AND_INTEGRATIONS',
        family='platform',
        axes=('config_category',),
        observed={
            'config_category': (
                'general',
                'security',
                'notification',
                'backup',
                'system',
                'database',
                'email',
                'sms',
            )
        },
        rule=(
            'The system-config page is the read side of the same rows the save route '
            'writes, and the integrations page is the read side of the same credentials '
            'the webhook and SSO routes use. Reading a config is therefore how a password '
            'typed row is confirmed saved, and the redaction is the only thing standing '
            'between that page and a credential.'
        ),
        steps=(
            _s(OWNER, 'POST /owner/system-config/save', 'configuration saved'),
            _s(OWNER, 'GET /owner/system-config', 'configuration read back'),
            _s(OWNER, 'GET /owner/integrations', 'integrations read'),
            _s(OWNER, 'GET /owner/company-info', 'company info read'),
            _s(OWNER, 'GET /owner/notifications', 'notification rules read'),
            _s(OWNER, 'GET /owner/reports', 'reports read'),
            _s(OWNER, 'GET /owner/backups', 'backups read'),
            _s(OWNER, 'GET /owner/emergency-switches', 'emergency switches read'),
            _s(OWNER, 'GET /owner/control', 'control page read'),
        ),
    ),
    # ── super-admin console ──────────────────────────────────────────────
    Template(
        key='READ_SUPERADMIN_CATALOGUE_AND_PRICING',
        family='platform',
        axes=('module_name',),
        observed={
            'module_name': (
                'reception',
                'doctor',
                'lab',
                'radiology',
                'pharmacy',
                'emergency',
                'nursing',
                'billing',
                'inventory',
                'reporting',
                'appointments',
                'owner',
                'portal',
                'ai_imaging',
                'accounting',
                'admin',
                'manager',
                'dicom',
            )
        },
        rule=(
            'The catalogue is read as a list and as a detail, and the detail routes take '
            'a department or a service id rather than the session, so one operator can '
            'read any row. Pricing is a fourth read that joins the catalogue to the '
            'ledger, which is why a price shown here can differ from the price a visit '
            'was actually charged.'
        ),
        steps=(
            _s(SUPER_ADMIN, 'POST /super-admin/services/create', 'service created'),
            _s(SUPER_ADMIN, 'POST /super-admin/departments/create', 'department created'),
            _s(SUPER_ADMIN, 'GET /super-admin/services', 'service list read'),
            _s(SUPER_ADMIN, 'GET /super-admin/service/<int:service_id>', 'service detail read'),
            _s(SUPER_ADMIN, 'GET /super-admin/departments', 'department list read'),
            _s(
                SUPER_ADMIN,
                'GET /super-admin/department/<int:department_id>',
                'department detail read',
            ),
            _s(
                SUPER_ADMIN,
                'GET /super-admin/department-staff/<int:department_id>',
                'department staff read',
            ),
            _s(SUPER_ADMIN, 'GET /super-admin/pricing', 'pricing read'),
        ),
    ),
    Template(
        key='READ_SUPERADMIN_SECURITY_SURFACES',
        family='platform',
        axes=('security_event_type',),
        observed={
            'security_event_type': (
                'login_failed',
                'password_changed',
                'permission_denied',
                'suspicious_activity',
                'data_breach',
                'unauthorized_access',
            )
        },
        rule=(
            'The security-logs list and the security-summary endpoint are two reads over '
            'the same table with different shapes, and the summary is what an alert would '
            'be built from. A ban and an unban are writes but a force-logout is a write '
            'with no history, so the logs show a session ending rather than an operator '
            'ending it.'
        ),
        steps=(
            _s(SUPER_ADMIN, 'POST /super-admin/users/<int:user_id>/edit', 'account activity'),
            _s(SUPER_ADMIN, 'GET /super-admin/security-logs', 'security log read'),
            _s(SUPER_ADMIN, 'GET /super-admin/api/security-logs/summary', 'security summary read'),
            _s(SUPER_ADMIN, 'GET /super-admin/users', 'user list read'),
            _s(SUPER_ADMIN, 'GET /super-admin/permissions', 'permission list read'),
            _s(SUPER_ADMIN, 'GET /super-admin/api/recent-activities', 'recent activity read'),
        ),
    ),
    Template(
        key='READ_SUPERADMIN_SYSTEM_AND_BACKUP_VIEWS',
        family='platform',
        axes=('backup_status',),
        observed={'backup_status': ('PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'CANCELLED')},
        rule=(
            'The backup surface is four separate reads: the current job, the history, '
            'the report and the log export. A job that is IN_PROGRESS appears in the '
            'current view and not in the history, so a failed job can be invisible in the '
            'one place an operator would look for it.'
        ),
        steps=(
            _s(SUPER_ADMIN, 'POST /super-admin/backup/create', 'backup taken'),
            _s(SUPER_ADMIN, 'GET /super-admin/backup', 'current backup read'),
            _s(SUPER_ADMIN, 'GET /super-admin/backup/history', 'history read'),
            _s(SUPER_ADMIN, 'GET /super-admin/backup/report', 'backup report read'),
            _s(SUPER_ADMIN, 'GET /super-admin/backup/export-logs', 'backup logs exported'),
            _s(SUPER_ADMIN, 'GET /super-admin/system-backup', 'system backup view read'),
        ),
    ),
    Template(
        key='READ_SUPERADMIN_OPERATIONS_SURFACES',
        family='platform',
        axes=('log_level',),
        observed={'log_level': ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')},
        rule=(
            'The operations surface is the monitoring, performance, maintenance and '
            'system pages, and each reads a different table with no shared index. The '
            'warehouse export and the generic download route are the two reads that '
            'leave the platform, and the download route takes a filename as a path '
            'parameter rather than an id.'
        ),
        steps=(
            _s(SUPER_ADMIN, 'POST /super-admin/system/cleanup', 'cleanup run'),
            _s(SUPER_ADMIN, 'GET /super-admin/system', 'system page read'),
            _s(SUPER_ADMIN, 'GET /super-admin/system-monitor', 'monitor read'),
            _s(SUPER_ADMIN, 'GET /super-admin/performance', 'performance read'),
            _s(SUPER_ADMIN, 'GET /super-admin/system/maintenance', 'maintenance read'),
            _s(SUPER_ADMIN, 'GET /super-admin/data-warehouse', 'warehouse read'),
            _s(SUPER_ADMIN, 'GET /super-admin/data-warehouse/export', 'warehouse exported'),
            _s(SUPER_ADMIN, 'GET /super-admin/analytics', 'analytics read'),
            _s(SUPER_ADMIN, 'GET /super-admin/reports', 'reports read'),
        ),
    ),
    Template(
        key='READ_SUPERADMIN_BRANDING_AND_SUBSCRIPTION',
        family='platform',
        axes=('module_status',),
        observed={
            'module_status': {
                'enabled': 'the tenant module row is left enabled, so the branding preview '
                'is what a tenant with the module would actually see',
                'disabled': 'the tenant module row is left disabled, so the branding preview '
                'renders for a surface the tenant cannot reach',
            }
        },
        rule=(
            'Branding, its print preview and the subscription status are three reads of '
            'what a tenant will see. The preview renders the theme without a tenant '
            'context, so it can show a branding that no tenant actually has applied, '
            'which is useful for design review and misleading as a statement of fact.'
        ),
        steps=(
            _s(
                SUPER_ADMIN,
                'POST /super-admin/branding/apply-theme/<int:theme_id>',
                'theme applied',
            ),
            _s(SUPER_ADMIN, 'GET /super-admin/branding', 'branding read'),
            _s(SUPER_ADMIN, 'GET /super-admin/branding/preview', 'branding previewed'),
            _s(SUPER_ADMIN, 'GET /super-admin/subscription-status', 'subscription status read'),
            _s(SUPER_ADMIN, 'GET /super-admin/usage', 'usage read'),
            _s(SUPER_ADMIN, 'GET /super-admin/dashboard', 'dashboard read'),
        ),
    ),
    # ── remaining clinical blueprints ───────────────────────────────────
    Template(
        key='READ_DICOM_STUDY_BROWSER',
        family='clinical',
        axes=('dicom_study_status',),
        observed={
            'dicom_study_status': (
                'RECEIVED',
                'PENDING_REVIEW',
                'REVIEWED',
                'REPORTED',
                'ARCHIVED',
            )
        },
        rule=(
            'DICOM is the only surface where the application reads objects it did not '
            'create, and the study status is advanced by no route at all, so a study can '
            'sit at RECEIVED forever while the radiology console shows the report it '
            'belongs to. The viewer and the study detail are two reads of the same '
            'object with different authorisation.'
        ),
        steps=(
            _s(DOCTOR, 'POST /doctor/radiology-request/<int:visit_id>', 'imaging requested'),
            _s(RADIOLOGY, 'POST /api/radiology/results/<int:result_id>/amend', 'report written'),
            _s(RADIOLOGY, 'GET /dicom/studies', 'study list read'),
            _s(RADIOLOGY, 'GET /dicom/study/<int:study_id>', 'study detail read'),
            _s(RADIOLOGY, 'GET /dicom/viewer/<int:study_id>', 'viewer opened'),
            _s(RADIOLOGY, 'GET /dicom/api/worklist', 'worklist read'),
            _s(
                RADIOLOGY, 'GET /dicom/api/studies/patient/<int:patient_id>', 'patient studies read'
            ),
            _s(
                RADIOLOGY,
                'GET /dicom/api/worklist/patient/<int:patient_id>',
                'patient worklist read',
            ),
        ),
    ),
    Template(
        key='READ_SPECIALTY_FORMS_AND_SUBMISSIONS',
        family='clinical',
        axes=('workflow_status',),
        observed={'workflow_status': ('active', 'completed', 'cancelled', 'transferred')},
        rule=(
            'A form and a submission are separate records, and the submissions list is '
            'per form while the submission detail is by submission id. Publishing a '
            'version does not create a submission, so a published form with no '
            'submissions is indistinguishable on the read side from a form nobody has '
            'used.'
        ),
        steps=(
            _s(DOCTOR, 'POST /specialty-forms/new', 'form drafted'),
            _s(DOCTOR, 'POST /specialty-forms/<int:form_id>/fill', 'form filled'),
            _s(DOCTOR, 'GET /specialty-forms', 'form list read'),
            _s(DOCTOR, 'GET /specialty-forms/<int:form_id>', 'form detail read'),
            _s(DOCTOR, 'GET /specialty-forms/<int:form_id>/submissions', 'submission list read'),
            _s(DOCTOR, 'GET /specialty-forms/submissions/<int:submission_id>', 'submission read'),
        ),
    ),
    Template(
        key='READ_BED_MANAGEMENT_AND_ADMISSIONS',
        family='clinical',
        axes=('bed_status',),
        observed={'bed_status': ('AVAILABLE', 'OCCUPIED', 'RESERVED', 'CLEANING', 'OUT_OF_ORDER')},
        rule=(
            'The bed status API, the admissions list and the dashboard are three reads '
            'over the same occupancy, and OUT_OF_ORDER is not an occupancy, so a count '
            'of occupied beds and a count of unavailable beds do not partition the same '
            'set unless OUT_OF_ORDER is subtracted explicitly on both sides.'
        ),
        steps=(
            _s(NURSE, 'POST /bed/api/admissions/admit', 'admission opened'),
            _s(NURSE, 'GET /bed/api/bed-status', 'bed status read'),
            _s(NURSE, 'GET /bed/admissions', 'admission list read'),
            _s(NURSE, 'GET /bed/dashboard', 'bed dashboard read'),
        ),
    ),
    Template(
        key='READ_CLINICAL_DECISION_SUPPORT',
        family='clinical',
        axes=('drug_interaction_severity',),
        observed={'drug_interaction_severity': ('LOW', 'MODERATE', 'HIGH')},
        rule=(
            'The alert surface is three reads: the rule catalogue, the alerts raised for '
            'the tenant, and the alerts raised for one patient. The rule table carries '
            'no tenant_id, so a rule written for one tenant fires in every other, which '
            'is why the rule list and the alert list can disagree about what is enabled.'
        ),
        steps=(
            _s(PHARMACY, 'POST /medication/add', 'drug added to screen against'),
            _s(DOCTOR, 'GET /cds/rules', 'rule catalogue read'),
            _s(DOCTOR, 'GET /cds/alerts', 'alert list read'),
            _s(DOCTOR, 'GET /cds/patient/<int:patient_id>/alerts', 'patient alerts read'),
        ),
    ),
    Template(
        key='READ_CARE_PATHWAYS',
        family='clinical',
        axes=('problem_status',),
        observed={
            'problem_status': (
                'ACTIVE',
                'CHRONIC',
                'RESOLVED',
                'RELAPSE',
                'IN_REMISSION',
                'RULED_OUT',
            )
        },
        rule=(
            'Pathways are templates and a care plan is a patient instance of one, so the '
            'pathway detail and the patient care-plan list are reads of different '
            'tables. A problem marked RULED_OUT stays on the chart and does not remove '
            'the plan it produced, so the care plan list can describe work for a '
            'condition that has been excluded.'
        ),
        steps=(
            _s(DOCTOR, 'POST /doctor/diagnosis/<int:visit_id>', 'diagnosis recorded'),
            _s(DOCTOR, 'GET /pathway/pathways', 'pathway list read'),
            _s(DOCTOR, 'GET /pathway/pathway/<int:pathway_id>', 'pathway detail read'),
            _s(
                DOCTOR,
                'GET /pathway/patient/<int:patient_id>/care-plans',
                'patient care plans read',
            ),
        ),
    ),
    Template(
        key='READ_POPULATION_HEALTH_AND_REGISTRY',
        family='clinical',
        axes=('diagnosis_status',),
        observed={'diagnosis_status': ('ACTIVE', 'RESOLVED', 'CHRONIC', 'RELAPSE')},
        rule=(
            'Population health aggregates across patients rather than showing one, and '
            'the disease registry and the quality-measures page are two independent '
            'aggregations over the same diagnoses. The dashboard is a third, so the '
            'three can carry different denominators for the same condition.'
        ),
        steps=(
            _s(
                DOCTOR, 'POST /doctor/diagnosis/<int:visit_id>', 'the diagnosis the registry counts'
            ),
            _s(SUPER_ADMIN, 'POST /super-admin/seed/users', 'population seeded'),
            _s(SUPER_ADMIN, 'GET /population-health/dashboard', 'population dashboard read'),
            _s(SUPER_ADMIN, 'GET /population-health/disease-registry', 'disease registry read'),
            _s(SUPER_ADMIN, 'GET /population-health/quality-measures', 'quality measures read'),
        ),
    ),
    Template(
        key='READ_REFERRAL_TRACKING',
        family='clinical',
        axes=('referral_status',),
        observed={
            'referral_status': (
                'PENDING',
                'SENT',
                'ACCEPTED',
                'SCHEDULED',
                'COMPLETED',
                'CANCELLED',
                'DECLINED',
            )
        },
        rule=(
            'Referrals are read-only in the application: there is no create route, so '
            'the list can only ever show rows something else wrote. A referral in '
            'PENDING is the state no route in this codebase can leave it in, which is '
            'the clearest single fact about the referral feature.'
        ),
        steps=(
            _s(
                DOCTOR,
                'POST /doctor/diagnosis/<int:visit_id>',
                'encounter that would need a referral',
            ),
            _s(DOCTOR, 'GET /referral/list', 'referral list read'),
            _s(DOCTOR, 'GET /referral/detail/<int:referral_id>', 'referral detail read'),
        ),
    ),
    Template(
        key='READ_OPERATING_ROOM_SURGICAL_RECORDS',
        family='clinical',
        axes=('surgery_status',),
        observed={
            'surgery_status': (
                'SCHEDULED',
                'CONFIRMED',
                'IN_PROGRESS',
                'COMPLETED',
                'CANCELLED',
                'DELAYED',
            )
        },
        rule=(
            'The operating room is the one clinical blueprint with a detail read and no '
            'write at all, so the surgery detail is the only way this codebase can show '
            'a theatre case. DELAYED is a status the enum defines and no route can write, '
            'so it appears here only if something outside the application wrote it.'
        ),
        steps=(
            _s(DOCTOR, 'POST /doctor/notes/<int:visit_id>', 'operative note recorded'),
            _s(NURSE, 'POST /handover/open', 'theatre handover opened'),
            _s(DOCTOR, 'GET /or/surgery/<int:surgery_id>', 'surgery detail read'),
        ),
    ),
    Template(
        key='READ_HANDOVER_AND_NURSING_ASSESSMENT',
        family='clinical',
        axes=('task_state',),
        observed={'task_state': ('pending', 'in_progress', 'completed', 'cancelled')},
        rule=(
            'The handover dashboard and the nursing-assessment dashboard aggregate the '
            'two records a shift produces, and neither has a write beyond the shift and '
            'the assessment itself. A handover sheet that was opened and never closed '
            'stays on the dashboard as current, which is the state that actually loses '
            'information.'
        ),
        steps=(
            _s(NURSE, 'POST /handover/open', 'shift opened'),
            _s(NURSE, 'POST /nursing-assessment/new/<int:patient_id>', 'assessment recorded'),
            _s(NURSE, 'GET /handover/', 'handover dashboard read'),
            _s(NURSE, 'GET /nursing-assessment/dashboard', 'assessment dashboard read'),
        ),
    ),
    Template(
        key='READ_KIOSK_AND_BARCODE_REGISTRY',
        family='clinical',
        axes=('queue_state',),
        observed={
            'queue_state': ('waiting', 'called', 'in_progress', 'completed', 'skipped', 'cancelled')
        },
        rule=(
            'The kiosk check-in and the barcode scan page are the two unauthenticated '
            'reads a patient can reach, so they are the only clinical surfaces with no '
            'session behind them. The registry behind them lists every issued label, '
            'which is a read of identifiers rather than of patients.'
        ),
        steps=(
            _s(RECEPTION, 'POST /reception/queue/add-patient', 'ticket raised'),
            _s(RECEPTION, 'GET /barcode/scan', 'scan page read'),
            _s(RECEPTION, 'GET /barcode/registry', 'label registry read'),
            _s(RECEPTION, 'GET /kiosk/check-in', 'kiosk page read'),
        ),
    ),
    Template(
        key='READ_AI_IMAGING_CONSOLE',
        family='clinical',
        axes=('radiology_result_status',),
        observed={'radiology_result_status': ('PENDING', 'READY', 'VALIDATED')},
        rule=(
            'The AI imaging console is one list read, and the request and review routes '
            'that populate it are the only writes. Because the review is what records '
            'that a clinician saw the suggestion, an unreviewed request and a reviewed '
            'one differ by a timestamp and nothing else on the list.'
        ),
        steps=(
            _s(RADIOLOGY, 'POST /ai-imaging/request', 'AI read requested'),
            _s(RADIOLOGY, 'POST /ai-imaging/<int:ai_id>/review', 'clinician reviewed'),
            _s(RADIOLOGY, 'GET /ai-imaging/', 'console read'),
        ),
    ),
    Template(
        key='READ_LANDING_AND_ACCOUNT_PAGES',
        family='rbac',
        axes=('actor_role',),
        observed={
            'actor_role': (
                'super_admin',
                'owner',
                'admin',
                'manager',
                'reception',
                'doctor',
                'nurse',
                'lab',
                'radiology',
                'pharmacist',
                'accountant',
            )
        },
        rule=(
            'The root dashboard, settings and the appointments redirect are the three '
            'reads every session lands on, so a defect in any of them is the first thing '
            'a user sees. The root itself is package-restricted: a tenant without the '
            'module lands on package-restricted instead, which is a page rather than a '
            'redirect.'
        ),
        steps=(
            _s(RECEPTION, 'POST /reception/visits/create', 'visit created'),
            _s(RECEPTION, 'GET /', 'root read'),
            _s(RECEPTION, 'GET /dashboard', 'dashboard read'),
            _s(RECEPTION, 'GET /appointments', 'appointments redirect read'),
            _s(RECEPTION, 'GET /settings', 'settings read'),
            _s(RECEPTION, 'GET /package-restricted', 'restricted page read'),
        ),
    ),
    Template(
        key='READ_PUBLIC_INFORMATION_PAGES',
        family='rbac',
        axes=('actor_role',),
        observed={'actor_role': ('super_admin', 'owner', 'admin', 'manager', 'reception')},
        rule=(
            'The about, terms, privacy and support pages are unauthenticated reads, and '
            'the tenant search endpoint is unauthenticated too, which is what makes the '
            'tenant list enumerable from outside. The health check is the only read in '
            'the application that is safe to expose by design.'
        ),
        steps=(
            _s(PATIENT, 'GET /', 'root read without a session'),
            _s(PATIENT, 'GET /about-system', 'about page read'),
            _s(PATIENT, 'GET /terms-of-use', 'terms read'),
            _s(PATIENT, 'GET /privacy-policy', 'privacy read'),
            _s(PATIENT, 'GET /technical-support', 'support read'),
            _s(PATIENT, 'GET /api/tenants/search', 'tenant search exercised'),
            _s(SUPER_ADMIN, 'GET /health', 'health check read'),
        ),
    ),
    Template(
        key='READ_GLOBAL_SEARCH',
        family='rbac',
        axes=('actor_role',),
        observed={'actor_role': ('reception', 'doctor', 'nurse', 'manager', 'admin')},
        rule=(
            'The global search is the widest read in the application: one query across '
            'patients, visits and appointments, returning whatever the role of the caller '
            'allows. Because the results span three id spaces in one list, it is the read '
            'where a row from the wrong entity type is hardest for a user to notice.'
        ),
        steps=(
            _s(RECEPTION, 'POST /reception/add_patient', 'patient registered'),
            _s(RECEPTION, 'POST /reception/visits/create', 'visit created'),
            _s(RECEPTION, 'GET /api/search', 'global search exercised'),
        ),
    ),
    Template(
        key='READ_FHIR_BUNDLE_ENDPOINTS',
        family='clinical',
        axes=('actor_role',),
        observed={'actor_role': ('doctor', 'reception', 'nurse', 'manager', 'admin')},
        rule=(
            'These four are the only reads that return a FHIR bundle rather than a '
            'single resource, and the two list endpoints are searches with no '
            'pagination parameters declared, so an integrator asking for a large tenant '
            'gets whatever the default page size happens to be.'
        ),
        steps=(
            _s(RECEPTION, 'POST /reception/add_patient', 'patient registered'),
            _s(RECEPTION, 'POST /reception/visits/create', 'visit created'),
            _s(DOCTOR, 'GET /api/fhir/Patient', 'patient bundle read'),
            _s(DOCTOR, 'GET /api/fhir/Patient/<int:patient_id>', 'single patient read'),
            _s(DOCTOR, 'GET /api/fhir/Encounter', 'encounter bundle read'),
            _s(DOCTOR, 'GET /api/fhir/Observation', 'observation bundle read'),
        ),
    ),
    Template(
        key='READ_IHE_PATIENT_AND_DOCUMENT_QUERIES',
        family='clinical',
        axes=('hl7_message_type',),
        observed={'hl7_message_type': ('ADT', 'ORM', 'ORU', 'SIU', 'VXU')},
        rule=(
            'The IHE PDQ and PIX queries are patient lookup services for a federated '
            'network, and both are reads that return matching patient demographics to a '
            'caller outside this tenant. They are the widest read boundary in the system '
            'and they are protected by the blueprint rather than by a filter on the rows.'
        ),
        steps=(
            _s(RECEPTION, 'POST /reception/add_patient', 'patient registered'),
            _s(SUPER_ADMIN, 'GET /ihe/pix/query', 'PIX query exercised'),
            _s(SUPER_ADMIN, 'GET /ihe/pdq/query', 'PDQ query exercised'),
        ),
    ),
    Template(
        key='READ_PROCUREMENT_AND_SUPPLIER_VIEWS',
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
            'The procurement list is the only read on the purchasing side, and it reads '
            'the purchases rather than the suppliers, so a supplier with no purchase '
            'history does not appear on it at all. The supplier list is the other read, '
            'and neither one shows the movement ledger that both are derived from.'
        ),
        steps=(
            _s(MANAGER, 'POST /medication/purchases/add', 'purchase recorded'),
            _s(MANAGER, 'GET /procurement/', 'purchase list read'),
            _s(MANAGER, 'GET /medication/suppliers', 'supplier list read'),
        ),
    ),
    Template(
        key='READ_PWA_AND_METRICS_SURFACES',
        family='rbac',
        axes=('actor_role',),
        observed={'actor_role': ('super_admin', 'owner', 'admin', 'manager')},
        rule=(
            'The service worker manifest and the offline page are the only reads the '
            'browser makes without a session, and the metrics endpoint is the only read '
            'that exposes process-level numbers. Each is public by design, which is why '
            'the metrics route carries the same exposure risk as the health check and '
            'usually a larger one.'
        ),
        steps=(
            _s(SUPER_ADMIN, 'GET /pwa/manifest.webmanifest', 'manifest read'),
            _s(SUPER_ADMIN, 'GET /pwa/offline', 'offline page read'),
            _s(SUPER_ADMIN, 'GET /metrics', 'metrics read'),
            _s(SUPER_ADMIN, 'GET /health', 'health check read'),
        ),
    ),
    # ── diagnostic and error surfaces ────────────────────────────────────
    Template(
        key='READ_DIAGNOSTIC_SURFACES_REVEAL_IDENTITY',
        family='rbac',
        axes=('login_outcome',),
        observed={
            'login_outcome': (
                'success',
                'bad_password',
                'unknown_user',
                'disabled_user',
                'locked_out',
            )
        },
        rule=(
            'The ghost-mode diagnostic route is registered with no authentication and '
            'is on the tenant middleware exemption list, so it answers an anonymous '
            'caller with the resolved tenant id, the session user id and the username. '
            'It exists to debug the ghost-mode signature path, and as written it is an '
            'identity disclosure endpoint reachable without a credential.'
        ),
        steps=(
            _s(PATIENT, 'GET /_ghost_whoami', 'identity resolved for an anonymous caller'),
            _s(
                SUPER_ADMIN,
                'GET /security/sessions',
                'sessions compared against what was disclosed',
            ),
            _s(SUPER_ADMIN, 'GET /mfa/status', 'mfa status read'),
            _s(SUPER_ADMIN, 'GET /auth/api/tenants-list', 'tenant list read through the auth API'),
        ),
    ),
    Template(
        key='READ_ERROR_TRIGGER_ROUTES',
        family='rbac',
        axes=(),
        observed={},
        rule=(
            'Six routes exist only to raise an error: permission, tenant-context, '
            'tenant-isolation, idempotency and module failures, each in a JSON and an '
            'HTML form. They are the only place the error handlers are exercised '
            'against real requests, and each one asserts that the handler returns the '
            'right status and does not leak the exception. The HTML variants are the '
            'riskier pair, because a template that renders an exception renders it to '
            'a browser.'
        ),
        steps=(
            _s(SUPER_ADMIN, 'GET /test/perm-error', 'permission error path exercised'),
            _s(SUPER_ADMIN, 'GET /test/tenant-ctx-error', 'tenant context error path exercised'),
            _s(SUPER_ADMIN, 'GET /test/tenant-iso-error', 'tenant isolation error path exercised'),
            _s(SUPER_ADMIN, 'GET /test/idempotency-error', 'idempotency error path exercised'),
            _s(
                SUPER_ADMIN,
                'GET /test/idempotency-error-html',
                'idempotency error rendered as HTML',
            ),
            _s(SUPER_ADMIN, 'GET /test/module-error', 'module error path exercised'),
            _s(SUPER_ADMIN, 'GET /test/module-error-html', 'module error rendered as HTML'),
        ),
    ),
    Template(
        key='READ_TRACE_AND_STATUS_ROUTES',
        family='rbac',
        axes=('log_level',),
        observed={'log_level': ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')},
        rule=(
            'The trace and status routes are the diagnostic surface: a log-trace read, '
            'a g-trace read, the HL7 channel status and the health check. Each returns '
            'information about the running process rather than about a patient, and '
            'each is unauthenticated, so what they expose is the question rather than '
            'the content.'
        ),
        steps=(
            _s(SUPER_ADMIN, 'GET /test/log-trace', 'log trace exercised'),
            _s(SUPER_ADMIN, 'GET /test/g-trace', 'g-trace exercised'),
            _s(SUPER_ADMIN, 'GET /hl7/status', 'interface channel status read'),
            _s(SUPER_ADMIN, 'GET /__health', 'liveness read'),
            _s(SUPER_ADMIN, 'GET /health', 'health check read'),
        ),
    ),
    Template(
        key='READ_ROOT_LEVEL_SHORTCUTS',
        family='clinical',
        axes=('actor_role',),
        observed={'actor_role': ('reception', 'doctor', 'nurse', 'manager', 'admin')},
        rule=(
            'Three patient-list routes are registered at the application root rather '
            'than under a blueprint: /patients, /visits and /medications. They are the '
            'widest read paths in the system, each returning a tenant-wide list, and '
            'the root namespace is also where the unauthenticated diagnostic routes '
            'live.'
        ),
        steps=(
            _s(RECEPTION, 'POST /reception/add_patient', 'patient registered'),
            _s(RECEPTION, 'POST /reception/visits/create', 'visit created'),
            _s(RECEPTION, 'GET /patients', 'root patient list read'),
            _s(RECEPTION, 'GET /visits', 'root visit list read'),
            _s(RECEPTION, 'GET /medications', 'root medication list read'),
        ),
    ),
    Template(
        key='READ_DASHBOARD_SNAPSHOT_AND_PATIENT_SEARCH_API',
        family='clinical',
        axes=('actor_role',),
        observed={'actor_role': ('reception', 'doctor', 'nurse', 'manager', 'admin')},
        rule=(
            'The snapshot endpoint is the one read that returns the counts behind every '
            'dashboard at once, which makes it the cheapest possible way to compare what '
            'a dashboard claims against what the underlying rows say. The patient-search '
            'API is the machine-facing half of the global search, and it is a separate '
            'route from it.'
        ),
        steps=(
            _s(RECEPTION, 'POST /reception/add_patient', 'patient registered'),
            _s(RECEPTION, 'POST /reception/visits/create', 'visit created'),
            _s(RECEPTION, 'GET /api/dashboard/snapshot', 'dashboard snapshot read'),
            _s(RECEPTION, 'GET /api/search/patients', 'patient search API exercised'),
            _s(RECEPTION, 'GET /api/search', 'global search exercised'),
        ),
    ),
    Template(
        key='READ_CONSOLE_LANDING_PAGES',
        family='platform',
        axes=('actor_role',),
        observed={
            'actor_role': (
                'super_admin',
                'owner',
                'admin',
                'manager',
                'reception',
                'doctor',
                'nurse',
                'lab',
                'radiology',
                'pharmacist',
                'accountant',
            )
        },
        rule=(
            'Each department console has a landing page that is separate from its '
            'dashboard, so a console can show a dashboard with no route back to its own '
            'index. They are reads of the same authorisation as the dashboard, so a '
            'landing page that loads for a role the dashboard refuses is a navigation '
            'defect rather than a data one.'
        ),
        steps=(
            _s(RECEPTION, 'POST /reception/visits/create', 'work to display'),
            _s(DOCTOR, 'GET /doctor/', 'doctor landing read'),
            _s(NURSE, 'GET /nurse/', 'nurse landing read'),
            _s(LAB, 'GET /lab/', 'lab landing read'),
            _s(RADIOLOGY, 'GET /radiology/', 'radiology landing read'),
            _s(PHARMACY, 'GET /medication/', 'pharmacy landing read'),
            _s(EMERGENCY, 'GET /emergency/', 'emergency landing read'),
            _s(ACCOUNTANT, 'GET /payment/', 'payment landing read'),
            _s(MANAGER, 'GET /manager/dashboard', 'manager landing read'),
            _s(OWNER, 'GET /owner/dashboard', 'owner landing read'),
        ),
    ),
    Template(
        key='READ_DEPARTMENT_DASHBOARDS',
        family='clinical',
        axes=('actor_role',),
        observed={
            'actor_role': (
                'super_admin',
                'owner',
                'admin',
                'manager',
                'reception',
                'doctor',
                'nurse',
                'lab',
                'radiology',
                'pharmacist',
                'accountant',
            )
        },
        rule=(
            'Seven department dashboards are separate reads with no shared aggregation, '
            'so a visit can be counted by the reception dashboard, the doctor dashboard '
            'and the queue display and appear in none of them. The queue department '
            'status endpoints are the per-department counterpart, and there are two of '
            'them with different names.'
        ),
        steps=(
            _s(RECEPTION, 'POST /reception/visits/create', 'visit to count'),
            _s(RECEPTION, 'GET /reception/dashboard', 'reception dashboard read'),
            _s(DOCTOR, 'GET /doctor/dashboard-new', 'doctor dashboard read'),
            _s(NURSE, 'GET /nurse/dashboard', 'nurse dashboard read'),
            _s(LAB, 'GET /lab/dashboard', 'lab dashboard read'),
            _s(RADIOLOGY, 'GET /radiology/dashboard', 'radiology dashboard read'),
            _s(PHARMACY, 'GET /medication/dashboard', 'pharmacy dashboard read'),
            _s(EMERGENCY, 'GET /emergency/dashboard', 'emergency dashboard read'),
        ),
    ),
    Template(
        key='READ_QUEUE_DISPLAY_AND_DEPARTMENT_STATUS',
        family='clinical',
        axes=('queue_state',),
        observed={
            'queue_state': ('waiting', 'called', 'in_progress', 'completed', 'skipped', 'cancelled')
        },
        rule=(
            'Four reads serve the waiting and calls boards, and two of them are the same '
            'data under different names: queue-status and smart-queue-management for a '
            'department, and the display endpoints for the board. A ticket can be present '
            'in one and absent from the other without either being wrong, which is the '
            'reason both exist.'
        ),
        steps=(
            _s(RECEPTION, 'POST /reception/queue/add-patient', 'ticket raised'),
            _s(RECEPTION, 'GET /reception/api/display/waiting', 'waiting board API read'),
            _s(RECEPTION, 'GET /reception/api/display/calls', 'calls board API read'),
            _s(
                RECEPTION,
                'GET /reception/api/queue-status/<int:department_id>',
                'department status read',
            ),
            _s(
                RECEPTION,
                'GET /reception/api/queue-department-status/<int:department_id>',
                'department status read through the other route',
            ),
        ),
    ),
    Template(
        key='READ_PATIENT_EDUCATION_LIBRARY',
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
            'The library, the material and the per-patient assignment are three reads '
            'over two tables, and the per-patient list is what tells a clinician whether '
            'a patient was already told something. It records no confirmation of '
            'reading, so the list shows an instruction given and not an instruction '
            'understood.'
        ),
        steps=(
            _s(DOCTOR, 'POST /patient-education/new', 'material authored'),
            _s(DOCTOR, 'POST /patient-education/assign', 'material assigned to the patient'),
            _s(DOCTOR, 'GET /patient-education/', 'library read'),
            _s(DOCTOR, 'GET /patient-education/material/<int:material_id>', 'material read'),
            _s(
                DOCTOR, 'GET /patient-education/patient/<int:patient_id>', 'assigned materials read'
            ),
        ),
    ),
    Template(
        key='READ_TELEMEDICINE_CONSULTATION_ROOM',
        family='clinical',
        axes=('telemedicine_outcome',),
        observed={'telemedicine_outcome': ('completed', 'no_show', 'cancelled', 'ended_early')},
        rule=(
            'The consultation room and the appointment view are two reads of one '
            'teleconsultation from the clinician side, and the room is the only place a '
            'clinician joins the call. A consultation the patient never joined is still '
            'readable here, because the room does not check the outcome the outcome '
            'route wrote.'
        ),
        steps=(
            _s(DOCTOR, 'POST /telemedicine/new', 'consultation opened'),
            _s(DOCTOR, 'POST /telemedicine/consult/<int:cid>/start', 'consultation started'),
            _s(DOCTOR, 'GET /telemedicine/', 'list read'),
            _s(DOCTOR, 'GET /telemedicine/<int:tm_id>', 'appointment view read'),
            _s(DOCTOR, 'GET /telemedicine/consult/<int:consultation_id>', 'consult room read'),
        ),
    ),
    Template(
        key='READ_REPORT_BUILDER_INTERFACES',
        family='financial',
        axes=('report_execution_state',),
        observed={
            'report_execution_state': ('pending', 'running', 'completed', 'failed', 'cancelled')
        },
        rule=(
            'The builder and the per-template read are the two read sides of the '
            'template table, and the template detail takes its id as a path parameter '
            'rather than a validated value. A template saved with an empty column set '
            'renders as an empty report rather than an error, so the read is where a '
            'misconfigured template is discovered.'
        ),
        steps=(
            _s(MANAGER, 'POST /report-builder/templates', 'template saved'),
            _s(MANAGER, 'GET /report-builder/', 'builder read'),
            _s(MANAGER, 'GET /report-builder/templates/<int:template_id>', 'template detail read'),
        ),
    ),
    Template(
        key='READ_BACKUP_CONSOLE_VIEWS',
        family='platform',
        axes=('backup_status',),
        observed={'backup_status': ('PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'CANCELLED')},
        rule=(
            'The backup console has its own dashboard, list and download, separate from '
            'the super-admin backup surface that writes the same rows. The download is a '
            'GET that hands over the whole dump, so it is the read with the largest '
            'consequence and the one a permission change does not obviously cover.'
        ),
        steps=(
            _s(SUPER_ADMIN, 'POST /super-admin/backup/create', 'backup taken'),
            _s(SUPER_ADMIN, 'GET /backup/list', 'backup list read'),
            _s(SUPER_ADMIN, 'GET /backup/backup/dashboard', 'backup dashboard read'),
            _s(SUPER_ADMIN, 'GET /backup/download/<int:backup_id>', 'backup downloaded'),
        ),
    ),
    Template(
        key='READ_ACCOUNTANT_RECEIPT_AND_EXPORT',
        family='financial',
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
            'The receipt route and the audit export are the two reads an accountant '
            'uses to settle a dispute: one renders a single payment and the other dumps '
            'a period by report type. The export takes its report type as a path '
            'parameter, so it is the read that decides what leaves the tenant.'
        ),
        steps=(
            _s(ACCOUNTANT, 'POST /payment/process/<visit_id>', 'payment recorded'),
            _s(ACCOUNTANT, 'GET /accountant/receipt/<int:payment_id>', 'receipt rendered'),
            _s(ACCOUNTANT, 'GET /accountant/audit/export/<report_type>', 'audit report exported'),
        ),
    ),
    Template(
        key='READ_SUPERADMIN_EXPORT_AND_ACCOUNT_ACTIONS',
        family='platform',
        axes=('actor_role',),
        observed={
            'actor_role': (
                'super_admin',
                'owner',
                'admin',
                'manager',
                'reception',
                'doctor',
                'nurse',
                'lab',
                'radiology',
                'pharmacist',
                'accountant',
            )
        },
        rule=(
            'Ban, unban and force-logout are three reads that change state, which is why '
            'they do not appear in a POST inventory: a route that mutates on GET is '
            'reachable by a prefetch, a crawler or a link preview. The three export '
            'routes and the filename download are the platform read surface that leaves '
            'the system.'
        ),
        steps=(
            _s(SUPER_ADMIN, 'POST /super-admin/users/create', 'account created to act on'),
            _s(SUPER_ADMIN, 'GET /super-admin/users/ban/<int:user_id>', 'ban applied by GET'),
            _s(SUPER_ADMIN, 'GET /super-admin/users/unban/<int:user_id>', 'unban applied by GET'),
            _s(
                SUPER_ADMIN,
                'GET /super-admin/users/force-logout/<int:user_id>',
                'force logout applied by GET',
            ),
            _s(SUPER_ADMIN, 'GET /super-admin/export-departments', 'departments exported'),
            _s(SUPER_ADMIN, 'GET /super-admin/export-services', 'services exported'),
            _s(
                SUPER_ADMIN,
                'GET /super-admin/download-export/<filename>',
                'export downloaded by filename',
            ),
        ),
    ),
    Template(
        key='READ_SUBSCRIPTION_RENEWAL_IS_A_WRITE_ON_GET',
        family='platform',
        axes=('subscription_type',),
        observed={'subscription_type': ('perpetual', 'monthly', 'yearly')},
        rule=(
            'This route is registered for GET and it renews the subscription: it '
            'advances tenant.subscription_end by a month or a year and commits. A link '
            'preview, a crawler or a browser prefetch therefore bills a tenant. It is '
            'the only renewal path in the owner console, so moving it to POST is the '
            'whole fix, and until then every GET here is a mutation.'
        ),
        steps=(
            _s(OWNER, 'POST /owner/tenants/create', 'tenant created'),
            _s(OWNER, 'POST /owner/plans/create', 'plan created'),
            _s(
                OWNER,
                'POST /owner/subscriptions/<int:tenant_id>/renew',
                'renewal written by POST for comparison',
            ),
            _s(OWNER, 'GET /owner/tenants/<int:tenant_id>/renew', 'renewal written by GET'),
            _s(OWNER, 'GET /owner/tenants/', 'subscription end read back'),
        ),
    ),
    Template(
        key='READ_DOCTOR_AND_LAB_CATALOGUE_SURFACES',
        family='clinical',
        axes=('actor_role',),
        observed={'actor_role': ('doctor', 'reception', 'manager', 'admin', 'lab')},
        rule=(
            'The doctor-side test and dashboard reads sit alongside the lab-side ones for '
            'the same catalogue, and neither is derived from the other. A clinician '
            'can therefore see a test in one list that the laboratory cannot order, '
            'which is the difference between a catalogue and a price list.'
        ),
        steps=(
            _s(LAB, 'POST /lab/test-catalog/add', 'catalogue test added'),
            _s(DOCTOR, 'GET /lab/tests', 'test list read'),
            _s(DOCTOR, 'GET /lab/api/test-catalog/<int:id>', 'catalogue item read'),
            _s(DOCTOR, 'GET /doctor/appointments', 'doctor appointment list read'),
            _s(
                DOCTOR,
                'GET /doctor/print-invoice/<int:invoice_id>',
                'invoice printed from the doctor console',
            ),
            _s(
                DOCTOR,
                'GET /doctor/print-receipt/<int:visit_id>',
                'receipt printed from the doctor console',
            ),
        ),
    ),
    Template(
        key='READ_RADIOLOGY_TEST_CATALOGUE',
        family='clinical',
        axes=('radiology_modality',),
        observed={'radiology_modality': ('XRay', 'CT', 'MRI', 'US')},
        rule=(
            'The radiology test catalogue and its FHIR observation export are the two '
            'reads that describe what can be ordered and how a result leaves the '
            'system. The modality column is a free String, so the catalogue can list a '
            'modality the equipment table does not have.'
        ),
        steps=(
            _s(RADIOLOGY, 'POST /radiology/tests/add', 'imaging test added'),
            _s(RADIOLOGY, 'POST /api/radiology/results/<int:result_id>/amend', 'report written'),
            _s(RADIOLOGY, 'GET /radiology/tests', 'test catalogue read'),
            _s(
                RADIOLOGY,
                'GET /radiology/api/fhir/observation/radiology/<int:result_id>',
                'observation exported',
            ),
        ),
    ),
    Template(
        key='READ_PHARMACY_EXTERNAL_CATALOGUE_AND_EMERGENCY_PRINTS',
        family='clinical',
        axes=('medication_status',),
        observed={'medication_status': ('active', 'inactive', 'discontinued')},
        rule=(
            'The external drug search is the only read that reaches outside the '
            'application, and it returns whatever the third party returns without a '
            'schema check, so it is the read that can introduce a drug the pharmacy '
            'catalogue does not hold. The emergency prescription print is the '
            'counterpart that puts one back on paper.'
        ),
        steps=(
            _s(PHARMACY, 'POST /medication/add', 'local drug added'),
            _s(PHARMACY, 'GET /medication/api/external-drug-search', 'external catalogue searched'),
            _s(
                EMERGENCY,
                'POST /emergency/prescription/<int:emergency_id>',
                'emergency prescription issued',
            ),
            _s(
                EMERGENCY,
                'GET /emergency/print-prescription/<int:prescription_id>',
                'prescription printed',
            ),
        ),
    ),
    Template(
        key='READ_PORTAL_BOOKING_AND_DOCUMENTS',
        family='financial',
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
            'The portal appointment list and the booking page are the two patient-facing '
            'scheduling reads, and the document download is the one that hands a file to '
            'the patient rather than rendering it. A file id that resolves to another '
            'patient document is the risk the download carries and the list does not.'
        ),
        steps=(
            _s(PATIENT, 'POST /portal/link-account', 'portal identity linked'),
            _s(PATIENT, 'GET /portal/appointments', 'appointment list read'),
            _s(PATIENT, 'GET /portal/book-appointment', 'booking page read'),
            _s(PATIENT, 'GET /portal/documents/<int:file_id>', 'document downloaded'),
        ),
    ),
    Template(
        key='READ_CLINICAL_CODING_DRG_LIST',
        family='clinical',
        axes=('diagnosis_type',),
        observed={'diagnosis_type': ('PRIMARY', 'SECONDARY', 'ADMITTING', 'DISCHARGE')},
        rule=(
            'The DRG list is the last reference read in the coding module, and it is the '
            'only one whose rows are derived rather than authored: a DRG is computed '
            'from the diagnoses and procedures attached to an encounter, so the list can '
            'be empty for a coded patient if nothing has grouped the encounter.'
        ),
        steps=(
            _s(DOCTOR, 'POST /doctor/diagnosis/<int:visit_id>', 'coded diagnosis written'),
            _s(DOCTOR, 'GET /clinical-coding/drg', 'drg list read'),
            _s(
                DOCTOR,
                'GET /clinical-coding/patient/<int:patient_id>/diagnoses',
                'diagnoses read back',
            ),
        ),
    ),
    Template(
        key='READ_FINANCE_WEEKLY_SLOW_QUERY_DETAIL',
        family='financial',
        axes=('log_level',),
        observed={'log_level': ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')},
        rule=(
            'The weekly slow-query detail is a read of a generated report rather than of '
            'a live query, so it can show a problem that has since been fixed and miss '
            'one that has appeared since. It is the only finance read that reports on '
            'the application rather than on the business.'
        ),
        steps=(
            _s(ACCOUNTANT, 'POST /finance/slow-queries/capture', 'slow query captured'),
            _s(ACCOUNTANT, 'GET /finance/slow-queries/weekly', 'weekly report read'),
            _s(
                ACCOUNTANT, 'GET /finance/slow-queries/weekly/<int:report_id>', 'weekly detail read'
            ),
        ),
    ),
    Template(
        key='READ_STATIC_AND_FAVICON_SURFACES',
        family='rbac',
        axes=('actor_role',),
        observed={'actor_role': ('super_admin', 'owner', 'admin', 'manager', 'reception')},
        rule=(
            'The static file route and the favicon are the two reads every page load '
            'depends on and no test needs to think about. They are recorded here because '
            'the static route is a path traversal surface, and a matrix that lists only '
            'interesting routes would leave that untested by default.'
        ),
        steps=(
            _s(SUPER_ADMIN, 'GET /static/<path:filename>', 'static asset served'),
            _s(SUPER_ADMIN, 'GET /favicon.ico', 'favicon served'),
            _s(SUPER_ADMIN, 'GET /health', 'application confirmed live'),
        ),
    ),
)


def add_read_templates() -> int:
    """Extend templates.TEMPLATES in place, idempotently. Returns how many were added."""
    existing = {t.key for t in TEMPLATES}
    added = 0
    for t in READ_TEMPLATES:
        if t.key not in existing:
            TEMPLATES.append(t)
            added += 1
    return added
