"""
تجميع نماذج المركز الصحي للإنتاج
"""
# استيراد النماذج الأساسية لضمان تسجيل الجداول لدى SQLAlchemy
from .department import Department
from .user import User
from .patient import Patient
from .visit import Visit
from .appointment import Appointment
from .invoice import Invoice, InvoiceService
from .lab_request import LabRequest, LabResult
from .radiology_request import RadiologyRequest
from .radiology_test import RadiologyResult
from .insurance import InsuranceCompany, InsuranceClaim
from .service import ServiceMaster
from .pricing import ServicePrice, DoctorPricing, InsuranceProvider, PricingCatalog, TemporaryService
from .payment import Payment, PaymentMethod
from .medical_record import MedicalRecord
from .medical_report import MedicalReport
from .queue_management import QueueManagement
from .patient_visit_counter import PatientVisitCounter
from .audit_trail import AuditTrail, SystemLog, SecurityEvent
from .system_config import SystemConfig
from .permissions import Permission, Role, RolePermission, UserPermission, AuditLog
from .notification import Notification
from .branding import BrandingSettings, SystemTheme

__all__ = [
    "Department", "User", "Patient", "Visit", "Appointment",
    "Invoice", "InvoiceService",
    "LabRequest", "LabResult",
    "RadiologyRequest", "RadiologyResult",
    "InsuranceCompany", "InsuranceClaim",
    "ServiceMaster", "ServicePrice", "DoctorPricing", "InsuranceProvider", "PricingCatalog", "TemporaryService",
    "Payment", "PaymentMethod",
    "MedicalRecord", "MedicalReport",
    "QueueManagement", "PatientVisitCounter",
    "AuditTrail", "SystemLog", "SecurityEvent",
    "SystemConfig",
    "Permission", "Role", "RolePermission", "UserPermission", "AuditLog",
    "Notification",
    "BrandingSettings", "SystemTheme",
]