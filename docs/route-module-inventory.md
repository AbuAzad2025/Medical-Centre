# Route / Module Inventory

**Generated:** 2026-06-16  
**Purpose:** Complete mapping of all routes to modules for SaaS module gating

---

## Blueprint → Module Mapping

| Blueprint | URL Prefix | Module | Category | Guard Applied |
|-----------|------------|--------|----------|---------------|
| main_bp | / | core | core | No |
| auth_bp | /auth | core | core | No |
| owner_bp | /owner | owner | integration | Owner only |
| super_admin_bp | /super-admin | owner | integration | Super admin only |
| reception_bp | /reception | reception | administrative | Yes |
| doctor_bp | /doctor | doctor | clinical | Yes |
| emergency_bp | /emergency | emergency | clinical | Yes |
| lab_bp | /lab | lab | clinical | Yes |
| radiology_bp | /radiology | radiology | clinical | Yes |
| finance_bp | /finance | billing | financial | Yes |
| accountant_bp | /accountant | billing | financial | Yes |
| booking_bp | /booking | appointments | administrative | Yes |
| medication_bp | /medication | pharmacy | clinical | Yes |
| payment_bp | /payment | billing | financial | No* |
| nurse_bp | /nurse | nursing | clinical | Yes |
| clinical_coding_bp | /clinical-coding | reporting | administrative | No* |
| bed_bp | /bed | nursing | clinical | No* |
| or_bp | /or | nursing | clinical | No* |
| emar_bp | /emar | nursing | clinical | Yes (nursing) |
| vaccination_bp | /vaccination | doctor | clinical | No* |
| referral_bp | /referral | doctor | clinical | No* |
| pathway_bp | /pathway | doctor | clinical | Yes (doctor) |
| cds_bp | /cds | doctor | clinical | No* |
| barcode_bp | /barcode | inventory | administrative | No* |
| fhir_bp | /api/fhir | integration | integration | No* |
| dicom_bp | /dicom | radiology | clinical | No* |
| portal_bp | /portal | portal | clinical | No* |
| pop_health_bp | /population-health | reporting | administrative | No* |
| report_builder_bp | /report-builder | reporting | administrative | Yes (reporting) |
| security_bp | /security | core | core | No* |
| mfa_bp | /mfa | core | core | No* |
| nursing_assessment_bp | /nursing-assessment | nursing | clinical | No* |
| patient_education_bp | /patient-education | doctor | clinical | No* |
| backup_restore_bp | /backup-restore | core | core | No* |
| telemedicine_bp | /telemedicine | doctor | clinical | No* |
| sso_bp | /sso | integration | integration | No* |
| ai_imaging_bp | /ai-imaging | ai_imaging | clinical | No* |
| biometric_bp | /biometric | core | core | No* |
| data_warehouse_bp | /data-warehouse | reporting | administrative | Yes (reporting) |
| what_if_bp | /what-if | reporting | administrative | No* |
| quality_bp | /quality | reporting | administrative | No* |
| reception_currency_bp | /reception | reception | administrative | Yes (reception) |
| backup_bp | /backup | core | core | No* |
| ai_imaging_routes.py | /ai-imaging | ai_imaging | clinical | No* |
| barcode_routes.py | /barcode | inventory | administrative | No* |
| bed_management_routes.py | /bed | nursing | clinical | No* |
| biometric_routes.py | /biometric | core | core | No* |
| booking_routes.py | /booking | appointments | administrative | Yes |
| cds_alert_routes.py | /cds | doctor | clinical | No* |
| clinical_coding.py | /clinical-coding | reporting | administrative | No* |
| clinical_pathway_routes.py | /pathway | doctor | clinical | Yes (doctor) |
| custom_report_builder_routes.py | /report-builder | reporting | administrative | Yes (reporting) |
| data_warehouse_routes.py | /data-warehouse | reporting | administrative | Yes (reporting) |
| dicom_routes.py | /dicom | radiology | clinical | No* |
| doctor.py | /doctor | doctor | clinical | Yes |
| emergency.py | /emergency | emergency | clinical | Yes |
| emar_routes.py | /emar | nursing | clinical | Yes (nursing) |
| finance.py | /finance | billing | financial | Yes |
| fhir_api_routes.py | /api/fhir | integration | integration | No* |
| lab.py | /lab | lab | clinical | Yes |
| main.py | / | core | core | No |
| manager.py | /manager | reporting | administrative | Yes (reporting) |
| medication_routes.py | /medication | pharmacy | clinical | Yes |
| mfa_routes.py | /mfa | core | core | No* |
| nurse_routes.py | /nurse | nursing | clinical | Yes |
| nursing_assessment_routes.py | /nursing-assessment | nursing | clinical | No* |
| or_management_routes.py | /or | nursing | clinical | No* |
| patient_education_routes.py | /patient-education | doctor | clinical | No* |
| patient_portal.py | /portal | portal | clinical | No* |
| payment_routes.py | /payment | billing | financial | No* |
| population_health_routes.py | /population-health | reporting | administrative | No* |
| quality_compliance.py | /quality | reporting | administrative | No* |
| radiology.py | /radiology | radiology | clinical | Yes |
| reception.py | /reception | reception | administrative | Yes |
| reception_currency.py | /reception | reception | administrative | Yes (reception) |
| referral_routes.py | /referral | doctor | clinical | No* |
| security_advanced_routes.py | /security | core | core | No* |
| sso_routes.py | /sso | integration | integration | No* |
| super_admin.py | /super-admin | owner | integration | Super admin only |
| telemedicine_routes.py | /telemedicine | doctor | clinical | No* |
| vaccination_routes.py | /vaccination | doctor | clinical | No* |
| what_if_routes.py | /what-if | reporting | administrative | No* |

---

## Notes

* **Guard Applied = No* means the blueprint is registered but no module guard is added in `app_factory.py`. These need module assignment.
* **Core modules** (main, auth, owner, super_admin, security, mfa, backup, backup_restore) don't need module guards.
* **Integration modules** (fhir, dicom, sso, ai_imaging) may need separate feature flags.

---

## Module Registry vs Routes Gap Analysis

### Modules in Registry but Missing Guards:
- inventory → barcode_bp (needs guard)
- appointments → booking_bp (has guard)
- reporting → report_builder_bp, data_warehouse_bp, manager_bp (have guards), pop_health_bp, quality_bp, what_if_bp (missing)
- nursing → emar_bp, nurse_bp (have guards), bed_bp, or_bp, nursing_assessment_bp (missing)
- pharmacy → medication_bp (has guard)

### Routes without Module Assignment:
- clinical_coding, vaccination, referral, pathway (doctor - has guard), cds, barcode, fhir, dicom, portal, pop_health, security, mfa, patient_education, backup_restore, telemedicine, ai_imaging, biometric, quality, sso

---

## Required Actions

1. Add missing module guards in `app_factory.py`
2. Assign modules to orphan blueprints
3. Create `core/module_route_map.py` for programmatic lookup
4. Update `MODULE_REGISTRY` with missing modules: `ai_imaging`, `dicom`, `portal`, `inventory`, `nursing_assessment`, `bed`, `or_management`, `clinical_coding`, `vaccination`, `referral`, `pathway`, `cds`, `barcode`, `fhir`, `telemedicine`, `patient_education`, `quality`, `what_if`, `population_health`, `sso`, `biometric`