"""
تجميع نماذج المركز الصحي للإنتاج
"""
# استيراد النماذج الأساسية لضمان تسجيل الجداول لدى SQLAlchemy
from .department import Department
from .user import User, StaffWorkSchedule, StaffAbsence
from .patient import Patient, PatientAllergy
from .visit import Visit
from .appointment import Appointment
from .invoice import Invoice, InvoiceService
from .lab_request import LabRequest, LabResult
from .radiology_request import RadiologyRequest
from .radiology_result import RadiologyResult
from .insurance import InsuranceCompany, InsuranceClaim
from .service import ServiceMaster
from .pricing import ServicePrice, DoctorPricing, InsuranceProvider, PricingCatalog, TemporaryService
from .payment import Payment, PaymentMethod, PaymentStatus
from .medical_record import MedicalRecord
from .medical_report import MedicalReport
from .queue_management import QueueManagement, QueueSettings
from .patient_visit_counter import PatientVisitCounter
from .audit_trail import AuditTrail, SystemLog, SecurityEvent, SlowQueryReport, LoginAttempt
from .system_config import SystemConfig
from .permissions import (Permission, Role, RolePermission, UserPermission, AuditLog,
                           PermissionCategory, PermissionLevel,
                           create_default_permissions, create_default_roles, assign_super_admin_permissions)
from .notification import Notification, NotificationTemplate, NotificationQueue
from .branding import BrandingSettings, SystemTheme
from .patient_satisfaction import PatientSatisfactionSurvey
from .emergency import EmergencyCase
from .emergency_status_history import EmergencyStatusHistory
from .drug_interaction import DrugInteraction
from .follow_up import FollowUpRequest
from .lab_reagent import LabReagent
from .lab_quality import LabQualityControlEntry
from .lab_test_catalog import LabTestCatalog, LabTestPanel, LabTestPanelItem
from .medication import Medication, Prescription, PrescriptionItem, PrescriptionDispenseLog, PharmacySale, PharmacySaleItem, PharmacyReturn, Supplier, MedicationPurchase
from .nurse import Nurse, VitalSigns, MedicationAdministrationLog
from .online_booking import OnlineBooking, PaymentTransaction
from .patient_account import PatientAccount
from .receipt import Receipt
from .refund_request import RefundRequest, RefundStatus
from .reporting import Report
from .request_workflow import RequestWorkflow
from .supply_request import MedicationSupplyRequest, MedicationSupplyRequestItem
from .task_management import Task
from .treatment import Treatment
from .user_department_access import UserDepartmentAccess
from .visit_transfer import VisitTransferLog
from .whatsapp_integration import WhatsAppMessage
from .workflow import WorkflowStep, PatientWorkflow, WorkflowTransfer
from .backup import Backup, BackupLog
from .budget import Budget
from .cash_register import CashRegister
from .file_management import FileUpload
from .advanced_permissions import ModulePermission, DepartmentPermission
from .ai_analytics import AIRecommendation, DiseasePattern, PerformanceAnalytics, PatientInsight, ModelPrediction
from .pricing_management import PricingManagement, PricingRule
from .icd_coding import ICD10Code, CPTCode, DRGCode, CodedDiagnosis, CodedProcedure
from .emar import eMARAdministration, MedicationSchedule
from .bed_management import Ward, Room, Bed, Admission, BedTransfer
from .fhir_mapping import FHIRPatient, FHIRObservation, FHIREncounter, FHIRDocumentReference, FHIRAuditLog
from .dental import DentalChart, DentalTooth
from .dicom_pacs import DICOMStudy, DICOMSeries, DICOMInstance, PACSConfiguration
from .vaccination import Vaccine, Immunization, VaccinationSchedule
from .problem_list import PatientProblem, AllergyIntolerance
from .referral import Referral
from .clinical_pathway import ClinicalPathway, ClinicalPathwayStep, PatientCarePlan, CarePlanTask
from .or_management import SurgerySchedule, SurgeryChecklist
from .medication_reconciliation import MedicationReconciliation
from .cds_alert import CDSAlertRule, CDSFiredAlert
from .barcode_tracking import BarcodeRegistry, BarcodeScanLog
from .digital_signature import DigitalSignature, PasswordPolicy, SessionLog, EncryptedField
from .population_health import DiseaseRegistry, PopulationHealthIndicator, QualityMeasure
from .user_mfa import UserMFASettings, MFALoginAttempt
from .nursing_assessment import NursingAssessment
from .patient_education import PatientEducationMaterial, PatientEducationAssignment
from .backup_restore import BackupRestoreLog
from .telemedicine import TelemedicineAppointment
from .sso_config import SSOConfiguration, SSOUserMapping
from .ai_imaging import AIImagingAnalysis
from .expense import Expense
from .biometric_auth import BiometricCredential, BiometricAuthChallenge
from .data_warehouse import DataWarehouseSync, DailyVisitSummary, MonthlyFinanceSummary
from .what_if_scenario import WhatIfScenario
from .exchange_rate import ExchangeRate, CurrencySettings
from .specialty_form import SpecialtyForm, SpecialtyFormVersion, SpecialtyFormField, SpecialtyFormSubmission

__all__ = [
    "Department", "User", "StaffWorkSchedule", "StaffAbsence",
    "Patient", "PatientAllergy", "Visit", "Appointment",
    "Invoice", "InvoiceService",
    "LabRequest", "LabResult",
    "RadiologyRequest", "RadiologyResult",
    "InsuranceCompany", "InsuranceClaim",
    "ServiceMaster", "ServicePrice", "DoctorPricing", "InsuranceProvider", "PricingCatalog", "TemporaryService",
    "Payment", "PaymentMethod", "PaymentStatus",
    "MedicalRecord", "MedicalReport",
    "QueueManagement", "QueueSettings", "PatientVisitCounter",
    "AuditTrail", "SystemLog", "SecurityEvent", "SlowQueryReport", "LoginAttempt",
    "SystemConfig",
    "Permission", "Role", "RolePermission", "UserPermission", "AuditLog",
    "PermissionCategory", "PermissionLevel",
    "create_default_permissions", "create_default_roles", "assign_super_admin_permissions",
    "Notification", "NotificationTemplate", "NotificationQueue",
    "BrandingSettings", "SystemTheme",
    "PatientSatisfactionSurvey",
    "EmergencyCase", "EmergencyStatusHistory",
    "DrugInteraction", "FollowUpRequest",
    "LabReagent", "LabQualityControlEntry", "LabTestCatalog", "LabTestPanel", "LabTestPanelItem",
    "Medication", "Prescription", "PrescriptionItem", "PrescriptionDispenseLog",
    "PharmacySale", "PharmacySaleItem", "PharmacyReturn", "Supplier", "MedicationPurchase",
    "Nurse", "VitalSigns", "MedicationAdministrationLog",
    "OnlineBooking", "PaymentTransaction", "PatientAccount",
    "Receipt",
    "RefundRequest", "RefundStatus",
    "Report",
    "RequestWorkflow", "MedicationSupplyRequest", "MedicationSupplyRequestItem",
    "Task",
    "Treatment",
    "UserDepartmentAccess", "VisitTransferLog",
    "WhatsAppMessage",
    "WorkflowStep", "PatientWorkflow", "WorkflowTransfer",
    "Backup", "BackupLog", "FileUpload",
    "ModulePermission", "DepartmentPermission",
    "AIRecommendation", "DiseasePattern", "PerformanceAnalytics", "PatientInsight", "ModelPrediction",
    "PricingManagement", "PricingRule",
    "ICD10Code", "CPTCode", "DRGCode", "CodedDiagnosis", "CodedProcedure",
    "eMARAdministration", "MedicationSchedule",
    "Ward", "Room", "Bed", "Admission", "BedTransfer",
    "FHIRPatient", "FHIRObservation", "FHIREncounter", "FHIRDocumentReference", "FHIRAuditLog",
    "DICOMStudy", "DICOMSeries", "DICOMInstance", "PACSConfiguration",
    "Vaccine", "Immunization", "VaccinationSchedule",
    "PatientProblem", "AllergyIntolerance",
    "Referral",
    "ClinicalPathway", "ClinicalPathwayStep", "PatientCarePlan", "CarePlanTask",
    "SurgerySchedule", "SurgeryChecklist",
    "MedicationReconciliation",
    "CDSAlertRule", "CDSFiredAlert",
    "BarcodeRegistry", "BarcodeScanLog",
    "Expense",
    "DigitalSignature", "PasswordPolicy", "SessionLog", "EncryptedField",
    "DiseaseRegistry", "PopulationHealthIndicator", "QualityMeasure",
    "UserMFASettings", "MFALoginAttempt",
    "NursingAssessment",
    "PatientEducationMaterial", "PatientEducationAssignment",
    "BackupRestoreLog",
    "TelemedicineAppointment",
    "SSOConfiguration", "SSOUserMapping",
    "AIImagingAnalysis",
    "BiometricCredential", "BiometricAuthChallenge",
    "DataWarehouseSync", "DailyVisitSummary", "MonthlyFinanceSummary",
    "WhatIfScenario",
    "ExchangeRate", "CurrencySettings",
    "SpecialtyForm", "SpecialtyFormVersion", "SpecialtyFormField", "SpecialtyFormSubmission",
]