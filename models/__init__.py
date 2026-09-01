"""
تجميع نماذج المركز الصحي للإنتاج
"""

# استيراد النماذج الأساسية لضمان تسجيل الجداول لدى SQLAlchemy
from .advanced_permissions import DepartmentPermission, ModulePermission
from .ai_analytics import (
    AIRecommendation,
    DiseasePattern,
    ModelPrediction,
    PatientInsight,
    PerformanceAnalytics,
)
from .ai_imaging import AIImagingAnalysis
from .appointment import Appointment
from .audit_trail import AuditTrail, LoginAttempt, SecurityEvent, SlowQueryReport, SystemLog
from .backup import Backup, BackupLog
from .backup_restore import BackupRestoreLog
from .barcode_tracking import BarcodeRegistry, BarcodeScanLog
from .bed_management import Admission, Bed, BedTransfer, Room, Ward
from .biometric_auth import BiometricAuthChallenge, BiometricCredential
from .branding import BrandingSettings, SystemTheme
from .budget import Budget as Budget
from .cash_register import CashRegister as CashRegister
from .cds_alert import CDSAlertRule, CDSFiredAlert
from .clinical_pathway import CarePlanTask, ClinicalPathway, ClinicalPathwayStep, PatientCarePlan
from .data_warehouse import DailyVisitSummary, DataWarehouseSync, MonthlyFinanceSummary
from .dental import DentalChart as DentalChart
from .dental import DentalTooth as DentalTooth
from .department import Department
from .dicom_pacs import DICOMInstance, DICOMSeries, DICOMStudy, PACSConfiguration
from .digital_signature import DigitalSignature, EncryptedField, PasswordPolicy, SessionLog
from .drug_interaction import DrugInteraction
from .emar import MedicationSchedule, eMARAdministration
from .emergency import EmergencyCase
from .emergency_status_history import EmergencyStatusHistory
from .exchange_rate import CurrencySettings, ExchangeRate
from .expense import Expense
from .fhir_mapping import (
    FHIRAuditLog,
    FHIRDocumentReference,
    FHIREncounter,
    FHIRObservation,
    FHIRPatient,
)
from .file_management import FileUpload
from .follow_up import FollowUpRequest
from .gl import Account, FinancialPeriod, GLJournal, GLJournalLine
from .icd_coding import CodedDiagnosis, CodedProcedure, CPTCode, DRGCode, ICD10Code
from .insurance import InsuranceClaim, InsuranceCompany
from .invoice import Invoice, InvoiceService
from .lab_quality import LabQualityControlEntry
from .lab_reagent import LabReagent
from .lab_request import LabRequest, LabResult
from .lab_test_catalog import LabTestCatalog, LabTestPanel, LabTestPanelItem
from .medical_record import MedicalRecord
from .medical_report import MedicalReport
from .medication import (
    Medication,
    MedicationPurchase,
    PharmacyReturn,
    PharmacySale,
    PharmacySaleItem,
    Prescription,
    PrescriptionDispenseLog,
    PrescriptionItem,
    Supplier,
)
from .medication_reconciliation import MedicationReconciliation
from .notification import Notification, NotificationQueue, NotificationTemplate
from .nurse import MedicationAdministrationLog, Nurse, VitalSigns
from .nursing_assessment import NursingAssessment
from .online_booking import OnlineBooking, PaymentTransaction
from .or_management import SurgeryChecklist, SurgerySchedule
from .patient import Patient, PatientAllergy
from .patient_account import PatientAccount
from .patient_education import PatientEducationAssignment, PatientEducationMaterial
from .patient_satisfaction import PatientSatisfactionSurvey
from .patient_visit_counter import PatientVisitCounter
from .payment import Payment, PaymentMethod, PaymentStatus
from .permissions import (
    AuditLog,
    Permission,
    PermissionCategory,
    PermissionLevel,
    Role,
    RolePermission,
    UserPermission,
    assign_super_admin_permissions,
    create_default_permissions,
    create_default_roles,
)
from .population_health import DiseaseRegistry, PopulationHealthIndicator, QualityMeasure
from .pricing import (
    DoctorPricing,
    InsuranceProvider,
    PricingCatalog,
    ServicePrice,
    TemporaryService,
)
from .pricing_management import PricingManagement, PricingRule
from .problem_list import AllergyIntolerance, PatientProblem
from .queue_management import QueueManagement, QueueSettings
from .radiology_request import RadiologyRequest
from .radiology_result import RadiologyResult
from .receipt import Receipt
from .referral import Referral
from .refund_request import RefundRequest, RefundStatus
from .reporting import Report
from .request_workflow import RequestWorkflow
from .service import ServiceMaster
from .specialty_form import (
    SpecialtyForm,
    SpecialtyFormField,
    SpecialtyFormSubmission,
    SpecialtyFormVersion,
)
from .sso_config import SSOConfiguration, SSOUserMapping
from .supply_request import MedicationSupplyRequest, MedicationSupplyRequestItem
from .system_config import SystemConfig
from .task_management import Task
from .telemedicine import TelemedicineAppointment
from .treatment import Treatment
from .user import StaffAbsence, StaffWorkSchedule, User
from .user_department_access import UserDepartmentAccess
from .user_mfa import MFALoginAttempt, UserMFASettings
from .vaccination import Immunization, VaccinationSchedule, Vaccine
from .visit import Visit
from .visit_transfer import VisitTransferLog
from .what_if_scenario import WhatIfScenario
from .whatsapp_integration import WhatsAppMessage
from .workflow import PatientWorkflow, WorkflowStep, WorkflowTransfer

__all__ = [
    'AIImagingAnalysis',
    'AIRecommendation',
    'Account',
    'Admission',
    'AllergyIntolerance',
    'Appointment',
    'AuditLog',
    'AuditTrail',
    'Backup',
    'BackupLog',
    'BackupRestoreLog',
    'BarcodeRegistry',
    'BarcodeScanLog',
    'Bed',
    'BedTransfer',
    'BiometricAuthChallenge',
    'BiometricCredential',
    'BrandingSettings',
    'CDSAlertRule',
    'CDSFiredAlert',
    'CPTCode',
    'CarePlanTask',
    'ClinicalPathway',
    'ClinicalPathwayStep',
    'CodedDiagnosis',
    'CodedProcedure',
    'CurrencySettings',
    'DICOMInstance',
    'DICOMSeries',
    'DICOMStudy',
    'DRGCode',
    'DailyVisitSummary',
    'DataWarehouseSync',
    'Department',
    'DepartmentPermission',
    'DigitalSignature',
    'DiseasePattern',
    'DiseaseRegistry',
    'DoctorPricing',
    'DrugInteraction',
    'EmergencyCase',
    'EmergencyStatusHistory',
    'EncryptedField',
    'ExchangeRate',
    'Expense',
    'FHIRAuditLog',
    'FHIRDocumentReference',
    'FHIREncounter',
    'FHIRObservation',
    'FHIRPatient',
    'FileUpload',
    'FinancialPeriod',
    'FollowUpRequest',
    'GLJournal',
    'GLJournalLine',
    'ICD10Code',
    'Immunization',
    'InsuranceClaim',
    'InsuranceCompany',
    'InsuranceProvider',
    'Invoice',
    'InvoiceService',
    'LabQualityControlEntry',
    'LabReagent',
    'LabRequest',
    'LabResult',
    'LabTestCatalog',
    'LabTestPanel',
    'LabTestPanelItem',
    'LoginAttempt',
    'MFALoginAttempt',
    'MedicalRecord',
    'MedicalReport',
    'Medication',
    'MedicationAdministrationLog',
    'MedicationPurchase',
    'MedicationReconciliation',
    'MedicationSchedule',
    'MedicationSupplyRequest',
    'MedicationSupplyRequestItem',
    'ModelPrediction',
    'ModulePermission',
    'MonthlyFinanceSummary',
    'Notification',
    'NotificationQueue',
    'NotificationTemplate',
    'Nurse',
    'NursingAssessment',
    'OnlineBooking',
    'PACSConfiguration',
    'PasswordPolicy',
    'Patient',
    'PatientAccount',
    'PatientAllergy',
    'PatientCarePlan',
    'PatientEducationAssignment',
    'PatientEducationMaterial',
    'PatientInsight',
    'PatientProblem',
    'PatientSatisfactionSurvey',
    'PatientVisitCounter',
    'PatientWorkflow',
    'Payment',
    'PaymentMethod',
    'PaymentStatus',
    'PaymentTransaction',
    'PerformanceAnalytics',
    'Permission',
    'PermissionCategory',
    'PermissionLevel',
    'PharmacyReturn',
    'PharmacySale',
    'PharmacySaleItem',
    'PopulationHealthIndicator',
    'Prescription',
    'PrescriptionDispenseLog',
    'PrescriptionItem',
    'PricingCatalog',
    'PricingManagement',
    'PricingRule',
    'QualityMeasure',
    'QueueManagement',
    'QueueSettings',
    'RadiologyRequest',
    'RadiologyResult',
    'Receipt',
    'Referral',
    'RefundRequest',
    'RefundStatus',
    'Report',
    'RequestWorkflow',
    'Role',
    'RolePermission',
    'Room',
    'SSOConfiguration',
    'SSOUserMapping',
    'SecurityEvent',
    'ServiceMaster',
    'ServicePrice',
    'SessionLog',
    'SlowQueryReport',
    'SpecialtyForm',
    'SpecialtyFormField',
    'SpecialtyFormSubmission',
    'SpecialtyFormVersion',
    'StaffAbsence',
    'StaffWorkSchedule',
    'Supplier',
    'SurgeryChecklist',
    'SurgerySchedule',
    'SystemConfig',
    'SystemLog',
    'SystemTheme',
    'Task',
    'TelemedicineAppointment',
    'TemporaryService',
    'Treatment',
    'User',
    'UserDepartmentAccess',
    'UserMFASettings',
    'UserPermission',
    'VaccinationSchedule',
    'Vaccine',
    'Visit',
    'VisitTransferLog',
    'VitalSigns',
    'Ward',
    'WhatIfScenario',
    'WhatsAppMessage',
    'WorkflowStep',
    'WorkflowTransfer',
    'assign_super_admin_permissions',
    'create_default_permissions',
    'create_default_roles',
    'eMARAdministration',
]
