"""
Shared Enums and Constants — المصدر الوحيد لجميع الحالات والقيم
All workflow and model enums consolidated into one place.
"""
from enum import Enum

# =============================================================================
# Subscription & Tenant
# =============================================================================

class SubscriptionType(str, Enum):
    PERPETUAL = "perpetual"
    MONTHLY = "monthly"
    YEARLY = "yearly"

class TenantStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING = "pending"
    EXPIRED = "expired"
    DELETED = "deleted"

class StorageMode(str, Enum):
    CLOUD = "cloud"
    LOCAL = "local"
    HYBRID = "hybrid"

class ProductProfile(str, Enum):
    PRIVATE_DOCTOR_CLINIC = "private_doctor_clinic"
    SMALL_CLINIC = "small_clinic"
    STANDALONE_LAB = "standalone_lab"
    STANDALONE_RADIOLOGY = "standalone_radiology"
    STANDALONE_PHARMACY = "standalone_pharmacy"
    MULTI_DEPARTMENT_CENTER = "multi_department_center"
    CUSTOM = "custom"

class ModuleName(str, Enum):
    RECEPTION = "reception"
    DOCTOR = "doctor"
    LAB = "lab"
    RADIOLOGY = "radiology"
    PHARMACY = "pharmacy"
    EMERGENCY = "emergency"
    NURSING = "nursing"
    BILLING = "billing"
    INVENTORY = "inventory"
    REPORTING = "reporting"
    APPOINTMENTS = "appointments"
    OWNER = "owner"
    PORTAL = "portal"
    AI_IMAGING = "ai_imaging"
    ACCOUNTING = "accounting"
    ADMIN = "admin"
    MANAGER = "manager"
    DICOM = "dicom"

# =============================================================================
# Visits
# =============================================================================

class VisitState(str, Enum):
    """Database-level visit states (stored in visit.status)."""
    OPEN = "OPEN"
    CHECKED_IN = "CHECKED_IN"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"

class VisitWorkflowStatus(str, Enum):
    """Internal workflow states for visit state machine."""
    REGISTERED = "registered"
    WAITING = "waiting"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ARCHIVED = "archived"
    CANCELLED = "cancelled"

class VisitType(str, Enum):
    REGULAR = "REGULAR"
    FOLLOW_UP = "FOLLOW_UP"
    CONSULTATION = "CONSULTATION"
    EMERGENCY = "EMERGENCY"

class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    PARTIAL = "PARTIAL"
    DEBT = "DEBT"
    EMERGENCY_DEBT = "EMERGENCY_DEBT"
    CONFIRMED = "CONFIRMED"
    REFUNDED = "REFUNDED"
    CANCELLED = "CANCELLED"

class PaymentMethod(str, Enum):
    CASH = "CASH"
    CARD = "CARD"
    VISA = "visa"
    MADA = "mada"
    WIRE = "WIRE"
    INSURANCE = "INSURANCE"
    FORCE = "FORCE"

# =============================================================================
# Appointments
# =============================================================================

class AppointmentState(str, Enum):
    """Database-level appointment states."""
    SCHEDULED = "SCHEDULED"
    CONFIRMED = "CONFIRMED"
    CHECKED_IN = "CHECKED_IN"
    DONE = "DONE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"

class AppointmentWorkflowStatus(str, Enum):
    """Internal workflow states for appointment state machine."""
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    CHECKED_IN = "checked_in"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"

# =============================================================================
# Orders (Lab & Radiology)
# =============================================================================

class OrderState(str, Enum):
    """Database-level lab/radiology order states."""
    REQUESTED = "REQUESTED"
    RECEIVED = "RECEIVED"
    ANALYZING = "ANALYZING"
    REVIEWED = "REVIEWED"
    APPROVED = "APPROVED"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    CANCELLED = "CANCELLED"

class LabOrderStatus(str, Enum):
    """Internal workflow states for lab order state machine."""
    ORDERED = "ordered"
    SAMPLE_COLLECTED = "sample_collected"
    IN_PROGRESS = "in_progress"
    RESULTS_ENTERED = "results_entered"
    APPROVED = "approved"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

class RadiologyOrderStatus(str, Enum):
    """Internal workflow states for radiology order state machine."""
    ORDERED = "ordered"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    IMAGES_CAPTURED = "images_captured"
    REPORTED = "reported"
    APPROVED = "approved"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

class LabResultStatus(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    VALIDATED = "VALIDATED"

class RadiologyResultStatus(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    VALIDATED = "VALIDATED"

# =============================================================================
# Queue
# =============================================================================

class QueueState(str, Enum):
    WAITING = "waiting"
    CALLED = "called"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"

# =============================================================================
# Billing & Invoices
# =============================================================================

class BillingState(str, Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    PARTIAL = "PARTIAL"
    DEBT = "DEBT"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"

class InvoiceStatus(str, Enum):
    """Workflow states for invoice lifecycle."""
    DRAFT = "DRAFT"
    ISSUED = "ISSUED"
    POSTED = "POSTED"
    PAID = "PAID"
    VOID = "VOID"

# =============================================================================
# Prescriptions & Medications
# =============================================================================

class PrescriptionState(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    DISPENSED = "dispensed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    EXPIRED = "expired"

class MedicationStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DISCONTINUED = "discontinued"

class StockMovementType(str, Enum):
    PURCHASE = "purchase"
    SALE = "sale"
    RETURN = "return"
    ADJUSTMENT = "adjustment"
    EXPIRED = "expired"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"

# =============================================================================
# Booking
# =============================================================================

class BookingState(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    CONVERTED = "converted"
    EXPIRED = "expired"

# =============================================================================
# Notifications
# =============================================================================

class NotificationState(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    READ = "read"

class NotificationPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

# =============================================================================
# Tasks & Projects
# =============================================================================

class TaskState(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class ProjectState(str, Enum):
    PLANNING = "planning"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ON_HOLD = "on_hold"

# =============================================================================
# Emergency
# =============================================================================

class EmergencyStatus(str, Enum):
    NEW = "NEW"
    WAITING = "WAITING"
    TRIAGE = "TRIAGE"
    RESUSCITATION = "RESUSCITATION"
    TREATMENT = "TREATMENT"
    OBSERVATION = "OBSERVATION"
    COMPLETED = "COMPLETED"
    TRANSFERRED = "TRANSFERRED"

class EmergencySeverity(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

# =============================================================================
# Bed Management
# =============================================================================

class WardType(str, Enum):
    GENERAL = "GENERAL"
    ICU = "ICU"
    NICU = "NICU"
    PICU = "PICU"
    MATERNITY = "MATERNITY"
    SURGERY = "SURGERY"
    ISOLATION = "ISOLATION"

class RoomType(str, Enum):
    STANDARD = "STANDARD"
    PRIVATE = "PRIVATE"
    SEMI_PRIVATE = "SEMI_PRIVATE"
    ICU_BAY = "ICU_BAY"
    ISOLATION = "ISOLATION"

class BedType(str, Enum):
    STANDARD = "STANDARD"
    ELECTRIC = "ELECTRIC"
    BARIATRIC = "BARIATRIC"
    PEDIATRIC = "PEDIATRIC"
    ICU = "ICU"
    INCUBATOR = "INCUBATOR"

class BedStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    OCCUPIED = "OCCUPIED"
    RESERVED = "RESERVED"
    CLEANING = "CLEANING"
    OUT_OF_ORDER = "OUT_OF_ORDER"

class AdmissionType(str, Enum):
    ELECTIVE = "ELECTIVE"
    EMERGENCY = "EMERGENCY"
    URGENT = "URGENT"
    TRANSFER = "TRANSFER"
    READMISSION = "READMISSION"

class AdmissionStatus(str, Enum):
    ADMITTED = "ADMITTED"
    DISCHARGED = "DISCHARGED"
    TRANSFERRED = "TRANSFERRED"
    DECEASED = "DECEASED"

# =============================================================================
# Clinical
# =============================================================================

class DiagnosisType(str, Enum):
    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"
    ADMITTING = "ADMITTING"
    DISCHARGE = "DISCHARGE"

class DiagnosisStatus(str, Enum):
    ACTIVE = "ACTIVE"
    RESOLVED = "RESOLVED"
    CHRONIC = "CHRONIC"
    RELAPSE = "RELAPSE"

class ProblemType(str, Enum):
    DIAGNOSIS = "DIAGNOSIS"
    SYMPTOM = "SYMPTOM"
    COMPLAINT = "COMPLAINT"
    FUNCTIONAL_LIMITATION = "FUNCTIONAL_LIMITATION"

class ProblemSeverity(str, Enum):
    MILD = "MILD"
    MODERATE = "MODERATE"
    SEVERE = "SEVERE"
    LIFE_THREATENING = "LIFE_THREATENING"

class ProblemStatus(str, Enum):
    ACTIVE = "ACTIVE"
    CHRONIC = "CHRONIC"
    RESOLVED = "RESOLVED"
    RELAPSE = "RELAPSE"
    IN_REMISSION = "IN_REMISSION"
    RULED_OUT = "RULED_OUT"

class DrugInteractionSeverity(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"

class TreatmentStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FOLLOW_UP = "follow_up"

class FollowUpStatus(str, Enum):
    PENDING = "PENDING"
    SCHEDULED = "SCHEDULED"
    DONE = "DONE"
    CANCELLED = "CANCELLED"

class ProcedureStatus(str, Enum):
    PLANNED = "PLANNED"
    PERFORMED = "PERFORMED"
    CANCELLED = "CANCELLED"

# =============================================================================
# Backup & System
# =============================================================================

class BackupType(str, Enum):
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"

class BackupStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class BackupScheduleType(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"

class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class ConfigType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    JSON = "json"
    FILE = "file"
    PASSWORD = "password"

class ConfigCategory(str, Enum):
    GENERAL = "general"
    SECURITY = "security"
    NOTIFICATION = "notification"
    BACKUP = "backup"
    SYSTEM = "system"
    DATABASE = "database"
    EMAIL = "email"
    SMS = "sms"

class AuditAction(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    VIEW = "view"
    LOGIN = "login"
    LOGOUT = "logout"
    EXPORT = "export"
    IMPORT_ = "import"
    BACKUP = "backup"
    RESTORE = "restore"
    SECURITY = "security"
    LOGIN_FAILED = "login_failed"
    LOGIN_BLOCKED = "login_blocked"
    FORCE_LOGOUT = "force_logout"
    PERMISSION_DENIED = "permission_denied"
    UNAUTHORIZED_ACCESS = "unauthorized_access"

class EntityType(str, Enum):
    SYSTEM = "system"
    USER = "user"
    PATIENT = "patient"
    VISIT = "visit"
    APPOINTMENT = "appointment"
    PAYMENT = "payment"
    INVOICE = "invoice"
    LAB_TEST = "lab_test"
    RADIOLOGY_TEST = "radiology_test"
    NOTIFICATION = "notification"
    ROLE = "role"
    DEPARTMENT = "department"

class SecurityEventType(str, Enum):
    LOGIN_FAILED = "login_failed"
    PASSWORD_CHANGED = "password_changed"
    PERMISSION_DENIED = "permission_denied"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    DATA_BREACH = "data_breach"
    UNAUTHORIZED_ACCESS = "unauthorized_access"

class SecuritySeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

# =============================================================================
# Permissions
# =============================================================================

class PermissionLevel(Enum):
    """مستويات الصلاحيات"""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"

    @property
    def label_ar(self):
        return {
            "READ": "قراءة",
            "WRITE": "كتابة",
            "DELETE": "حذف",
            "ADMIN": "إدارة",
            "SUPER_ADMIN": "إدارة عليا",
        }[self.name]


class PermissionCategory(Enum):
    """فئات الصلاحيات"""
    USER_MANAGEMENT = "user_management"
    PATIENT_MANAGEMENT = "patient_management"
    MEDICAL_RECORDS = "medical_records"
    FINANCIAL = "financial"
    SYSTEM_ADMIN = "system_admin"
    BACKUP_RESTORE = "backup_restore"
    REPORTS = "reports"
    SETTINGS = "settings"
    SECURITY = "security"
    AUDIT = "audit"

    @property
    def label_ar(self):
        return {
            "USER_MANAGEMENT": "إدارة المستخدمين",
            "PATIENT_MANAGEMENT": "إدارة المرضى",
            "MEDICAL_RECORDS": "السجلات الطبية",
            "FINANCIAL": "النظام المالي",
            "SYSTEM_ADMIN": "إدارة النظام",
            "BACKUP_RESTORE": "النسخ الاحتياطي والاستعادة",
            "REPORTS": "التقارير",
            "SETTINGS": "الإعدادات",
            "SECURITY": "الأمان",
            "AUDIT": "التدقيق",
        }[self.name]

# =============================================================================
# Other
# =============================================================================

class ReportExecutionState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Currency(str, Enum):
    ILS = "ILS"
    EGP = "EGP"
    USD = "USD"
    EUR = "EUR"
    JOD = "JOD"

class SurgeryType(str, Enum):
    ELECTIVE = "ELECTIVE"
    EMERGENCY = "EMERGENCY"
    URGENT = "URGENT"

class SurgeryPriority(str, Enum):
    NORMAL = "NORMAL"
    URGENT = "URGENT"
    STAT = "STAT"

class SurgeryStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    CONFIRMED = "CONFIRMED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    DELAYED = "DELAYED"

class ReferralUrgency(str, Enum):
    ROUTINE = "ROUTINE"
    URGENT = "URGENT"
    STAT = "STAT"

class ReferralStatus(str, Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    ACCEPTED = "ACCEPTED"
    SCHEDULED = "SCHEDULED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    DECLINED = "DECLINED"

class SupplyRequestStatus(str, Enum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    FULFILLED = "FULFILLED"
    CANCELLED = "CANCELLED"

class eMARAdministrationStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    GIVEN = "GIVEN"
    NOT_GIVEN = "NOT_GIVEN"
    HELD = "HELD"
    REFUSED = "REFUSED"
    PARTIAL = "PARTIAL"
    MISSED = "MISSED"
    LATE = "LATE"

class InsuranceClaimStatus(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PAID = "PAID"

class DICOMStudyStatus(str, Enum):
    RECEIVED = "RECEIVED"
    PENDING_REVIEW = "PENDING_REVIEW"
    REVIEWED = "REVIEWED"
    REPORTED = "REPORTED"
    ARCHIVED = "ARCHIVED"

class VaccineRoute(str, Enum):
    IM = "IM"
    SC = "SC"
    PO = "PO"
    ID = "ID"
    INTRANASAL = "INTRANASAL"

class VaccineStatus(str, Enum):
    COMPLETED = "COMPLETED"
    REFUSED = "REFUSED"
    DEFERRED = "DEFERRED"
    PARTIAL = "PARTIAL"

class WorkflowStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    TRANSFERRED = "transferred"

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
