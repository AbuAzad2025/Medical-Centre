"""
Shared Enums and Constants
"""
from enum import Enum

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

class VisitState(str, Enum):
    OPEN = "OPEN"
    CHECKED_IN = "CHECKED_IN"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"

class QueueState(str, Enum):
    WAITING = "waiting"
    CALLED = "called"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"

class OrderState(str, Enum):
    REQUESTED = "REQUESTED"
    RECEIVED = "RECEIVED"
    ANALYZING = "ANALYZING"
    REVIEWED = "REVIEWED"
    APPROVED = "APPROVED"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    CANCELLED = "CANCELLED"

class BillingState(str, Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    PARTIAL = "PARTIAL"
    DEBT = "DEBT"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"

class AppointmentState(str, Enum):
    SCHEDULED = "SCHEDULED"
    CONFIRMED = "CONFIRMED"
    CHECKED_IN = "CHECKED_IN"
    DONE = "DONE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"

class BookingState(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    CONVERTED = "converted"
    EXPIRED = "expired"

class PrescriptionState(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    DISPENSED = "dispensed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    EXPIRED = "expired"

class NotificationState(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    READ = "read"

class TaskState(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class ReportExecutionState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
