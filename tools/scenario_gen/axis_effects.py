"""What each axis actually does to the run, one authored sentence per axis.

The matrix has a duplication failure mode that is easy to hide: a template
declares an axis, the generator multiplies the journey across every value of it,
and the emitted scenarios differ only in a field nobody reads. The count goes up
and the coverage does not.

So every axis is required to state its mechanism here, and the mechanism has to
contain ``{value}``, which expands to one true sentence per value. An axis that
cannot say what it does to the run is not declared at all: it is deleted from the
template instead, and the matrix shrinks honestly rather than growing falsely.

Most mechanisms are the same across the templates that use the axis, so the
entries are keyed by ``(template, axis)`` and there is a shared fallback by axis
for the cases where the effect genuinely is the same everywhere. A template entry
overrides the fallback.

Reading a mechanism tells you what varies. Reading what is *absent* is the more
useful signal: those axes were removed because no route on the journey could be
shown to depend on them.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Mechanisms shared by every template that declares the axis.
#
# Each is written so that substituting the value states something true about that
# value in the code, not something generic about the dimension.
# ---------------------------------------------------------------------------
AXIS_EFFECTS: dict[str, str] = {
    # ---- money -------------------------------------------------------------
    'payment_method': (
        'collected by {value}: CASH and FORCE both post to the cash GL account, '
        'while the lowercase visa and mada members are mapped onto CARD by '
        'payment_routes and INSURANCE posts to the insurer receivable instead'
    ),
    'insurance_coverage': (
        'the insurer pays {value} percent, so patient_share is total x '
        '(1 - {value}/100); the value is a hand-typed percentage with no '
        'deductible, no copay and no exclusion list'
    ),
    'cash_amount': (
        'a cash collection of {value}, against GatekeeperService.MAX_CASH_AMOUNT '
        'of 5000 with no per-tenant or per-user override path'
    ),
    'payment_amount_over_remaining': (
        'the amount is {value} percent of the outstanding balance, so the run '
        'distinguishes a partial payment, an exact settlement and an overpayment '
        'that the route rejects with 400'
    ),
    'line_item_count': (
        'the invoice carries {value} add-service lines, which is what the archive '
        'reconciliation compares against visit.total_amount'
    ),
    'invoice_status': (
        'the invoice is left in {value}, and only POSTED is the point at which '
        'revenue is recognised'
    ),
    'journal_status': (
        'the journal is left in {value}; VOID reverses its lines rather than deleting them'
    ),
    'journal_source_type': (
        'the ledger entry is posted under source type {value}, and idempotency is '
        'enforced per source type and source id, so the same fact under two '
        'types is two valid journals'
    ),
    'currency': (
        'amounts are carried in {value}; every price column and the whole '
        'settlement arithmetic treat the currency as ILS regardless, so this axis '
        'changes what is recorded and not what is charged'
    ),
    'insurance_claim_status': (
        'the claim is driven to {value}; only SETTLED should mean money arrived'
    ),
    'insurance_claim_outcome': (
        'adjudication records {value}, and the payout that follows is written on '
        'the claim rather than posted to the ledger'
    ),
    'force_payment_ratio': (
        'force payments are {value} percent of the last thirty days of visits, '
        'against a gate that refuses at five percent'
    ),
    # ---- visit and appointment state ----------------------------------------
    'visit_state': (
        'the visit is driven to {value}, and a direct assignment raises unless the '
        'state machine authorises the transition'
    ),
    'visit_workflow_status': (
        'the visit reaches {value} in the reception workflow, which is a different '
        'naming of the same states as VisitState'
    ),
    'visit_archive_status': (
        'the visit ends {value}, and archiving is only permitted once the invoice '
        'line sum reconciles with visit.total_amount'
    ),
    'visit_type': (
        'the visit is opened as {value}, which selects the pricing rule: a '
        'FOLLOW_UP is discounted while the others are not'
    ),
    'payment_status': ('the visit payment status is {value}, and the queue gate admits PAID only'),
    'appointment_status': (
        'the appointment sits in {value} in the lower-cased workflow enum, which '
        'has no CHECKED_IN member even though AppointmentState does'
    ),
    'appointment_state': ('the appointment moves to {value} in Appointment.state'),
    'booking_state': (
        'the online booking ends in {value}; only converted produces a real '
        'Patient and a real Visit'
    ),
    'queue_state': (
        'the ticket ends in {value}, and skipped is the value return-to-queue has '
        'to treat as non-terminal'
    ),
    'task_state': ('the nursing or handover task moves to {value}'),
    'task_priority': (
        'the task is raised at {value} priority, which decides where it sorts in the work list'
    ),
    # ---- emergency -----------------------------------------------------------
    'triage_level': (
        'the case is triaged {value}; routes/emergency/queue.py maps RED to '
        'CRITICAL, YELLOW to HIGH and GREEN to MODERATE, and RED is the only '
        'level that reaches resuscitation without waiting'
    ),
    'emergency_severity': ('the case carries {value} severity, uppercased by a validator'),
    'emergency_status': (
        'the case moves to {value} in the nine-state machine that only five routes can write'
    ),
    'admission_type': (
        'the admission is filed as {value}, which is recorded separately from the '
        'emergency severity'
    ),
    'admission_status': (
        'the admission ends {value}; DISCHARGED and DECEASED both release the bed'
    ),
    'discharge_type': (
        'the discharge is typed {value}; AGAINST_ADVICE is the one the schema has '
        'no column to record a signature for'
    ),
    # ---- diagnostics ---------------------------------------------------------
    'lab_result_status': (
        'the result is left in {value}; only VALIDATED releases it to the ordering clinician'
    ),
    'lab_order_status': (
        'the lab order advances to {value}, which is a separate progression from LabResult.status'
    ),
    'lab_result_flag': (
        'the result is interpreted as {value}; the interpretation column is a '
        'free String, so {value} is a convention rather than a constraint'
    ),
    'radiology_modality': (
        'the study is booked as {value}, the modality the request column documents'
    ),
    'radiology_result_status': ('the report is left in {value}'),
    'radiology_order_status': ('the imaging order advances to {value}'),
    'dicom_study_status': (
        'the DICOM study is recorded as {value}, a status no route in the application writes'
    ),
    # ---- pharmacy and prescribing --------------------------------------------
    'prescription_state': (
        'the prescription reaches {value}; the enum is wider than the column '
        'CHECK constraint, so part of the axis is not representable'
    ),
    'medication_status': (
        'the drug is {value}; the POS dispense check only looks at inactive, so '
        'a discontinued drug is still dispensable'
    ),
    'drug_interaction_severity': (
        'the interaction is recorded at {value} severity on a table that carries no tenant_id'
    ),
    'emar_status': (
        'the administration record is {value}, and MISSED and LATE cannot be '
        'written because eMAR has no reachable route'
    ),
    'supply_request_status': (
        'the supply request moves to {value} in the DRAFT to FULFILLED machine'
    ),
    'stock_movement_type': (
        'the inventory ledger records a {value} movement; the enum has no '
        'dispense and no waste member even though dispensing is the main outflow'
    ),
    'vaccine_route': ('the vaccination is recorded as {value}'),
    'vaccine_status': ('the vaccination ends {value}'),
    # ---- clinical record ------------------------------------------------------
    'problem_severity': ('the problem is recorded at {value} severity'),
    'problem_status': ('the problem ends {value}'),
    'problem_type': ('the chart entry is filed as a {value}'),
    'diagnosis_type': ('the diagnosis is filed as the {value} diagnosis'),
    'diagnosis_status': ('the diagnosis ends {value}'),
    'follow_up_status': ('the follow-up ends {value}'),
    'treatment_status': ('the treatment record moves to {value}'),
    'procedure_status': ('the procedure record moves to {value}'),
    'referral_status': (
        'the referral is {value}; there is no create endpoint anywhere, so this '
        'state is only reachable through the model'
    ),
    'referral_urgency': ('the referral is raised at {value} urgency'),
    'ward_type': (
        'the bed is placed in a {value} ward, which prices nothing: an ICU stay '
        'and a general stay cost the same'
    ),
    'bed_type': ('the bed is a {value}, which also prices nothing'),
    'bed_status': (
        'the bed ends {value}, and OUT_OF_ORDER is not an occupancy, so '
        'availability has to subtract it explicitly'
    ),
    'room_type': ('the room is a {value}, which prices nothing'),
    'surgery_type': ('the theatre case is filed as {value}'),
    'surgery_priority': (
        'the case is scheduled at {value} priority; STAT is the only one that bypasses the queue'
    ),
    'surgery_status': ('the theatre case ends {value}, and DELAYED is a member no route writes'),
    'workflow_status': ('the record ends {value}'),
    'staff_schedule_status': (
        'attendance is recorded as {value}; the column is a free String with no CHECK constraint'
    ),
    # ---- access control --------------------------------------------------------
    'actor_role': (
        'the journey is run as {value}, which is what decides whether the '
        'role_required decorator admits or refuses the step'
    ),
    'permission_level': (
        'the permission is granted at {value} level, and the decorator matches on '
        'the level string rather than on the category'
    ),
    'permission_category': (
        'the permission belongs to the {value} category, and the matrix is built '
        'per category so a new category starts with no rows'
    ),
    'login_outcome': (
        'the attempt ends as {value}; only success writes an audit row with '
        'action login, while every failure writes a SecurityEvent instead'
    ),
    'mfa_method': (
        'the second factor is enrolled as {value}, and verify checks the same '
        'TOTP path for all three methods, so the method is recorded rather than '
        'enforced'
    ),
    'sso_protocol': ('federation is configured for {value}'),
    'audit_action': ('the audit row records a {value} action on that entity'),
    'entity_type': ('the audited entity is the {value} row'),
    'security_event_type': (
        'a {value} security event is raised, in the table separate from the audit trail'
    ),
    'security_severity': ('the event is filed at {value} severity'),
    'log_level': ('the system log line is written at {value}'),
    # ---- platform configuration --------------------------------------------------
    'tenant_status': (
        'the tenant is {value}, which is the value every feature gate and subscription check reads'
    ),
    'product_profile': (
        'the tenant is seeded from the {value} profile, which decides which '
        'modules exist on day one; custom seeds none'
    ),
    'storage_mode': (
        'the tenant stores objects as {value}; hybrid is the only mode where the '
        'backup path must reconcile two stores'
    ),
    'module_name': (
        'the {value} module is the one being activated or deactivated for the '
        'tenant, and the feature gate reads that row on every request'
    ),
    'module_status': ('the module is left {value}, which is the row the feature gate reads'),
    'bundle_kind': (
        'the bundle is the {value} profile, whose max_users and max_patients '
        'ceilings are enforced at flush rather than at subscribe time'
    ),
    'subscription_type': (
        'the subscription bills {value}; this is tenant revenue and is entirely '
        'disconnected from patient billing'
    ),
    'config_category': (
        'the setting is filed under the {value} category, and a reader matches on '
        'the name, so an unknown category simply never matches'
    ),
    'config_type': (
        'the value is stored as {value}, which decides how the string is coerced; '
        'password is the one type redacted on read'
    ),
    'notification_event_type': (
        'the rule fires on {value}, one of the only four triggers the sender knows'
    ),
    'notification_channel': (
        'delivery goes out over {value} to a free-text target that is not '
        'validated when the rule is saved'
    ),
    'notification_priority': (
        'the notification is queued at {value} priority, and urgent is the only '
        'value that skips the queue'
    ),
    'notification_state': (
        'the notification ends {value}; a failed send is recorded here rather than '
        'as an error on the rule'
    ),
    'support_ticket_category': (
        'the ticket is filed as {value}, a free-text column documented by '
        'comment rather than by a constraint'
    ),
    'backup_type': ('the backup is a {value} taken now'),
    'backup_status': ('the backup job ends {value}'),
    'backup_schedule_type': (
        'the schedule repeats {value}; custom is the only member carrying its own cron expression'
    ),
    'report_execution_state': (
        'the saved report ends {value}, and a failure is visible only as a state '
        'and never as an error to the caller'
    ),
    'print_doc_type': (
        'the printed document is the {value}, each of which renders from its own '
        'template and its own set of permitted fields'
    ),
    # ---- integration ---------------------------------------------------------------
    'hl7_message_type': (
        'an {value} message is ingested, which dispatches to a different handler; '
        'an unknown type is acknowledged and then dropped'
    ),
    'telemedicine_outcome': (
        'the consultation ends as {value}; these are four routes rather than one '
        'route with a parameter, so the status column has no state machine to '
        'reject an impossible transition'
    ),
}

# ---------------------------------------------------------------------------
# Template-specific overrides, where the effect genuinely differs from the
# shared mechanism for that axis.
# ---------------------------------------------------------------------------
TEMPLATE_EFFECTS: dict[str, dict[str, object]] = {
    'OWNER_MODULE_ENTITLEMENT': {
        'module_status': {
            'enabled': 'the row is left enabled, so the feature gate admits the '
            'request and the module appears in the menus',
            'disabled': 'the row is left disabled, so the feature gate refuses the '
            'request and the module disappears from the menus in the same response',
        }
    },
    'PLATFORM_MODULE_ACTIVATION': {
        'module_status': {
            'enabled': 'the tenant module row is left enabled, so the gate admits it',
            'disabled': 'the tenant module row is left disabled, so the gate refuses '
            'it, and with ENABLE_SAAS_MODE False the gate ignores the row entirely',
        }
    },
    'OPD_FOLLOW_UP_DISCOUNT': {
        'visit_type': 'the visit is opened as {value}, which is what the discount '
        'rule keys on: FOLLOW_UP is the only member that is discounted'
    },
    'FORCE_PAYMENT_QUOTA_AND_APPROVAL': {
        'force_payment_ratio': 'the trailing thirty-day force-payment share is '
        '{value} percent of all visits, and the gate refuses at five percent, so '
        'this value decides whether a manager is needed at all'
    },
    'QUEUE_GATE_AND_ADD_SERVICE_RBAC': {
        'payment_status': 'the visit carries payment status {value}, and '
        '_check_queue_entry_conditions admits PAID only'
    },
    'QUEUE_TICKET_LIFECYCLE': {'task_state': 'the ticket task ends {value}'},
    'NURSING_ASSESSMENT_SCALES': {
        'ward_type': 'the assessment is recorded on a {value} ward, which is '
        'descriptive only and does not change the scale that is applied'
    },
    'INPATIENT_PLACEMENT_BY_WARD_AND_BED': {
        'ward_type': 'the bed is placed in a {value} ward; nothing prices a ward, '
        'so the stay costs the same as any other',
        'bed_type': 'the bed allocated is a {value}; nothing prices a bed either',
    },
    'DISPENSE_GATE_SEQUENCE': {
        'actor_role': 'the dispense is attempted as {value}; the pharmacy routes '
        'are pharmacist-gated, so the outcome is a refusal for every other role'
    },
    'INPATIENT_ADMIT_TRANSFER_DISCHARGE': {
        'actor_role': 'the admission is opened as {value}, and the bed routes are '
        'nurse-gated, so only a clinical role may write the bed state'
    },
    'MANAGER_PRICING_ADMINISTRATION': {
        'insurance_coverage': 'the coverage recorded alongside the seeded price is '
        '{value} percent; it changes the share shown on the pricing page and '
        'nothing about the seeded price itself'
    },
    'MANAGER_WHAT_IF_MODELLING': {
        'payment_method': 'the model prices the tenant as if payment were {value}, '
        'which is the only axis the projection reads'
    },
    'MANAGER_SETTINGS_AND_INTEGRATIONS': {
        'config_category': 'the setting is written under the {value} category, and '
        'the exchange rate that follows is global rather than per tenant'
    },
    'ACCOUNTING_PERIOD_CLOSE': {
        'currency': 'the period is closed with amounts carried in {value}, while '
        'the trial balance reads the same account rows the ledger wrote'
    },
    'SHIFT_HANDOVER_CASH_SNAPSHOT': {'task_state': 'the handover sheet is closed in {value}'},
    'MANAGER_FINANCE_AND_BUDGET': {
        'invoice_status': 'the invoice is left in {value}, which is the state the '
        'archive reconciliation and the budget entry both read'
    },
    'MANAGER_FORCE_PAYMENT_REVIEW': {
        'force_payment_ratio': 'the trailing share is {value} percent, so the '
        'manager rejection step is only reachable once the gate has already let '
        'the payment through'
    },
    'IDENTITY_PERMISSION_MATRIX': {
        'permission_category': 'the permission is created in the {value} category, '
        'and the matrix is written per category, so an empty category denies '
        'everything',
        'permission_level': 'the permission carries the {value} level, which is '
        'the string the role decorator matches on',
    },
    'IDENTITY_REGISTRATION_AND_LOGIN': {
        'login_outcome': 'the attempt ends as {value}, which is the branch the '
        'audit writer and the security-event writer take'
    },
    'IDENTITY_PATIENT_PORTAL_ACCOUNT': {
        'login_outcome': 'the portal attempt ends as {value}, and only success '
        'reaches link-account, so a failed attempt cannot join an identity'
    },
    'IDENTITY_SECOND_FACTOR_ENROLMENT': {
        'mfa_method': 'the factor is enrolled as {value}; verify checks one shared '
        'TOTP path, so the recorded method does not change the code that is '
        'accepted'
    },
    'IDENTITY_SSO_FEDERATION': {
        'sso_protocol': 'the tenant federates over {value}, and nothing validates '
        'that the provider answers before the password path stays enabled'
    },
    'IDENTITY_AUDIT_TRAIL_COVERAGE': {
        'entity_type': 'the audited row is a {value}, and coverage is a matrix, so '
        'a gap on one entity type is invisible from another',
        'audit_action': 'the audit row records a {value} action, and the four '
        'failure members are written by the decorator rather than by the handler',
    },
    'IDENTITY_PASSWORD_LIFECYCLE': {
        'actor_role': 'the credential is handled as {value}; only owner and '
        'super_admin may reset or reveal somebody else password'
    },
    'IDENTITY_SESSION_TERMINATION': {
        'actor_role': 'the session is held by a {value} user, and the force-logout '
        'action is not emitted for any of them'
    },
    'IDENTITY_IMPERSONATION': {
        'actor_role': 'impersonation targets a {value} user, and every row written '
        'while the context is borrowed carries the target rather than the operator'
    },
    'IDENTITY_STAFF_ACCOUNT_LIFECYCLE': {
        'actor_role': 'the account belongs to a {value} user, and only owner or '
        'super_admin may deactivate or delete one'
    },
    'IDENTITY_ROLE_DEPARTMENT_BINDING': {
        'actor_role': 'the binding is made for a {value} user; a role without a '
        'department is reachable in none'
    },
    'IDENTITY_USER_PREFERENCES': {
        'print_doc_type': 'the preference decides how the {value} prints for this '
        'user, so the same record renders differently for two users of one tenant'
    },
    'RADIOLOGY_REPORT_AND_REVIEW': {
        'radiology_modality': 'the study is booked as {value}, and the report '
        'template library is selected per modality',
    },
    'RADIOLOGY_TEMPLATES_AND_MACROS': {
        'radiology_modality': 'the macro is written for {value} studies only'
    },
    'AI_IMAGING_TRIAGE': {
        'radiology_modality': 'the AI request is raised for a {value} study, and '
        'the modality column is a free String, so the request can name a modality '
        'the study did not use'
    },
    'RADIOLOGY_REPORT_TEMPLATE_LIBRARY': {
        'print_doc_type': 'the {value} is the document the stored template is '
        'injected into, and deleting the template leaves the queued document to '
        'fall back without recording that it did'
    },
    'PATIENT_EDUCATION_MATERIAL': {
        'print_doc_type': 'the material is printed as the {value}, so the document '
        'type decides which instruction the patient actually receives'
    },
    'BARCODE_AND_QUEUE_LABELLING': {
        'print_doc_type': 'the scan resolves a {value} label, and the barcode '
        'routes are the only place a ticket can be raised without a visit'
    },
    'LAB_RESULT_CRITICAL_FLAGGING': {
        'lab_result_status': 'the result is left {value}, so a {value} result is '
        'the one that is not yet released to the ordering clinician',
    },
    'LAB_BARCODE_AND_LIS_RECEIPT': {
        'lab_result_status': 'the result is left {value} after the receipt'
    },
    'LAB_QUALITY_CONTROL_AND_REAGENTS': {'lab_result_status': 'the control result is left {value}'},
    'PHARMACY_STOCK_AND_SUPPLY': {
        'supply_request_status': 'the request moves to {value}, and the inventory '
        'ledger movement type is chosen by the caller rather than derived from '
        'the request',
        'stock_movement_type': 'a {value} movement is written, and nothing ties it '
        'to the request that caused it',
    },
    'PROCUREMENT_RECEIVE_AND_LEDGER': {
        'stock_movement_type': 'the receipt is booked as a {value} movement'
    },
    'PHARMACY_POS_SALE_AND_RETURN': {
        'payment_method': 'the sale is tendered by {value}, and only CASH and CARD '
        'reach the POS charge',
        'stock_movement_type': 'the return posts a {value} movement, which is the '
        'closest the enum comes to a refund of stock',
    },
    'PHARMACY_PURCHASE_AND_DISPENSE': {
        'stock_movement_type': 'the ledger records a {value} movement; the dispense '
        'itself has no member of its own',
        'prescription_state': 'the prescription is {value} when the POS charges it',
    },
    'PHARMACY_CATALOGUE_AND_SUPPLIERS': {
        'medication_status': 'the drug is {value}, and only inactive is checked by '
        'the dispense gate'
    },
    'MEDICATION_CATALOG_AND_INTERACTIONS': {
        'actor_role': 'the interaction screen is opened by a {value} user; the '
        'check itself spans tenants because the table carries no tenant_id'
    },
    'CUSTOM_SERVICE_APPROVAL': {
        'actor_role': 'the service is approved by a {value} user, and the approval '
        'route is manager-gated'
    },
    'DOCTOR_PRESCRIPTION_STATE_CHANGES': {
        'actor_role': 'the prescription is written by a {value} prescriber'
    },
    'DOCTOR_NOTES_AND_TEMPLATES': {
        'treatment_status': 'the treatment the note describes is {value}'
    },
    'RECEPTION_PATIENT_ADMINISTRATION': {
        'actor_role': 'the record is administered by a {value} user, and the '
        'delete route is reception-gated'
    },
    'PATIENT_CHART_PROBLEM_AND_ALLERGY': {
        'problem_severity': 'the problem is recorded at {value} severity',
        'problem_status': 'the problem ends {value}, and the toggle route flips it '
        'between active and resolved only',
    },
    'INPATIENT_BED_AND_ADMISSION': {
        'bed_status': 'the bed ends {value}, and availability has to subtract '
        'OUT_OF_ORDER because it is not an occupancy',
        'admission_status': 'the admission ends {value}',
        'discharge_type': 'the discharge is typed {value}',
    },
    'INPATIENT_SURGERY_SCHEDULING': {
        'surgery_type': 'the case is filed as {value}; the operating room has no '
        'create route, so this state is exercised through the model',
        'surgery_priority': 'the case is scheduled at {value} priority',
        'surgery_status': 'the case ends {value}',
    },
    'SPECIALTY_FORM_LIFECYCLE': {'workflow_status': 'the form version ends {value}'},
    'EMERGENCY_QUEUE_TO_ADMISSION': {
        'triage_level': 'the case is triaged {value}, and only RED reaches '
        'resuscitation without a wait; the emergency severity the queue writes is '
        'derived from it rather than chosen separately',
    },
    'EMERGENCY_QUEUE_EXEMPTION': {
        'emergency_severity': 'the exemption is claimed on {value} severity, which '
        'is the field the queue gate reads to admit an unpaid patient',
        'triage_level': 'the case is triaged {value}',
    },
    'EMERGENCY_CASE_RESOLUTION': {'emergency_severity': 'the case is closed at {value} severity'},
    'EMERGENCY_CASE_TREATMENT': {
        'emergency_status': 'the case moves to {value}, and the edit route writes no '
        'history row while moving it'
    },
    'EMERGENCY_TREATMENT_AND_ORDERS': {
        'emergency_severity': 'the treatment is recorded against {value} severity',
        'treatment_status': 'the treatment record moves to {value}',
    },
    'QUEUE_TICKET_OPERATIONS': {
        'queue_state': 'the ticket ends {value}, and returning a skipped patient '
        'can leave two live rows if the guard does not treat skipped as terminal',
    },
    'STAFF_SCHEDULE_AND_ABSENCE': {
        'staff_schedule_status': 'attendance is recorded as {value}, and marking a '
        'clinician absent does not cancel their appointments',
        'actor_role': 'the {value} user is the one whose attendance is written, and '
        'the write does not cancel their appointments',
    },
    'SUPERADMIN_NOTIFICATION_DELIVERY': {
        'notification_priority': 'the notification is queued at {value} priority',
        'notification_state': 'the notification ends {value}; running the queue and '
        'draining it directly can send it twice',
    },
    'SUPERADMIN_BACKUP_LIFECYCLE': {
        'backup_type': 'a {value} backup is taken, and nothing in the path '
        'validates tenant scope, so a restore is platform wide'
    },
    'SUPERADMIN_PLATFORM_OPERATIONS': {
        'backup_schedule_type': 'automation is scheduled {value}, which is the '
        'only member that carries its own cron expression'
    },
    'SUPERADMIN_BRANCH_AND_QUEUE_CONFIGURATION': {
        'queue_state': 'the global queue settings are written while the department '
        'queue sits in {value}, and neither console records which one wins'
    },
    'SUPERADMIN_SIMPLE_ROLE_AND_PERMISSION_WIZARDS': {
        'permission_level': 'the wizard-created permission carries the {value} '
        'level, which is the string the decorator matches on'
    },
    'SUPERADMIN_DEPARTMENT_STAFF_BINDING': {
        'actor_role': 'a {value} user is bound to the department and then unbound, '
        'and the scheduled visits are not rewritten'
    },
    'SUPERADMIN_DEPARTMENT_AND_SERVICE_CATALOGUE': {
        'audit_action': 'the catalogue write is audited as a {value} action'
    },
    'OWNER_TENANT_PROVISIONING': {
        'tenant_status': 'the tenant is created {value}, which is the value every '
        'gate reads, and deleted is a status like any other',
        'product_profile': 'the tenant is seeded from the {value} profile, and '
        'custom seeds no modules at all',
    },
    'OWNER_TENANT_STATUS_TRANSITIONS': {
        'tenant_status': 'the tenant is driven to {value}, and there is no expiry '
        'route, so a lapsed trial stays active'
    },
    'OWNER_TENANT_SELF_SERVICE_SIGNUP': {
        'tenant_status': 'the self-registered tenant arrives {value}, reachable by '
        'nobody until an owner activates it',
        'product_profile': 'the signup requests the {value} profile',
    },
    'OWNER_SUBSCRIPTION_BILLING_CYCLE': {
        'subscription_type': 'the tenant subscription bills {value}, and the Stripe '
        'and local paths are separate code with separate state'
    },
    'OWNER_PLAN_AND_BUNDLE_CATALOGUE': {
        'subscription_type': 'the plan bills {value}',
        'bundle_kind': 'the bundle is the {value} profile, and its ceilings are '
        'enforced at flush rather than at subscribe time',
    },
    'OWNER_PACKAGE_VERSION_LIFECYCLE': {
        'audit_action': 'the version write is audited as a {value} action, and '
        'deprecating a version reaches every tenant subscribed to it'
    },
    'OWNER_SYSTEM_CONFIGURATION': {
        'config_category': 'the setting is filed under {value}',
        'config_type': 'the value is stored as {value}, and password is the one '
        'type redacted on read',
    },
    'OWNER_NOTIFICATION_RULES': {
        'notification_event_type': 'the rule fires on {value}',
        'notification_channel': 'delivery goes out over {value}',
    },
    'OWNER_API_KEYS_AND_WEBHOOKS': {'audit_action': 'the key write is audited as a {value} action'},
    'OWNER_BRANDING_AND_THEMES': {
        'storage_mode': 'the tenant stores objects as {value}, which decides where '
        'the theme asset and the DICOM objects live'
    },
    'OWNER_SUPPORT_TICKETS': {'support_ticket_category': 'the ticket is filed as {value}'},
    'OWNER_USAGE_AND_ASSUMPTIONS': {'entity_type': 'usage is recorded against the {value} count'},
    'SUPERADMIN_PLAN_CHANGE_FROM_PLATFORM': {
        'subscription_type': 'the tenant is moved onto a {value} plan, and the '
        'family is validated so unrelated families cannot be reached'
    },
    'INTEGRATION_HL7_MESSAGE_INGEST': {
        'hl7_message_type': 'an {value} message is ingested; an unknown type is '
        'acknowledged with a 200 and then dropped'
    },
    'INTEGRATION_FHIR_OBSERVATION_EXPORT': {
        'lab_result_flag': 'the exported observation carries the {value} flag, and '
        'a push with no acknowledgement leaves no record that anything was sent'
    },
    'INTEGRATION_DATA_WAREHOUSE_SYNC': {
        'entity_type': 'the {value} rows are the ones the synchronisation copies'
    },
    'INTEGRATION_REPORT_BUILDER': {
        'report_execution_state': 'the saved report ends {value}, and a failure is '
        'visible only as a state'
    },
    'INTEGRATION_API_KEY_CONSUMER': {
        'audit_action': 'the key write is audited as a {value} action'
    },
    'TELEMEDICINE_CONSULTATION_LIFECYCLE': {
        'telemedicine_outcome': 'the consultation ends as {value}'
    },
    'TELEMEDICINE_NON_ATTENDANCE': {
        'telemedicine_outcome': 'the consultation ends as {value}, and neither '
        'route records a reason or releases the slot'
    },
    'INSURANCE_CLAIM_LIFECYCLE': {
        'insurance_coverage': 'the claim is raised at {value} percent coverage',
        'payment_status': 'the visit payment status is {value} when the claim is '
        'raised, which is what decides whether an insurer row is created at all',
    },
    'REFUND_REQUEST_APPROVE_EXECUTE': {
        'payment_status': 'the payment is refunded from {value}, and only a '
        'confirmed payment has a refundable balance'
    },
    'ACCOUNTANT_REFUND_EXECUTION': {'journal_status': 'the refund journal is left {value}'},
    'LEDGER_JOURNAL_REVERSAL': {
        'journal_source_type': 'the entry is posted under {value}, and the guard is '
        'per source type, so a repeat under another type is not caught'
    },
    'PHARMACY_SALE_POSTS_TO_LEDGER': {
        'journal_source_type': 'the sale posts under the {value} source type, '
        'which is how a retail sale avoids needing a Visit row'
    },
    'PAYMENT_INSURANCE_ADJUDICATION_API': {
        'insurance_claim_status': 'the claim is driven to {value}'
    },
    'PROCUREMENT_SUPPLY_CHAIN': {'supply_request_status': 'the request moves to {value}'},
    'APPOINTMENT_CHECKIN_HUB_AND_SPOKE': {'appointment_status': 'the appointment sits in {value}'},
    'APPOINTMENT_NO_SHOW_AND_CANCEL': {'appointment_status': 'the appointment ends {value}'},
    'APPOINTMENT_LIFECYCLE': {'appointment_state': 'the appointment moves to {value}'},
    'ONLINE_BOOKING_CONVERSION': {'booking_state': 'the booking ends {value}'},
    'CASH_PAYMENT_LIMIT': {'cash_amount': 'the collection is {value} against the fixed 5000 cap'},
    'OVERPAYMENT_AND_BOUNDARY': {
        'payment_amount_over_remaining': 'the payment is {value} percent of the '
        'balance, which decides between partial, exact and rejected',
        'line_item_count': 'the invoice carries {value} lines, which is what the '
        'archive reconciliation counts',
    },
    'PLATFORM_AUDIT_AND_SECURITY_REVIEW': {
        'security_severity': 'the event is filed at {value} severity',
        'log_level': 'the line is written at {value} level',
    },
    'PLATFORM_BACKUP_RESTORE': {
        'backup_type': 'a {value} backup is taken',
        'backup_status': 'the job ends {value}',
    },
    'PLATFORM_BUNDLE_AND_ENTITLEMENT': {'bundle_kind': 'the bundle is the {value} profile'},
    'PLATFORM_SUBSCRIPTION_LIFECYCLE': {
        'tenant_status': 'the tenant is {value} when the subscription changes',
        'subscription_type': 'the subscription bills {value}',
    },
    'PLATFORM_BILLING_SUBSCRIPTION_PORTAL': {'subscription_type': 'the subscription bills {value}'},
    'PLATFORM_USER_AND_ROLE_GOVERNANCE': {
        'actor_role': 'the user is created as {value}, and only super_admin or '
        'owner may manage users'
    },
    'VISIT_WORKFLOW_STATE_MACHINE': {'visit_state': 'the visit is driven to {value}'},
    'LAB_CATALOGUE_MAINTENANCE': {'currency': 'the catalogue price is carried in {value}'},
}


# ---------------------------------------------------------------------------
# Where each axis's value actually comes from.
#
# This is the independent check on the mechanisms above. A mechanism says what
# the value does; this says the operator sends it, by naming the form field, the
# column, or the query parameter that carries it. An axis with neither a route
# converter on the journey nor an entry here is describing something the run does
# not send, and multiplying the journey over it produces the same run repeatedly.
# ---------------------------------------------------------------------------
SUPPLIED_BY: dict[str, str] = {
    # money
    'payment_method': 'the method form field on /payment/process',
    'insurance_coverage': 'the insurance_coverage form field the receptionist types',
    'cash_amount': 'the amount form field on /payment/process',
    'payment_amount_over_remaining': 'the amount form field on /payment/process',
    'line_item_count': 'the repeated add-service form fields on /reception/visits/<id>/add-service',
    'invoice_status': 'the state written by the invoice posting route',
    'journal_status': 'the status column on GLJournal, written by the posting route',
    'journal_source_type': 'the source_type the posting route stamps on the journal',
    'currency': 'the currency column on the price row',
    'insurance_claim_status': 'the status column on InsuranceClaim, written by adjudication',
    'insurance_claim_outcome': 'the adjudication form field on the claim route',
    'force_payment_ratio': 'derived from the counts the gate reads, not an input',
    # visit and appointment state
    'visit_state': 'the state machine Visit.transition_to drives',
    'visit_workflow_status': 'the status the reception visit routes write',
    'visit_archive_status': 'the archive flag set by /finance/visits/<id>/archive',
    'visit_type': 'the visit_type form field on /reception/visits/create',
    'payment_status': 'Visit.payment_status, written by /payment/process',
    'appointment_status': 'the appointment status written by the reception appointment routes',
    'appointment_state': 'the appointment status written by the reception appointment routes',
    'booking_state': 'the booking state written by /booking/create and the checkin route',
    'queue_state': 'QueueManagement.status, written by the skip and return routes',
    'task_state': 'the status form field on /nurse/tasks/<id>/status',
    'task_priority': 'the priority form field on /nurse/tasks/create',
    # emergency
    'triage_level': 'the triage form field on /emergency/triage/<emergency_id>',
    'emergency_severity': 'the severity form field on /emergency/cases/create',
    'emergency_status': 'the status the emergency routes write',
    'admission_type': 'the admission_type form field on /bed/api/admissions/admit',
    'admission_status': 'the status written by the discharge and transfer routes',
    'discharge_type': 'the discharge_type form field on the discharge route',
    # diagnostics
    'lab_result_status': 'the status form field on the result-entry route',
    'lab_order_status': 'the status the lab worklist routes advance',
    'lab_result_flag': 'the interpretation form field on the result-entry route',
    'radiology_modality': 'the modality form field on the radiology request route',
    'radiology_result_status': 'the status form field on the report route',
    'radiology_order_status': 'the status the radiology worklist routes advance',
    'dicom_study_status': 'the status column on DICOMStudy, written by no route',
    # pharmacy
    'prescription_state': 'the state the prescribing and dispensing routes write',
    'medication_status': 'the status form field on /medication/add and /medication/edit',
    'drug_interaction_severity': 'the severity column on DrugInteraction',
    'emar_status': 'the administration status, on a table no route reaches',
    'supply_request_status': 'the status the approve and fulfil routes write',
    'stock_movement_type': 'the movement_type form field on the ledger routes',
    'vaccine_route': 'the route form field on the vaccination route',
    'vaccine_status': 'the status written by the vaccination route',
    # clinical record
    'problem_severity': 'the severity form field on the problem-add route',
    'problem_status': 'the status the problem toggle route flips',
    'problem_type': 'the problem_type form field on the problem-add route',
    'diagnosis_type': 'the diagnosis_type form field on the diagnosis route',
    'diagnosis_status': 'the status form field on the diagnosis route',
    'follow_up_status': 'the status the follow-up routes write',
    'treatment_status': 'the status form field on the treatment routes',
    'procedure_status': 'the status the procedure routes write',
    'referral_status': 'the referral status column, with no create endpoint',
    'referral_urgency': 'the urgency form field on the referral route',
    'ward_type': 'the ward_type column on Ward, written when the ward is created',
    'bed_type': 'the bed_type form field on the bed route',
    'bed_status': 'the status the admit and discharge routes write',
    'room_type': 'the type column on Room',
    'surgery_type': 'the surgery_type column, with no writer route',
    'surgery_priority': 'the priority column, with no writer route',
    'surgery_status': 'the status column, with no writer route',
    'workflow_status': 'the status the form and handover routes write',
    'staff_schedule_status': 'the status form field on the schedule and absence routes',
    # access control
    'actor_role': 'the role the session user holds, which the decorator reads',
    'permission_level': 'the level form field on the permission-create route',
    'permission_category': 'the category form field on the permission-create route',
    'login_outcome': 'the outcome the credential check reaches with these credentials',
    'mfa_method': 'the method form field on /mfa/setup',
    'sso_protocol': 'the protocol form field on /sso/config',
    'audit_action': 'written by the audit writer, not sent by the operator',
    'entity_type': 'written by the audit writer, not sent by the operator',
    'security_event_type': 'the event type the security writer stamps',
    'security_severity': 'the severity the security event is filed at',
    'log_level': 'the level the system log line is written at',
    # platform configuration
    'tenant_status': 'the status form field on the tenant create and edit routes',
    'product_profile': 'the product_profile form field on the tenant create route',
    'storage_mode': 'the storage_mode form field on the profile route',
    'module_name': 'the module_name path converter on the module entitlement route',
    'module_status': 'the row the activate and deactivate routes write',
    'bundle_kind': 'the bundle profile the plan is built from',
    'subscription_type': 'the billing_type on the subscription line',
    'config_category': 'the category form field on the config save route',
    'config_type': 'the config_type form field on the config save route',
    'notification_event_type': 'the event_type form field on the rule-create route',
    'notification_channel': 'the channel form field on the rule-create route',
    'notification_priority': 'the priority the notification is queued with',
    'notification_state': 'the state the delivery worker writes',
    'support_ticket_category': 'the category form field on the ticket route',
    'backup_type': 'the backup_type form field on the backup-create route',
    'backup_status': 'the status the backup job writes',
    'backup_schedule_type': 'the schedule_type form field on the schedule route',
    'report_execution_state': 'the state the report run writes',
    'print_doc_type': 'the document the print route is asked for',
    # integration
    'hl7_message_type': 'the message type inside the posted HL7 payload',
    'telemedicine_outcome': 'the status the four outcome routes write',
}


def supplied_by(axis: str) -> str | None:
    """Where the value for this axis is supplied, or None if nothing supplies it."""
    return SUPPLIED_BY.get(axis)


def effects_for(template) -> dict[str, str]:
    out: dict[str, str] = {}
    for axis in template.axes:
        override = TEMPLATE_EFFECTS.get(template.key, {}).get(axis)
        out[axis] = override if override is not None else AXIS_EFFECTS.get(axis, '')
    return {axis: text for axis, text in out.items() if text}
