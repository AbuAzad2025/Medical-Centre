# Medical System Forms

# Import base forms
from .base_forms import (
    FormBase, SearchFormBase, PaymentMixin, PricingBaseForm, 
    MedicalEntityMixin, StatusMixin, PriorityMixin, DateRangeMixin,
    FileUploadMixin, NotificationMixin, AuditMixin
)

# Import specific form modules
from .invoice_forms import (
    InvoiceForm, InvoiceSearchForm, ReceiptForm, RefundForm,
    InsuranceClaimForm, InsuranceClaimSearchForm, InsurancePolicyForm, InsuranceProviderForm
)

from .request_forms import (
    LabRequestForm, LabRequestSearchForm, RadiologyRequestForm, RadiologyRequestSearchForm,
    TriageForm, QueueItemForm, WorkflowStepForm, WorkflowTransferForm
)

from .management_forms import (
    DoctorScheduleForm, AvailabilityExceptionForm, OnlineBookingForm,
    MedicalRecordForm, PrescriptionForm, PrescriptionItemForm, FollowUpPlanForm,
    MedicalRecordSearchForm, PrescriptionSearchForm, FollowUpPlanSearchForm
)

from .system_forms import (
    RoleForm, PermissionAssignmentForm, DepartmentWorkflowConfigForm,
    FileUploadForm, BackupSettingsForm, RunBackupForm, AuditSearchForm,
    FinancialAuditSearchForm, AIAnalyticsConfigForm, SystemConfigForm,
    UserRoleAssignmentForm, NotificationForm, SystemLogSearchForm, SecurityEventSearchForm
)

# Import existing forms
from .admin_forms import *
from .appointment_forms import *
from .emergency_forms import *
from .medication_forms import *
from .notification_forms import *
from .patient_forms import *
from .payment_forms import *
from .pricing_forms import *
from .report_forms import *
from .user_forms import *
from .visit_forms import *

__all__ = [
    # Base forms
    'FormBase', 'SearchFormBase', 'PaymentMixin', 'PricingBaseForm',
    'MedicalEntityMixin', 'StatusMixin', 'PriorityMixin', 'DateRangeMixin',
    'FileUploadMixin', 'NotificationMixin', 'AuditMixin',
    
    # Invoice forms
    'InvoiceForm', 'InvoiceSearchForm', 'ReceiptForm', 'RefundForm',
    'InsuranceClaimForm', 'InsuranceClaimSearchForm', 'InsurancePolicyForm', 'InsuranceProviderForm',
    
    # Request forms
    'LabRequestForm', 'LabRequestSearchForm', 'RadiologyRequestForm', 'RadiologyRequestSearchForm',
    'TriageForm', 'QueueItemForm', 'WorkflowStepForm', 'WorkflowTransferForm',
    
    # Management forms
    'DoctorScheduleForm', 'AvailabilityExceptionForm', 'OnlineBookingForm',
    'MedicalRecordForm', 'PrescriptionForm', 'PrescriptionItemForm', 'FollowUpPlanForm',
    'MedicalRecordSearchForm', 'PrescriptionSearchForm', 'FollowUpPlanSearchForm',
    
    # System forms
    'RoleForm', 'PermissionAssignmentForm', 'DepartmentWorkflowConfigForm',
    'FileUploadForm', 'BackupSettingsForm', 'RunBackupForm', 'AuditSearchForm',
    'FinancialAuditSearchForm', 'AIAnalyticsConfigForm', 'SystemConfigForm',
    'UserRoleAssignmentForm', 'NotificationForm', 'SystemLogSearchForm', 'SecurityEventSearchForm'
]