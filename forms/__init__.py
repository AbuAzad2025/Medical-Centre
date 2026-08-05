# Medical System Forms

# Import base forms
# Import existing forms
from .admin_forms import *
from .appointment_forms import *
from .base_forms import (
    AuditMixin,
    DateRangeMixin,
    FileUploadMixin,
    FormBase,
    MedicalEntityMixin,
    NotificationMixin,
    PaymentMixin,
    PricingBaseForm,
    PriorityMixin,
    SearchFormBase,
    StatusMixin,
)
from .emergency_forms import *

# Import specific form modules
from .invoice_forms import (
    InsuranceClaimForm,
    InsuranceClaimSearchForm,
    InsurancePolicyForm,
    InsuranceProviderForm,
    InvoiceForm,
    InvoiceSearchForm,
    ReceiptForm,
    RefundForm,
)
from .management_forms import (
    AvailabilityExceptionForm,
    DoctorScheduleForm,
    FollowUpPlanForm,
    FollowUpPlanSearchForm,
    MedicalRecordForm,
    MedicalRecordSearchForm,
    OnlineBookingForm,
    PrescriptionForm,
    PrescriptionItemForm,
    PrescriptionSearchForm,
)
from .medication_forms import *
from .notification_forms import *
from .patient_forms import *
from .payment_forms import *
from .pricing_forms import *
from .report_forms import *
from .request_forms import (
    LabRequestForm,
    LabRequestSearchForm,
    QueueItemForm,
    RadiologyRequestForm,
    RadiologyRequestSearchForm,
    TriageForm,
    WorkflowStepForm,
    WorkflowTransferForm,
)
from .system_forms import (
    AIAnalyticsConfigForm,
    AuditSearchForm,
    BackupSettingsForm,
    DepartmentWorkflowConfigForm,
    FileUploadForm,
    FinancialAuditSearchForm,
    NotificationForm,
    PermissionAssignmentForm,
    RoleForm,
    RunBackupForm,
    SecurityEventSearchForm,
    SystemConfigForm,
    SystemLogSearchForm,
    UserRoleAssignmentForm,
)
from .user_forms import *
from .visit_forms import *

__all__ = [
    'AIAnalyticsConfigForm',
    'AuditMixin',
    'AuditSearchForm',
    'AvailabilityExceptionForm',
    'BackupSettingsForm',
    'DateRangeMixin',
    'DepartmentWorkflowConfigForm',
    # Management forms
    'DoctorScheduleForm',
    'FileUploadForm',
    'FileUploadMixin',
    'FinancialAuditSearchForm',
    'FollowUpPlanForm',
    'FollowUpPlanSearchForm',
    # Base forms
    'FormBase',
    'InsuranceClaimForm',
    'InsuranceClaimSearchForm',
    'InsurancePolicyForm',
    'InsuranceProviderForm',
    # Invoice forms
    'InvoiceForm',
    'InvoiceSearchForm',
    # Request forms
    'LabRequestForm',
    'LabRequestSearchForm',
    'MedicalEntityMixin',
    'MedicalRecordForm',
    'MedicalRecordSearchForm',
    'NotificationForm',
    'NotificationMixin',
    'OnlineBookingForm',
    'PaymentMixin',
    'PermissionAssignmentForm',
    'PrescriptionForm',
    'PrescriptionItemForm',
    'PrescriptionSearchForm',
    'PricingBaseForm',
    'PriorityMixin',
    'QueueItemForm',
    'RadiologyRequestForm',
    'RadiologyRequestSearchForm',
    'ReceiptForm',
    'RefundForm',
    # System forms
    'RoleForm',
    'RunBackupForm',
    'SearchFormBase',
    'SecurityEventSearchForm',
    'StatusMixin',
    'SystemConfigForm',
    'SystemLogSearchForm',
    'TriageForm',
    'UserRoleAssignmentForm',
    'WorkflowStepForm',
    'WorkflowTransferForm',
]
