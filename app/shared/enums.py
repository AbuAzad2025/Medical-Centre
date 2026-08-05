"""
Shared Enums and Constants — المصدر الوحيد لجميع الحالات والقيم
All workflow and model enums consolidated into one place.
"""

from enum import Enum, StrEnum

# =============================================================================
# Subscription & Tenant
# =============================================================================


class SubscriptionType(StrEnum):
    PERPETUAL = 'perpetual'
    MONTHLY = 'monthly'
    YEARLY = 'yearly'


class TenantStatus(StrEnum):
    ACTIVE = 'active'
    SUSPENDED = 'suspended'
    PENDING = 'pending'
    TRIAL = 'trial'
    EXPIRED = 'expired'
    CANCELLED = 'cancelled'
    DELETED = 'deleted'


class StorageMode(StrEnum):
    CLOUD = 'cloud'
    LOCAL = 'local'
    HYBRID = 'hybrid'


class ProductProfile(StrEnum):
    PRIVATE_DOCTOR_CLINIC = 'private_doctor_clinic'
    SMALL_CLINIC = 'small_clinic'
    STANDALONE_LAB = 'standalone_lab'
    STANDALONE_RADIOLOGY = 'standalone_radiology'
    STANDALONE_PHARMACY = 'standalone_pharmacy'
    MULTI_DEPARTMENT_CENTER = 'multi_department_center'
    CUSTOM = 'custom'


class ModuleName(StrEnum):
    RECEPTION = 'reception'
    DOCTOR = 'doctor'
    LAB = 'lab'
    RADIOLOGY = 'radiology'
    PHARMACY = 'pharmacy'
    EMERGENCY = 'emergency'
    NURSING = 'nursing'
    BILLING = 'billing'
    INVENTORY = 'inventory'
    REPORTING = 'reporting'
    APPOINTMENTS = 'appointments'
    OWNER = 'owner'
    PORTAL = 'portal'
    AI_IMAGING = 'ai_imaging'
    ACCOUNTING = 'accounting'
    ADMIN = 'admin'
    MANAGER = 'manager'
    DICOM = 'dicom'


# =============================================================================
# Visits
# =============================================================================


class VisitState(StrEnum):
    """Clinical lifecycle states stored in visit.status (ends at COMPLETED)."""

    OPEN = 'OPEN'
    CHECKED_IN = 'CHECKED_IN'
    IN_PROGRESS = 'IN_PROGRESS'
    COMPLETED = 'COMPLETED'
    CANCELLED = 'CANCELLED'


class VisitArchiveStatus(StrEnum):
    """Administrative retention flag on visit.archive_status (GatekeeperService)."""

    ACTIVE = 'ACTIVE'
    ARCHIVED = 'ARCHIVED'


class VisitWorkflowStatus(StrEnum):
    """Internal workflow states for visit state machine."""

    REGISTERED = 'registered'
    WAITING = 'waiting'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    ARCHIVED = 'archived'
    CANCELLED = 'cancelled'


class VisitType(StrEnum):
    REGULAR = 'REGULAR'
    FOLLOW_UP = 'FOLLOW_UP'
    CONSULTATION = 'CONSULTATION'
    EMERGENCY = 'EMERGENCY'


class PaymentStatus(StrEnum):
    PENDING = 'PENDING'
    PAID = 'PAID'
    PARTIAL = 'PARTIAL'
    DEBT = 'DEBT'
    EMERGENCY_DEBT = 'EMERGENCY_DEBT'
    CONFIRMED = 'CONFIRMED'
    REFUNDED = 'REFUNDED'
    CANCELLED = 'CANCELLED'


class PaymentMethod(StrEnum):
    CASH = 'CASH'
    CARD = 'CARD'
    VISA = 'visa'
    MADA = 'mada'
    WIRE = 'WIRE'
    INSURANCE = 'INSURANCE'
    FORCE = 'FORCE'


# =============================================================================
# Appointments
# =============================================================================


class AppointmentState(StrEnum):
    """Database-level appointment states."""

    SCHEDULED = 'SCHEDULED'
    CONFIRMED = 'CONFIRMED'
    CHECKED_IN = 'CHECKED_IN'
    DONE = 'DONE'
    COMPLETED = 'COMPLETED'
    CANCELLED = 'CANCELLED'
    NO_SHOW = 'NO_SHOW'


class AppointmentWorkflowStatus(StrEnum):
    """Internal workflow states for appointment state machine."""

    SCHEDULED = 'scheduled'
    CONFIRMED = 'confirmed'
    CHECKED_IN = 'checked_in'
    IN_PROGRESS = 'in_progress'
    DONE = 'done'
    CANCELLED = 'cancelled'
    NO_SHOW = 'no_show'


# =============================================================================
# Orders (Lab & Radiology)
# =============================================================================


class OrderState(StrEnum):
    """Database-level lab/radiology order states."""

    REQUESTED = 'REQUESTED'
    RECEIVED = 'RECEIVED'
    ANALYZING = 'ANALYZING'
    REVIEWED = 'REVIEWED'
    APPROVED = 'APPROVED'
    IN_PROGRESS = 'IN_PROGRESS'
    DONE = 'DONE'
    CANCELLED = 'CANCELLED'


class LabOrderStatus(StrEnum):
    """Internal workflow states for lab order state machine."""

    ORDERED = 'ordered'
    SAMPLE_COLLECTED = 'sample_collected'
    IN_PROGRESS = 'in_progress'
    RESULTS_ENTERED = 'results_entered'
    APPROVED = 'approved'
    DELIVERED = 'delivered'
    CANCELLED = 'cancelled'


class RadiologyOrderStatus(StrEnum):
    """Internal workflow states for radiology order state machine."""

    ORDERED = 'ordered'
    SCHEDULED = 'scheduled'
    IN_PROGRESS = 'in_progress'
    IMAGES_CAPTURED = 'images_captured'
    REPORTED = 'reported'
    APPROVED = 'approved'
    DELIVERED = 'delivered'
    CANCELLED = 'cancelled'


class LabResultStatus(StrEnum):
    PENDING = 'PENDING'
    READY = 'READY'
    VALIDATED = 'VALIDATED'


class RadiologyResultStatus(StrEnum):
    PENDING = 'PENDING'
    READY = 'READY'
    VALIDATED = 'VALIDATED'


# =============================================================================
# Queue
# =============================================================================


class QueueState(StrEnum):
    WAITING = 'waiting'
    CALLED = 'called'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    SKIPPED = 'skipped'
    CANCELLED = 'cancelled'


# =============================================================================
# Billing & Invoices
# =============================================================================


class BillingState(StrEnum):
    PENDING = 'PENDING'
    PAID = 'PAID'
    PARTIAL = 'PARTIAL'
    DEBT = 'DEBT'
    CANCELLED = 'CANCELLED'
    REFUNDED = 'REFUNDED'


class InvoiceStatus(StrEnum):
    """Workflow states for invoice lifecycle."""

    DRAFT = 'DRAFT'
    ISSUED = 'ISSUED'
    POSTED = 'POSTED'
    PAID = 'PAID'
    VOID = 'VOID'


# =============================================================================
# Prescriptions & Medications
# =============================================================================


class PrescriptionState(StrEnum):
    DRAFT = 'draft'
    ISSUED = 'issued'
    ACTIVE = 'active'
    DISPENSED = 'dispensed'
    PARTIAL = 'partial'
    CANCELLED = 'cancelled'
    EXPIRED = 'expired'


class MedicationStatus(StrEnum):
    ACTIVE = 'active'
    INACTIVE = 'inactive'
    DISCONTINUED = 'discontinued'


class StockMovementType(StrEnum):
    PURCHASE = 'purchase'
    SALE = 'sale'
    RETURN = 'return'
    ADJUSTMENT = 'adjustment'
    EXPIRED = 'expired'
    TRANSFER_IN = 'transfer_in'
    TRANSFER_OUT = 'transfer_out'


# =============================================================================
# Booking
# =============================================================================


class BookingState(StrEnum):
    PENDING = 'pending'
    CONFIRMED = 'confirmed'
    CANCELLED = 'cancelled'
    CONVERTED = 'converted'
    EXPIRED = 'expired'


# =============================================================================
# Notifications
# =============================================================================


class NotificationState(StrEnum):
    PENDING = 'pending'
    SENT = 'sent'
    FAILED = 'failed'
    READ = 'read'


class NotificationPriority(StrEnum):
    LOW = 'low'
    NORMAL = 'normal'
    HIGH = 'high'
    URGENT = 'urgent'


# =============================================================================
# Tasks & Projects
# =============================================================================


class TaskState(StrEnum):
    PENDING = 'pending'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'


class TaskPriority(StrEnum):
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    URGENT = 'urgent'


class ProjectState(StrEnum):
    PLANNING = 'planning'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'
    ON_HOLD = 'on_hold'


# =============================================================================
# Emergency
# =============================================================================


class EmergencyStatus(StrEnum):
    NEW = 'NEW'
    WAITING = 'WAITING'
    TRIAGE = 'TRIAGE'
    RESUSCITATION = 'RESUSCITATION'
    TREATMENT = 'TREATMENT'
    OBSERVATION = 'OBSERVATION'
    IN_PROGRESS = 'IN_PROGRESS'
    COMPLETED = 'COMPLETED'
    TRANSFERRED = 'TRANSFERRED'


class EmergencySeverity(StrEnum):
    LOW = 'LOW'
    MODERATE = 'MODERATE'
    HIGH = 'HIGH'
    CRITICAL = 'CRITICAL'


# =============================================================================
# Bed Management
# =============================================================================


class WardType(StrEnum):
    GENERAL = 'GENERAL'
    ICU = 'ICU'
    NICU = 'NICU'
    PICU = 'PICU'
    MATERNITY = 'MATERNITY'
    SURGERY = 'SURGERY'
    ISOLATION = 'ISOLATION'


class RoomType(StrEnum):
    STANDARD = 'STANDARD'
    PRIVATE = 'PRIVATE'
    SEMI_PRIVATE = 'SEMI_PRIVATE'
    ICU_BAY = 'ICU_BAY'
    ISOLATION = 'ISOLATION'


class BedType(StrEnum):
    STANDARD = 'STANDARD'
    ELECTRIC = 'ELECTRIC'
    BARIATRIC = 'BARIATRIC'
    PEDIATRIC = 'PEDIATRIC'
    ICU = 'ICU'
    INCUBATOR = 'INCUBATOR'


class BedStatus(StrEnum):
    AVAILABLE = 'AVAILABLE'
    OCCUPIED = 'OCCUPIED'
    RESERVED = 'RESERVED'
    CLEANING = 'CLEANING'
    OUT_OF_ORDER = 'OUT_OF_ORDER'


class AdmissionType(StrEnum):
    ELECTIVE = 'ELECTIVE'
    EMERGENCY = 'EMERGENCY'
    URGENT = 'URGENT'
    TRANSFER = 'TRANSFER'
    READMISSION = 'READMISSION'


class AdmissionStatus(StrEnum):
    ADMITTED = 'ADMITTED'
    DISCHARGED = 'DISCHARGED'
    TRANSFERRED = 'TRANSFERRED'
    DECEASED = 'DECEASED'


# =============================================================================
# Clinical
# =============================================================================


class DiagnosisType(StrEnum):
    PRIMARY = 'PRIMARY'
    SECONDARY = 'SECONDARY'
    ADMITTING = 'ADMITTING'
    DISCHARGE = 'DISCHARGE'


class DiagnosisStatus(StrEnum):
    ACTIVE = 'ACTIVE'
    RESOLVED = 'RESOLVED'
    CHRONIC = 'CHRONIC'
    RELAPSE = 'RELAPSE'


class ProblemType(StrEnum):
    DIAGNOSIS = 'DIAGNOSIS'
    SYMPTOM = 'SYMPTOM'
    COMPLAINT = 'COMPLAINT'
    FUNCTIONAL_LIMITATION = 'FUNCTIONAL_LIMITATION'


class ProblemSeverity(StrEnum):
    MILD = 'MILD'
    MODERATE = 'MODERATE'
    SEVERE = 'SEVERE'
    LIFE_THREATENING = 'LIFE_THREATENING'


class ProblemStatus(StrEnum):
    ACTIVE = 'ACTIVE'
    CHRONIC = 'CHRONIC'
    RESOLVED = 'RESOLVED'
    RELAPSE = 'RELAPSE'
    IN_REMISSION = 'IN_REMISSION'
    RULED_OUT = 'RULED_OUT'


class DrugInteractionSeverity(StrEnum):
    LOW = 'LOW'
    MODERATE = 'MODERATE'
    HIGH = 'HIGH'


class TreatmentStatus(StrEnum):
    PENDING = 'pending'
    ACTIVE = 'active'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'
    FOLLOW_UP = 'follow_up'


class FollowUpStatus(StrEnum):
    PENDING = 'PENDING'
    SCHEDULED = 'SCHEDULED'
    DONE = 'DONE'
    CANCELLED = 'CANCELLED'


class ProcedureStatus(StrEnum):
    PLANNED = 'PLANNED'
    PERFORMED = 'PERFORMED'
    CANCELLED = 'CANCELLED'


# =============================================================================
# Backup & System
# =============================================================================


class BackupType(StrEnum):
    FULL = 'full'
    INCREMENTAL = 'incremental'
    DIFFERENTIAL = 'differential'


class BackupStatus(StrEnum):
    PENDING = 'PENDING'
    IN_PROGRESS = 'IN_PROGRESS'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    CANCELLED = 'CANCELLED'


class BackupScheduleType(StrEnum):
    DAILY = 'daily'
    WEEKLY = 'weekly'
    MONTHLY = 'monthly'
    CUSTOM = 'custom'


class LogLevel(StrEnum):
    DEBUG = 'DEBUG'
    INFO = 'INFO'
    WARNING = 'WARNING'
    ERROR = 'ERROR'
    CRITICAL = 'CRITICAL'


class ConfigType(StrEnum):
    STRING = 'string'
    INTEGER = 'integer'
    BOOLEAN = 'boolean'
    JSON = 'json'
    FILE = 'file'
    PASSWORD = 'password'


class ConfigCategory(StrEnum):
    GENERAL = 'general'
    SECURITY = 'security'
    NOTIFICATION = 'notification'
    BACKUP = 'backup'
    SYSTEM = 'system'
    DATABASE = 'database'
    EMAIL = 'email'
    SMS = 'sms'


class AuditAction(StrEnum):
    CREATE = 'create'
    UPDATE = 'update'
    DELETE = 'delete'
    VIEW = 'view'
    LOGIN = 'login'
    LOGOUT = 'logout'
    EXPORT = 'export'
    IMPORT_ = 'import'
    BACKUP = 'backup'
    RESTORE = 'restore'
    SECURITY = 'security'
    LOGIN_FAILED = 'login_failed'
    LOGIN_BLOCKED = 'login_blocked'
    FORCE_LOGOUT = 'force_logout'
    PERMISSION_DENIED = 'permission_denied'
    UNAUTHORIZED_ACCESS = 'unauthorized_access'


class EntityType(StrEnum):
    SYSTEM = 'system'
    USER = 'user'
    PATIENT = 'patient'
    VISIT = 'visit'
    APPOINTMENT = 'appointment'
    PAYMENT = 'payment'
    INVOICE = 'invoice'
    LAB_TEST = 'lab_test'
    RADIOLOGY_TEST = 'radiology_test'
    NOTIFICATION = 'notification'
    ROLE = 'role'
    DEPARTMENT = 'department'


class SecurityEventType(StrEnum):
    LOGIN_FAILED = 'login_failed'
    PASSWORD_CHANGED = 'password_changed'
    PERMISSION_DENIED = 'permission_denied'
    SUSPICIOUS_ACTIVITY = 'suspicious_activity'
    DATA_BREACH = 'data_breach'
    UNAUTHORIZED_ACCESS = 'unauthorized_access'


class SecuritySeverity(StrEnum):
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    CRITICAL = 'critical'


# =============================================================================
# Permissions
# =============================================================================


class PermissionLevel(Enum):
    """مستويات الصلاحيات"""

    READ = 'read'
    WRITE = 'write'
    DELETE = 'delete'
    ADMIN = 'admin'
    SUPER_ADMIN = 'super_admin'

    @property
    def label_ar(self):
        return {
            'READ': 'قراءة',
            'WRITE': 'كتابة',
            'DELETE': 'حذف',
            'ADMIN': 'إدارة',
            'SUPER_ADMIN': 'إدارة عليا',
        }[self.name]


class PermissionCategory(Enum):
    """فئات الصلاحيات"""

    USER_MANAGEMENT = 'user_management'
    PATIENT_MANAGEMENT = 'patient_management'
    MEDICAL_RECORDS = 'medical_records'
    FINANCIAL = 'financial'
    SYSTEM_ADMIN = 'system_admin'
    BACKUP_RESTORE = 'backup_restore'
    REPORTS = 'reports'
    SETTINGS = 'settings'
    SECURITY = 'security'
    AUDIT = 'audit'

    @property
    def label_ar(self):
        return {
            'USER_MANAGEMENT': 'إدارة المستخدمين',
            'PATIENT_MANAGEMENT': 'إدارة المرضى',
            'MEDICAL_RECORDS': 'السجلات الطبية',
            'FINANCIAL': 'النظام المالي',
            'SYSTEM_ADMIN': 'إدارة النظام',
            'BACKUP_RESTORE': 'النسخ الاحتياطي والاستعادة',
            'REPORTS': 'التقارير',
            'SETTINGS': 'الإعدادات',
            'SECURITY': 'الأمان',
            'AUDIT': 'التدقيق',
        }[self.name]


# =============================================================================
# Other
# =============================================================================


class ReportExecutionState(StrEnum):
    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


class Currency(StrEnum):
    ILS = 'ILS'
    EGP = 'EGP'
    USD = 'USD'
    EUR = 'EUR'
    JOD = 'JOD'


class SurgeryType(StrEnum):
    ELECTIVE = 'ELECTIVE'
    EMERGENCY = 'EMERGENCY'
    URGENT = 'URGENT'


class SurgeryPriority(StrEnum):
    NORMAL = 'NORMAL'
    URGENT = 'URGENT'
    STAT = 'STAT'


class SurgeryStatus(StrEnum):
    SCHEDULED = 'SCHEDULED'
    CONFIRMED = 'CONFIRMED'
    IN_PROGRESS = 'IN_PROGRESS'
    COMPLETED = 'COMPLETED'
    CANCELLED = 'CANCELLED'
    DELAYED = 'DELAYED'


class ReferralUrgency(StrEnum):
    ROUTINE = 'ROUTINE'
    URGENT = 'URGENT'
    STAT = 'STAT'


class ReferralStatus(StrEnum):
    PENDING = 'PENDING'
    SENT = 'SENT'
    ACCEPTED = 'ACCEPTED'
    SCHEDULED = 'SCHEDULED'
    COMPLETED = 'COMPLETED'
    CANCELLED = 'CANCELLED'
    DECLINED = 'DECLINED'


class SupplyRequestStatus(StrEnum):
    DRAFT = 'DRAFT'
    APPROVED = 'APPROVED'
    FULFILLED = 'FULFILLED'
    CANCELLED = 'CANCELLED'


class eMARAdministrationStatus(StrEnum):
    SCHEDULED = 'SCHEDULED'
    GIVEN = 'GIVEN'
    NOT_GIVEN = 'NOT_GIVEN'
    HELD = 'HELD'
    REFUSED = 'REFUSED'
    PARTIAL = 'PARTIAL'
    MISSED = 'MISSED'
    LATE = 'LATE'


class InsuranceClaimStatus(StrEnum):
    DRAFT = 'DRAFT'
    SUBMITTED = 'SUBMITTED'
    APPROVED = 'APPROVED'
    REJECTED = 'REJECTED'
    PAID = 'PAID'


class DICOMStudyStatus(StrEnum):
    RECEIVED = 'RECEIVED'
    PENDING_REVIEW = 'PENDING_REVIEW'
    REVIEWED = 'REVIEWED'
    REPORTED = 'REPORTED'
    ARCHIVED = 'ARCHIVED'


class VaccineRoute(StrEnum):
    IM = 'IM'
    SC = 'SC'
    PO = 'PO'
    ID = 'ID'
    INTRANASAL = 'INTRANASAL'


class VaccineStatus(StrEnum):
    COMPLETED = 'COMPLETED'
    REFUSED = 'REFUSED'
    DEFERRED = 'DEFERRED'
    PARTIAL = 'PARTIAL'


class WorkflowStatus(StrEnum):
    ACTIVE = 'active'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'
    TRANSFERRED = 'transferred'


# =============================================================================
# Print documents (§34.2)
# =============================================================================


class PrintDocType(StrEnum):
    INVOICE = 'invoice'
    RECEIPT = 'receipt'
    PRESCRIPTION = 'prescription'
    QUEUE_TICKET = 'queue_ticket'
    BARCODE_LABEL = 'barcode_label'
    LAB_RESULT = 'lab_result'
    RADIOLOGY_REPORT = 'radiology_report'
    EMERGENCY_REPORT = 'emergency_report'
    MEDICAL_REPORT = 'report'
    PHARMACY_SALE = 'pharmacy_sale'


# =============================================================================
# Helper: export all enum values as a JSON-serializable dict
# =============================================================================


def get_all_enums_json() -> dict:
    """Return all enum names → {member_name: value} for frontend consumption."""
    result = {}
    for name, obj in globals().items():
        if isinstance(obj, type) and issubclass(obj, Enum) and obj is not Enum:
            result[name] = {m.name: m.value for m in obj}
    return result


def get_enum_values(name: str) -> dict | None:
    """Return a single enum's values by class name."""
    obj = globals().get(name)
    if isinstance(obj, type) and issubclass(obj, Enum) and obj is not Enum:
        return {m.name: m.value for m in obj}
    return None
