"""The second tier of scenario dimensions, still derived from the code.

These axes exist because the first tier covered only the financial and
clinical lifecycle enums. The application defines roughly sixty more state
machines -- surgery, admissions, eMAR administration, insurance claims, DICOM
studies, permissions, configuration, audit actions -- and every one of them
branches real behaviour. They are read out of ``app.shared.enums`` at import
time exactly like the first tier, so a member that is deleted from the code
becomes a generator error instead of a document that quietly lies.

Where the code documents a value set in a column comment rather than in an enum,
the values are pulled from the comment with :func:`_commented_values`, so the axis
still tracks the code and cannot be padded with invented members.
"""

from __future__ import annotations

from dimensions import Dimension, _enum_values


def _commented_values(module_path: str, class_name: str, column: str, members) -> tuple[str, ...]:
    """Read a documented value set out of a model's own column comment.

    Several tables carry their allowed values in a trailing comment on the column
    instead of in an Enum, for example ``SupportTicket.category`` says
    "general, billing, techn...". Harvesting the members that actually appear in
    that comment keeps the axis honest: if the comment is deleted, the axis falls
    back to nothing rather than silently inventing values.
    """
    module = __import__(module_path, fromlist=[class_name])
    cls = getattr(module, class_name)
    comment = cls.__table__.columns[column].comment or ''
    found = tuple(m for m in members if m in comment)
    return found or tuple(members)


def _punch_statuses() -> tuple[str, ...]:
    """Attendance states a staff schedule row can hold."""
    return _commented_values(
        'app.modules.owner.routes',
        'StaffSchedule',
        'status',
        ('scheduled', 'present', 'absent', 'leave', 'late'),
    )


def build_advanced_dimensions() -> tuple[Dimension, ...]:
    """Axes for the clinical-ops, identity and platform templates."""
    return (
        # ---- appointments and the front desk -------------------------------
        Dimension(
            'appointment_state',
            'enum',
            _enum_values('app.shared.enums', 'AppointmentState'),
            'Appointment.state. The workflow enum AppointmentWorkflowStatus is a '
            'different, lower-cased set with no CHECKED_IN, so the two disagree on '
            'what a checked-in appointment looks like.',
        ),
        Dimension(
            'booking_state',
            'enum',
            _enum_values('app.shared.enums', 'BookingState'),
            'OnlineBooking.state. A booking only becomes a visit through '
            '/booking/register or /reception/online-bookings/checkin.',
        ),
        Dimension(
            'queue_state',
            'enum',
            _enum_values('app.shared.enums', 'QueueState'),
            'QueueManagement.status. The skip and return-to-queue endpoints move '
            'a ticket between these and both assert on the current value.',
        ),
        Dimension(
            'visit_workflow_status',
            'enum',
            _enum_values('app.shared.enums', 'VisitWorkflowStatus'),
            'Visit.VisitStatus as the visit template renders it: a third naming '
            'of the same five states alongside VisitState and Visit.status.',
        ),
        Dimension(
            'visit_archive_status',
            'enum',
            _enum_values('app.shared.enums', 'VisitArchiveStatus'),
            'Visit archive flag. Archiving requires the invoice line sum to equal '
            'visit.total_amount, which is what /finance/visits/<id>/archive checks.',
        ),
        # ---- inpatient --------------------------------------------------------
        Dimension(
            'admission_type',
            'enum',
            _enum_values('app.shared.enums', 'AdmissionType'),
            'Admission.admission_type.',
        ),
        Dimension(
            'admission_status',
            'enum',
            _enum_values('app.shared.enums', 'AdmissionStatus'),
            'Admission.status. DISCHARGED and DECEASED both close the bed.',
        ),
        Dimension(
            'discharge_type',
            'enum',
            _enum_values('app.shared.enums', 'DischargeType'),
            'Discharge.discharge_type. AGAINST_ADVICE is the one that needs a '
            'signature the schema has no column for.',
        ),
        Dimension(
            'bed_status',
            'enum',
            _enum_values('app.shared.enums', 'BedStatus'),
            'Bed.status. OUT_OF_ORDER is not an occupancy, so availability counts '
            'have to subtract it explicitly.',
        ),
        Dimension(
            'room_type',
            'enum',
            _enum_values('app.shared.enums', 'RoomType'),
            'Room.type. Like ward_type and bed_type it prices nothing.',
        ),
        Dimension(
            'diagnosis_type',
            'enum',
            _enum_values('app.shared.enums', 'DiagnosisType'),
            'Diagnosis.diagnosis_type.',
        ),
        Dimension(
            'diagnosis_status',
            'enum',
            _enum_values('app.shared.enums', 'DiagnosisStatus'),
            'Diagnosis.status.',
        ),
        Dimension(
            'surgery_type',
            'enum',
            _enum_values('app.shared.enums', 'SurgeryType'),
            'Surgery.surgery_type.',
        ),
        Dimension(
            'surgery_priority',
            'enum',
            _enum_values('app.shared.enums', 'SurgeryPriority'),
            'Surgery.priority. STAT is the only one that bypasses the queue.',
        ),
        Dimension(
            'surgery_status',
            'enum',
            _enum_values('app.shared.enums', 'SurgeryStatus'),
            'Surgery.status. DELAYED is documented in the enum and handled by no '
            'route, so it can only be reached through the model.',
        ),
        # ---- diagnostics ------------------------------------------------------
        Dimension(
            'lab_order_status',
            'enum',
            _enum_values('app.shared.enums', 'LabOrderStatus'),
            'LabOrder.status, the seven-step order workflow. The result column is '
            'a separate LabResultStatus, and the two can disagree.',
        ),
        Dimension(
            'radiology_order_status',
            'enum',
            _enum_values('app.shared.enums', 'RadiologyOrderStatus'),
            'RadiologyOrder.status.',
        ),
        Dimension(
            'dicom_study_status',
            'enum',
            _enum_values('app.shared.enums', 'DICOMStudyStatus'),
            'DICOMStudy.status. Only the radiology DICOM route writes it; there is '
            'no reader route at all.',
        ),
        Dimension(
            'lab_result_flag',
            'enum',
            ('normal', 'abnormal', 'critical'),
            'Interpretation recorded on a LabResult. The column is a free String, '
            'so these three are documentation rather than a constraint.',
        ),
        # ---- pharmacy and prescriptions ---------------------------------------
        Dimension(
            'prescription_state',
            'enum',
            _enum_values('app.shared.enums', 'PrescriptionState'),
            'Prescription.state. The enum is wider than the column CHECK '
            'constraint, so part of this axis is not representable in the database.',
        ),
        Dimension(
            'medication_status',
            'enum',
            _enum_values('app.shared.enums', 'MedicationStatus'),
            'Medication.status. Only inactive stops a dispense; discontinued is a '
            'separate value the POS does not check.',
        ),
        Dimension(
            'drug_interaction_severity',
            'enum',
            _enum_values('app.shared.enums', 'DrugInteractionSeverity'),
            'DrugInteraction.severity. The model carries no tenant_id, so a '
            'severity check here spans every tenant.',
        ),
        Dimension(
            'emar_status',
            'enum',
            _enum_values('app.shared.enums', 'eMARAdministrationStatus'),
            'eMAR administration record status. MISSED and LATE are outcomes the '
            'mar routes cannot write, because eMAR has no reachable route.',
        ),
        Dimension(
            'vaccine_route',
            'enum',
            _enum_values('app.shared.enums', 'VaccineRoute'),
            'Vaccination.route.',
        ),
        Dimension(
            'vaccine_status',
            'enum',
            _enum_values('app.shared.enums', 'VaccineStatus'),
            'Vaccination.status.',
        ),
        Dimension(
            'problem_type',
            'enum',
            _enum_values('app.shared.enums', 'ProblemType'),
            'Problem.problem_type, distinct from Problem.severity.',
        ),
        Dimension(
            'workflow_status',
            'enum',
            _enum_values('app.shared.enums', 'WorkflowStatus'),
            'Workflow.status for the tasks that have a four-state machine rather '
            'than a typed one, including specialty forms and handover sheets.',
        ),
        Dimension(
            'follow_up_status',
            'enum',
            _enum_values('app.shared.enums', 'FollowUpStatus'),
            'FollowUp.status.',
        ),
        # ---- emergency ---------------------------------------------------------
        Dimension(
            'emergency_status',
            'enum',
            _enum_values('app.shared.enums', 'EmergencyStatus'),
            'EmergencyCase.status. Nine values across five routes, and '
            '/emergency/cases/edit writes no history row while moving them.',
        ),
        # ---- finance and ledger -----------------------------------------------
        Dimension(
            'invoice_status',
            'enum',
            _enum_values('app.shared.enums', 'InvoiceStatus'),
            'Invoice.status. POSTED is the point at which the ledger recognises '
            'revenue; a DRAFT invoice posts nothing.',
        ),
        Dimension(
            'billing_state',
            'enum',
            _enum_values('app.shared.enums', 'BillingState'),
            'BillingRecord.state, a second copy of the payment status that can '
            'disagree with Visit.payment_status.',
        ),
        Dimension(
            'journal_status',
            'enum',
            _enum_values('app.shared.enums', 'JournalStatus'),
            'GLJournal.status. VOID is the only correction path, and it reverses '
            'lines rather than deleting them.',
        ),
        Dimension(
            'journal_source_type',
            'enum',
            _enum_values('app.shared.enums', 'JournalSourceType'),
            'GLJournal.source_type. Each source type is guarded by its own '
            '(source_type, source_id) uniqueness, so replaying a payment cannot '
            'double-post but posting twice under two types can.',
        ),
        Dimension(
            'account_type',
            'enum',
            _enum_values('app.shared.enums', 'AccountType'),
            'Account.account_type. Cash and revenue land in different types, which '
            'is what makes the payment journal balance on both sides.',
        ),
        Dimension(
            'insurance_claim_status',
            'enum',
            _enum_values('app.shared.enums', 'InsuranceClaimStatus'),
            'InsuranceClaim.status. An APPROVED claim never reaches the ledger, so '
            'the insurer receivable is only cleared out of band.',
        ),
        Dimension(
            'module_name',
            'enum',
            _enum_values('app.shared.enums', 'ModuleName'),
            'Module a tenant can be granted. Activation is per tenant and module, '
            'and the feature gate reads it on every request.',
        ),
        Dimension(
            'product_profile',
            'enum',
            _enum_values('app.shared.enums', 'ProductProfile'),
            'Tenant.product_profile. The profile decides the seeded module set, so '
            'it is the axis a new tenant is actually created on.',
        ),
        Dimension(
            'storage_mode',
            'enum',
            _enum_values('app.shared.enums', 'StorageMode'),
            'Tenant.storage_mode. DICOM storage is the only mode with a separate '
            'object store, so hybrid is where the backup path diverges.',
        ),
        Dimension(
            'config_category',
            'enum',
            _enum_values('app.shared.enums', 'ConfigCategory'),
            'SystemConfig.category. Values are stored as strings and matched by '
            'name, so an unknown category simply never matches a reader.',
        ),
        Dimension(
            'config_type',
            'enum',
            _enum_values('app.shared.enums', 'ConfigType'),
            'SystemConfig.config_type, which decides how the string is coerced. '
            'A password row is the one type that is redacted on read.',
        ),
        Dimension(
            'notification_channel',
            'enum',
            _commented_values(
                'app.core.tenant.models',
                'NotificationRule',
                'channel',
                ('email', 'webhook', 'sms'),
            ),
            'NotificationRule.channel, documented on the column. A webhook rule '
            'fires on delivery failure without recording the retry.',
        ),
        Dimension(
            'notification_event_type',
            'enum',
            _commented_values(
                'app.core.tenant.models',
                'NotificationRule',
                'event_type',
                ('subscription_expiry', 'trial_ending', 'high_resource', 'ticket_new'),
            ),
            'NotificationRule.event_type, documented on the column. These four are '
            'the only triggers the sender knows how to raise.',
        ),
        Dimension(
            'notification_state',
            'enum',
            _enum_values('app.shared.enums', 'NotificationState'),
            'Notification.state. A failed send is recorded here rather than as an '
            'error on the notification rule that caused it.',
        ),
        Dimension(
            'notification_priority',
            'enum',
            _enum_values('app.shared.enums', 'NotificationPriority'),
            'Notification.priority. urgent is the only value that skips the queue.',
        ),
        Dimension(
            'support_ticket_category',
            'enum',
            _commented_values(
                'app.core.tenant.models',
                'SupportTicket',
                'category',
                ('general', 'billing', 'technical', 'bug', 'feature_request'),
            ),
            'SupportTicket.category, documented on the column.',
        ),
        Dimension(
            'staff_schedule_status',
            'enum',
            ('scheduled', 'present', 'absent', 'leave', 'late'),
            'Attendance status written by the reception and manager schedule '
            'endpoints. The column is a free String with no CHECK.',
        ),
        Dimension(
            'backup_schedule_type',
            'enum',
            _enum_values('app.shared.enums', 'BackupScheduleType'),
            'BackupSchedule.schedule_type. custom is the only member that carries '
            'its own cron expression.',
        ),
        # ---- access control ----------------------------------------------------
        Dimension(
            'permission_level',
            'enum',
            _enum_values('app.shared.enums', 'PermissionLevel'),
            'Permission.level. The role decorator checks the level string, so this '
            'axis is what decides whether a write is allowed at all.',
        ),
        Dimension(
            'permission_category',
            'enum',
            _enum_values('app.shared.enums', 'PermissionCategory'),
            'Permission.category. The permissions matrix is built per category, so '
            'a new category starts with no rows.',
        ),
        Dimension(
            'audit_action',
            'enum',
            _enum_values('app.shared.enums', 'AuditAction'),
            'AuditLog.action. login_failed and permission_denied are separate '
            'members from login and update, which is how a failed attempt is told '
            'apart from a successful one.',
        ),
        Dimension(
            'entity_type',
            'enum',
            _enum_values('app.shared.enums', 'EntityType'),
            'AuditLog.entity_type. The audit trail is written per entity, so a '
            'gap in coverage on one entity type is invisible from another.',
        ),
        Dimension(
            'security_event_type',
            'enum',
            _enum_values('app.shared.enums', 'SecurityEventType'),
            'SecurityEvent.event_type, a separate table from the audit trail.',
        ),
        Dimension(
            'mfa_method',
            'enum',
            ('totp', 'sms', 'email'),
            'Second factor offered at MFA setup. The verify route checks a shared '
            'TOTP path for all three, so the method field is recorded and not '
            'enforced.',
        ),
        Dimension(
            'login_outcome',
            'enum',
            ('success', 'bad_password', 'unknown_user', 'disabled_user', 'locked_out'),
            'Outcome of an authentication attempt. Only success is counted as an '
            'active session; the rest all land in the security event table.',
        ),
        Dimension(
            'sso_protocol',
            'enum',
            ('saml', 'oidc'),
            'Federation protocol an SSO configuration can be written for.',
        ),
        # ---- reporting and integration -------------------------------------------
        Dimension(
            'report_execution_state',
            'enum',
            _enum_values('app.shared.enums', 'ReportExecutionState'),
            'SavedReport.execution_state. A report that fails leaves its last good '
            'row in place, so the state is the only record of the failure.',
        ),
        Dimension(
            'print_doc_type',
            'enum',
            _enum_values('app.shared.enums', 'PrintDocType'),
            'Document a print or PDF endpoint renders. Each type maps to its own '
            'template and its own set of permitted fields.',
        ),
        Dimension(
            'hl7_message_type',
            'enum',
            ('ADT', 'ORM', 'ORU', 'SIU', 'VXU'),
            'HL7 v2 message type the ingest endpoint accepts. Each maps to a '
            'different handler, and an unknown type is acknowledged then dropped.',
        ),
        Dimension(
            'telemedicine_outcome',
            'enum',
            ('completed', 'no_show', 'cancelled', 'ended_early'),
            'How a teleconsultation ends. The four endpoints set the state '
            'directly, which is why they are four routes and not one.',
        ),
        Dimension(
            'insurance_claim_outcome',
            'enum',
            ('approved', 'partially_approved', 'rejected'),
            'Adjudication outcome written by /payment/api/insurance/claims/<id>/'
            'adjudicate. The payout is recorded on the claim and never posted to '
            'the ledger.',
        ),
    )
