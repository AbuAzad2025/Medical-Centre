# Frontend-Backend Template Matching Report

Generated: 2026-10-15 05:52:34Z
Frontend pages analyzed: 81
Backend templates analyzed: 87

## Summary

- Frontend pages with backend match: 6/81 (7.4%)
- Orphaned backend templates: 65

## Page-by-Page Matching

### ✅ manager/unit_control
- File: `D:\recovers\data\medical\static\js\pages\manager\unit_control.js`
- API calls found: 1
- Matched backend templates: READ_MANAGER_PRICING_AND_SATISFACTION

### ✅ reception/appointments
- File: `D:\recovers\data\medical\static\js\pages\reception\appointments.js`
- API calls found: 10
- Matched backend templates: READ_DASHBOARD_SNAPSHOT_AND_PATIENT_SEARCH_API, READ_LANDING_AND_ACCOUNT_PAGES, READ_GLOBAL_SEARCH, READ_BOOKING_SLOT_AVAILABILITY, READ_DEPARTMENT_DASHBOARDS, READ_RECEPTION_PRINTABLES, READ_RECEPTION_FOLLOW_UP_AND_PAYMENT_LISTS, READ_CONSOLE_LANDING_PAGES, READ_RECEPTION_LOOKUP_AND_DETAIL, READ_FHIR_AND_INTEROPERABILITY_SURFACES, READ_FHIR_BUNDLE_ENDPOINTS, READ_RECEPTION_FRONT_DESK_DASHBOARDS, READ_ROOT_LEVEL_SHORTCUTS
- **Missing backend coverage for:** reception.appointments, __M0__, reception.no_show_appointment, reception.confirm_appointment, reception.cancel_appointment, reception.edit_appointment, reception.view_appointment, __M1__

### ✅ reception/visits
- File: `D:\recovers\data\medical\static\js\pages\reception\visits.js`
- API calls found: 9
- Matched backend templates: READ_ACCOUNTANT_DASHBOARDS_AND_REPORTS, READ_PAYMENT_CONSOLE, READ_ACCOUNTANT_ACCOUNTS_AND_PATIENT_BALANCES, READ_PATIENT_PORTAL_BILLS_AND_BOOKING, READ_ACCOUNTANT_RECEIPT_AND_EXPORT
- **Missing backend coverage for:** reception.edit_visit, reception.export_visits, reception.print_receipt, reception.transfer_visit, __M0__, reception.view_visit, reception.api_department_staff, __M1__

### ✅ super_admin/departments
- File: `D:\recovers\data\medical\static\js\pages\super_admin\departments.js`
- API calls found: 7
- Matched backend templates: READ_SUPERADMIN_CATALOGUE_AND_PRICING
- **Missing backend coverage for:** super_admin.department_staff, super_admin.export_departments, super_admin.deactivate_department, super_admin.edit_department, super_admin.activate_department, super_admin.view_department

### ✅ super_admin/services
- File: `D:\recovers\data\medical\static\js\pages\super_admin\services.js`
- API calls found: 7
- Matched backend templates: READ_SUPERADMIN_CATALOGUE_AND_PRICING
- **Missing backend coverage for:** super_admin.service_pricing, super_admin.edit_service, super_admin.view_service, super_admin.deactivate_service, super_admin.activate_service, super_admin.export_services

### ✅ super_admin/system_backup
- File: `D:\recovers\data\medical\static\js\pages\super_admin\system_backup.js`
- API calls found: 9
- Matched backend templates: READ_BACKUP_CONSOLE_VIEWS, READ_SUPERADMIN_SYSTEM_AND_BACKUP_VIEWS
- **Missing backend coverage for:** super_admin.cancel_backup, super_admin.delete_backup, super_admin.backup_report, super_admin.export_backup_logs, super_admin.restore_backup, super_admin.backup_history, super_admin.backup_schedule, super_admin.save_backup_settings

### ❌ accountant/dashboard_new
- File: `D:\recovers\data\medical\static\js\pages\accountant\dashboard_new.js`
- API calls found: 1
- **Missing backend coverage for:** __M0__

### ❌ accountant/pending_payments
- File: `D:\recovers\data\medical\static\js\pages\accountant\pending_payments.js`
- API calls found: 0

### ❌ accountant/process_payment
- File: `D:\recovers\data\medical\static\js\pages\accountant\process_payment.js`
- API calls found: 2
- **Missing backend coverage for:** __M0__, reception_currency.check_rate

### ❌ barcode/scan
- File: `D:\recovers\data\medical\static\js\pages\barcode\scan.js`
- API calls found: 2
- **Missing backend coverage for:** __M0__, __M1__

### ❌ biometric/status
- File: `D:\recovers\data\medical\static\js\pages\biometric\status.js`
- API calls found: 1
- **Missing backend coverage for:** __M0__

### ❌ booking/create
- File: `D:\recovers\data\medical\static\js\pages\booking\create.js`
- API calls found: 5
- **Missing backend coverage for:** __M4__, __M0__, __M2__, __M3__, __M1__

### ❌ booking/index
- File: `D:\recovers\data\medical\static\js\pages\booking\index.js`
- API calls found: 2
- **Missing backend coverage for:** __M0__, __M1__

### ❌ doctor/dashboard
- File: `D:\recovers\data\medical\static\js\pages\doctor\dashboard.js`
- API calls found: 7
- **Missing backend coverage for:** __M5__, __M4__, __M0__, __M2__, __M3__, doctor.api_dashboard_stats, __M1__

### ❌ doctor/dental_chart
- File: `D:\recovers\data\medical\static\js\pages\doctor\dental_chart.js`
- API calls found: 6
- **Missing backend coverage for:** __M5__, __M4__, __M0__, __M2__, __M3__, __M1__

### ❌ doctor/diagnosis
- File: `D:\recovers\data\medical\static\js\pages\doctor\diagnosis.js`
- API calls found: 0

### ❌ doctor/notes
- File: `D:\recovers\data\medical\static\js\pages\doctor\notes.js`
- API calls found: 3
- **Missing backend coverage for:** __M0__, __M2__, __M1__

### ❌ doctor/patient_details
- File: `D:\recovers\data\medical\static\js\pages\doctor\patient_details.js`
- API calls found: 2
- **Missing backend coverage for:** __M0__, __M1__

### ❌ doctor/patient_queue
- File: `D:\recovers\data\medical\static\js\pages\doctor\patient_queue.js`
- API calls found: 4
- **Missing backend coverage for:** __M0__, __M2__, reception.get_smart_queue_management, __M1__

### ❌ doctor/prescription
- File: `D:\recovers\data\medical\static\js\pages\doctor\prescription.js`
- API calls found: 1
- **Missing backend coverage for:** __M0__

### ❌ doctor/visit_summary
- File: `D:\recovers\data\medical\static\js\pages\doctor\visit_summary.js`
- API calls found: 2
- **Missing backend coverage for:** __M0__, __M1__

### ❌ emergency/dashboard_new
- File: `D:\recovers\data\medical\static\js\pages\emergency\dashboard_new.js`
- API calls found: 0

### ❌ emergency/edit
- File: `D:\recovers\data\medical\static\js\pages\emergency\edit.js`
- API calls found: 2
- **Missing backend coverage for:** __M0__, __M1__

### ❌ emergency/emergency_treatment
- File: `D:\recovers\data\medical\static\js\pages\emergency\emergency_treatment.js`
- API calls found: 2
- **Missing backend coverage for:** __M0__, __M1__

### ❌ emergency/emergency_visits
- File: `D:\recovers\data\medical\static\js\pages\emergency\emergency_visits.js`
- API calls found: 2
- **Missing backend coverage for:** __M0__, __M1__

### ❌ emergency/list
- File: `D:\recovers\data\medical\static\js\pages\emergency\list.js`
- API calls found: 0

### ❌ emergency/patient_queue
- File: `D:\recovers\data\medical\static\js\pages\emergency\patient_queue.js`
- API calls found: 0

### ❌ emergency/triage
- File: `D:\recovers\data\medical\static\js\pages\emergency\triage.js`
- API calls found: 2
- **Missing backend coverage for:** __M0__, __M1__

### ❌ emergency/view
- File: `D:\recovers\data\medical\static\js\pages\emergency\view.js`
- API calls found: 1
- **Missing backend coverage for:** __M0__

### ❌ kiosk/check_in
- File: `D:\recovers\data\medical\static\js\pages\kiosk\check_in.js`
- API calls found: 0

### ❌ lab/dashboard_new
- File: `D:\recovers\data\medical\static\js\pages\lab\dashboard_new.js`
- API calls found: 0

### ❌ lab/lab_requests_results_print
- File: `D:\recovers\data\medical\static\js\pages\lab\lab_requests_results_print.js`
- API calls found: 0

### ❌ manager/dashboard
- File: `D:\recovers\data\medical\static\js\pages\manager\dashboard.js`
- API calls found: 1
- **Missing backend coverage for:** __M0__

### ❌ manager/monitoring
- File: `D:\recovers\data\medical\static\js\pages\manager\monitoring.js`
- API calls found: 8
- **Missing backend coverage for:** __M5__, __M4__, __M0__, __M2__, __M7__, __M3__, __M6__, __M1__

### ❌ manager/pricing
- File: `D:\recovers\data\medical\static\js\pages\manager\pricing.js`
- API calls found: 3
- **Missing backend coverage for:** manager.get_services_api, __M0__, __M1__

### ❌ manager/reports
- File: `D:\recovers\data\medical\static\js\pages\manager\reports.js`
- API calls found: 0

### ❌ manager/user_management
- File: `D:\recovers\data\medical\static\js\pages\manager\user_management.js`
- API calls found: 0

### ❌ medication/interactions
- File: `D:\recovers\data\medical\static\js\pages\medication\interactions.js`
- API calls found: 2
- **Missing backend coverage for:** __M0__, medication.toggle_interaction

### ❌ medication/supply_request_detail
- File: `D:\recovers\data\medical\static\js\pages\medication\supply_request_detail.js`
- API calls found: 2
- **Missing backend coverage for:** __M0__, __M1__

### ❌ nurse/dashboard_new
- File: `D:\recovers\data\medical\static\js\pages\nurse\dashboard_new.js`
- API calls found: 1
- **Missing backend coverage for:** __M0__

### ❌ nurse/vital_signs
- File: `D:\recovers\data\medical\static\js\pages\nurse\vital_signs.js`
- API calls found: 0

### ❌ owner/dashboard
- File: `D:\recovers\data\medical\static\js\pages\owner\dashboard.js`
- API calls found: 1
- **Missing backend coverage for:** __M0__

### ❌ pharmacy/pos
- File: `D:\recovers\data\medical\static\js\pages\pharmacy\pos.js`
- API calls found: 0

### ❌ portal/base
- File: `D:\recovers\data\medical\static\js\pages\portal\base.js`
- API calls found: 0

### ❌ print/emergency_report
- File: `D:\recovers\data\medical\static\js\pages\print\emergency_report.js`
- API calls found: 0

### ❌ print/invoice
- File: `D:\recovers\data\medical\static\js\pages\print\invoice.js`
- API calls found: 0

### ❌ print/prescription
- File: `D:\recovers\data\medical\static\js\pages\print\prescription.js`
- API calls found: 0

### ❌ print/radiology_report
- File: `D:\recovers\data\medical\static\js\pages\print\radiology_report.js`
- API calls found: 0

### ❌ print/receipt
- File: `D:\recovers\data\medical\static\js\pages\print\receipt.js`
- API calls found: 0

### ❌ print/report
- File: `D:\recovers\data\medical\static\js\pages\print\report.js`
- API calls found: 0

### ❌ quality_compliance/dashboard
- File: `D:\recovers\data\medical\static\js\pages\quality_compliance\dashboard.js`
- API calls found: 1
- **Missing backend coverage for:** __M0__

### ❌ radiology/add_scan
- File: `D:\recovers\data\medical\static\js\pages\radiology\add_scan.js`
- API calls found: 0

### ❌ radiology/dashboard_new
- File: `D:\recovers\data\medical\static\js\pages\radiology\dashboard_new.js`
- API calls found: 0

### ❌ radiology/process
- File: `D:\recovers\data\medical\static\js\pages\radiology\process.js`
- API calls found: 8
- **Missing backend coverage for:** __M5__, __M4__, __M0__, __M2__, __M7__, __M3__, __M6__, __M1__

### ❌ reception/add_patient_to_queue
- File: `D:\recovers\data\medical\static\js\pages\reception\add_patient_to_queue.js`
- API calls found: 2
- **Missing backend coverage for:** reception.api_doctors, reception.queue_management

### ❌ reception/calls_display
- File: `D:\recovers\data\medical\static\js\pages\reception\calls_display.js`
- API calls found: 1
- **Missing backend coverage for:** __M0__

### ❌ reception/create_appointment
- File: `D:\recovers\data\medical\static\js\pages\reception\create_appointment.js`
- API calls found: 3
- **Missing backend coverage for:** __M0__, booking.api_available_doctors, booking.api_available_times

### ❌ reception/create_visit
- File: `D:\recovers\data\medical\static\js\pages\reception\create_visit.js`
- API calls found: 9
- **Missing backend coverage for:** reception.pos_charge, __M0__, reception.api_visit_pricing, reception.patients, reception.api_department_services, __M2__, __M3__, reception.api_department_staff, __M1__

### ❌ reception/patients
- File: `D:\recovers\data\medical\static\js\pages\reception\patients.js`
- API calls found: 3
- **Missing backend coverage for:** reception.api_smart_patient_search, __M0__, __M1__

### ❌ reception/queue_management
- File: `D:\recovers\data\medical\static\js\pages\reception\queue_management.js`
- API calls found: 13
- **Missing backend coverage for:** reception.approve_emergency_debt, reception.api_queue_wait_metrics, reception.transfer_visit, reception.return_to_queue, __M0__, __M2__, reception.complete_treatment, reception.start_treatment, reception.api_department_staff, reception.cancel_ticket, reception.skip_patient, __M1__, reception.approve_force_entry

### ❌ reception/view_appointment
- File: `D:\recovers\data\medical\static\js\pages\reception\view_appointment.js`
- API calls found: 3
- **Missing backend coverage for:** reception.cancel_appointment, reception.no_show_appointment, reception.confirm_appointment

### ❌ reception/waiting_display
- File: `D:\recovers\data\medical\static\js\pages\reception\waiting_display.js`
- API calls found: 1
- **Missing backend coverage for:** __M0__

### ❌ report_builder/builder
- File: `D:\recovers\data\medical\static\js\pages\report_builder\builder.js`
- API calls found: 8
- **Missing backend coverage for:** __M5__, __M4__, __M0__, __M2__, __M7__, __M3__, __M6__, __M1__

### ❌ super_admin/analytics
- File: `D:\recovers\data\medical\static\js\pages\super_admin\analytics.js`
- API calls found: 0

### ❌ super_admin/audit_trail
- File: `D:\recovers\data\medical\static\js\pages\super_admin\audit_trail.js`
- API calls found: 1
- **Missing backend coverage for:** __M0__

### ❌ super_admin/branch_templates
- File: `D:\recovers\data\medical\static\js\pages\super_admin\branch_templates.js`
- API calls found: 1
- **Missing backend coverage for:** __M0__

### ❌ super_admin/branding
- File: `D:\recovers\data\medical\static\js\pages\super_admin\branding.js`
- API calls found: 3
- **Missing backend coverage for:** __M0__, __M2__, __M1__

### ❌ super_admin/create_user
- File: `D:\recovers\data\medical\static\js\pages\super_admin\create_user.js`
- API calls found: 0

### ❌ super_admin/department_detail
- File: `D:\recovers\data\medical\static\js\pages\super_admin\department_detail.js`
- API calls found: 2
- **Missing backend coverage for:** super_admin.deactivate_department, super_admin.activate_department

### ❌ super_admin/department_staff
- File: `D:\recovers\data\medical\static\js\pages\super_admin\department_staff.js`
- API calls found: 4
- **Missing backend coverage for:** __M0__, super_admin.remove_staff_from_department, super_admin.add_staff_to_department, __M1__

### ❌ super_admin/maintenance_automation
- File: `D:\recovers\data\medical\static\js\pages\super_admin\maintenance_automation.js`
- API calls found: 1
- **Missing backend coverage for:** __M0__

### ❌ super_admin/performance
- File: `D:\recovers\data\medical\static\js\pages\super_admin\performance.js`
- API calls found: 0

### ❌ super_admin/permissions
- File: `D:\recovers\data\medical\static\js\pages\super_admin\permissions.js`
- API calls found: 0

### ❌ super_admin/queue_settings
- File: `D:\recovers\data\medical\static\js\pages\super_admin\queue_settings.js`
- API calls found: 2
- **Missing backend coverage for:** __M0__, __M1__

### ❌ super_admin/roles
- File: `D:\recovers\data\medical\static\js\pages\super_admin\roles.js`
- API calls found: 3
- **Missing backend coverage for:** super_admin.manage_role_department_permissions, super_admin.manage_role_permissions, super_admin.edit_role

### ❌ super_admin/security_logs
- File: `D:\recovers\data\medical\static\js\pages\super_admin\security_logs.js`
- API calls found: 0

### ❌ super_admin/service_detail
- File: `D:\recovers\data\medical\static\js\pages\super_admin\service_detail.js`
- API calls found: 2
- **Missing backend coverage for:** super_admin.activate_service, super_admin.deactivate_service

### ❌ super_admin/service_pricing
- File: `D:\recovers\data\medical\static\js\pages\super_admin\service_pricing.js`
- API calls found: 0

### ❌ super_admin/system_config
- File: `D:\recovers\data\medical\static\js\pages\super_admin\system_config.js`
- API calls found: 7
- **Missing backend coverage for:** __M5__, __M4__, __M0__, __M2__, __M3__, __M6__, __M1__

### ❌ super_admin/system_maintenance
- File: `D:\recovers\data\medical\static\js\pages\super_admin\system_maintenance.js`
- API calls found: 1
- **Missing backend coverage for:** main.health

### ❌ super_admin/users
- File: `D:\recovers\data\medical\static\js\pages\super_admin\users.js`
- API calls found: 2
- **Missing backend coverage for:** super_admin.reset_user_password, super_admin.delete_user

## Orphaned Backend Templates (No Frontend Coverage)

- `READ_RECEPTION_QUEUE_DISPLAYS` (unknown) - APIs: reception.add_patient_to_queue
- `READ_RECEPTION_LOOKUP_APIS` (unknown) - APIs: none
- `READ_DOCTOR_WORK_LISTS` (unknown) - APIs: doctor.start_treatment
- `READ_DOCTOR_PATIENT_CHART` (unknown) - APIs: doctor.notes
- `READ_DOCTOR_ORDER_AND_RESULT_LISTS` (unknown) - APIs: doctor.lab_request, doctor.radiology_request, doctor.prescription
- `READ_DOCTOR_RECORDS_AND_PATIENTS` (unknown) - APIs: doctor.notes
- `READ_NURSING_WORK_LISTS` (unknown) - APIs: nurse.create_task
- `READ_NURSING_PATIENT_SURFACES` (unknown) - APIs: nurse.record_vital_signs
- `READ_LAB_WORKLIST_AND_RESULTS` (unknown) - APIs: lab.worklist_complete
- `READ_LAB_CATALOGUE_AND_QUALITY` (unknown) - APIs: lab.test_catalog_add, lab.test_panels_add
- `READ_LAB_PRINTABLES` (unknown) - APIs: lab.worklist_complete
- `READ_RADIOLOGY_WORKLIST_AND_REPORTS` (unknown) - APIs: api_radiology.amend_radiology_result
- `READ_RADIOLOGY_PRINTABLES_AND_FILES` (unknown) - APIs: api_radiology.amend_radiology_result
- `READ_PHARMACY_CATALOGUE_AND_STOCK` (unknown) - APIs: medication.add_medication, medication.add_supplier, medication.add_purchase
- `READ_PHARMACY_SALES_AND_PRESCRIPTIONS` (unknown) - APIs: medication.pharmacy_pos_charge
- `READ_PHARMACY_RECEIPTS` (unknown) - APIs: medication.pharmacy_pos_charge
- `READ_EMERGENCY_TRIAGE_AND_QUEUE` (unknown) - APIs: emergency.start_treatment
- `READ_EMERGENCY_CASE_DETAIL` (unknown) - APIs: emergency.start_treatment
- `READ_EMERGENCY_PATIENT_CONTEXT` (unknown) - APIs: emergency.prescription
- `READ_FINANCE_OPS_AND_SLOW_QUERIES` (unknown) - APIs: finance.archive_visit
- `READ_MANAGER_REPORT_CENTRE` (unknown) - APIs: report_builder.templates_save
- `READ_MANAGER_STAFF_AND_DEPARTMENTS` (unknown) - APIs: manager.staff_schedule
- `READ_PATIENT_PORTAL_RECORDS` (unknown) - APIs: portal.link_account
- `READ_CLINICAL_CODING_LOOKUPS` (unknown) - APIs: doctor.diagnosis
- `READ_QUALITY_DASHBOARD` (unknown) - APIs: doctor.notes
- `READ_SECURITY_SURFACES` (unknown) - APIs: auth.login
- `READ_WHAT_IF_SCENARIO_MODELLING` (unknown) - APIs: what_if.new_scenario
- `READ_OWNER_TENANT_DIRECTORY` (unknown) - APIs: owner.owner_create_tenant
- `READ_OWNER_PLATFORM_OBSERVABILITY` (unknown) - APIs: owner.owner_create_tenant
- `READ_OWNER_BILLING_AND_VAULT` (unknown) - APIs: owner.owner_renew_subscription
- `READ_OWNER_CONFIGURATION_AND_INTEGRATIONS` (unknown) - APIs: owner.owner_save_system_config
- `READ_SUPERADMIN_SECURITY_SURFACES` (unknown) - APIs: super_admin.edit_user
- `READ_SUPERADMIN_OPERATIONS_SURFACES` (unknown) - APIs: super_admin.system_cleanup
- `READ_SUPERADMIN_BRANDING_AND_SUBSCRIPTION` (unknown) - APIs: super_admin.apply_branding_theme
- `READ_DICOM_STUDY_BROWSER` (unknown) - APIs: doctor.radiology_request, api_radiology.amend_radiology_result
- `READ_SPECIALTY_FORMS_AND_SUBMISSIONS` (unknown) - APIs: specialty_forms.new_form, specialty_forms.fill_form
- `READ_BED_MANAGEMENT_AND_ADMISSIONS` (unknown) - APIs: bed.api_admit
- `READ_CLINICAL_DECISION_SUPPORT` (unknown) - APIs: medication.add_medication
- `READ_CARE_PATHWAYS` (unknown) - APIs: doctor.diagnosis
- `READ_POPULATION_HEALTH_AND_REGISTRY` (unknown) - APIs: doctor.diagnosis, super_admin.seed_users
- `READ_REFERRAL_TRACKING` (unknown) - APIs: doctor.diagnosis
- `READ_OPERATING_ROOM_SURGICAL_RECORDS` (unknown) - APIs: doctor.notes, handover.handover_open
- `READ_HANDOVER_AND_NURSING_ASSESSMENT` (unknown) - APIs: handover.handover_open, nursing_assessment.new_assessment
- `READ_KIOSK_AND_BARCODE_REGISTRY` (unknown) - APIs: reception.add_patient_to_queue
- `READ_AI_IMAGING_CONSOLE` (unknown) - APIs: ai_imaging.request_analysis, ai_imaging.review
- `READ_PUBLIC_INFORMATION_PAGES` (unknown) - APIs: none
- `READ_IHE_PATIENT_AND_DOCUMENT_QUERIES` (unknown) - APIs: reception.add_patient
- `READ_PROCUREMENT_AND_SUPPLIER_VIEWS` (unknown) - APIs: medication.add_purchase
- `READ_PWA_AND_METRICS_SURFACES` (unknown) - APIs: none
- `READ_DIAGNOSTIC_SURFACES_REVEAL_IDENTITY` (unknown) - APIs: none
- `READ_ERROR_TRIGGER_ROUTES` (unknown) - APIs: none
- `READ_TRACE_AND_STATUS_ROUTES` (unknown) - APIs: none
- `READ_QUEUE_DISPLAY_AND_DEPARTMENT_STATUS` (unknown) - APIs: reception.add_patient_to_queue
- `READ_PATIENT_EDUCATION_LIBRARY` (unknown) - APIs: patient_education.new_material, patient_education.assign_material
- `READ_TELEMEDICINE_CONSULTATION_ROOM` (unknown) - APIs: telemedicine.new_appointment, telemedicine.start_consult
- `READ_REPORT_BUILDER_INTERFACES` (unknown) - APIs: report_builder.templates_save
- `READ_SUPERADMIN_EXPORT_AND_ACCOUNT_ACTIONS` (unknown) - APIs: super_admin.create_user
- `READ_SUBSCRIPTION_RENEWAL_IS_A_WRITE_ON_GET` (unknown) - APIs: owner.owner_create_tenant, owner.owner_create_plan, owner.owner_renew_subscription
- `READ_DOCTOR_AND_LAB_CATALOGUE_SURFACES` (unknown) - APIs: lab.test_catalog_add
- `READ_RADIOLOGY_TEST_CATALOGUE` (unknown) - APIs: radiology.add_scan_post, api_radiology.amend_radiology_result
- `READ_PHARMACY_EXTERNAL_CATALOGUE_AND_EMERGENCY_PRINTS` (unknown) - APIs: medication.add_medication, emergency.prescription
- `READ_PORTAL_BOOKING_AND_DOCUMENTS` (unknown) - APIs: portal.link_account
- `READ_CLINICAL_CODING_DRG_LIST` (unknown) - APIs: doctor.diagnosis
- `READ_FINANCE_WEEKLY_SLOW_QUERY_DETAIL` (unknown) - APIs: finance.capture_slow_queries_weekly
- `READ_STATIC_AND_FAVICON_SURFACES` (unknown) - APIs: none

## Backend Template APIs Not Covered by Frontend

- **READ_RECEPTION_QUEUE_DISPLAYS**: reception.add_patient_to_queue
- **READ_DOCTOR_WORK_LISTS**: doctor.start_treatment
- **READ_DOCTOR_PATIENT_CHART**: doctor.notes
- **READ_DOCTOR_ORDER_AND_RESULT_LISTS**: doctor.lab_request, doctor.radiology_request, doctor.prescription
- **READ_DOCTOR_RECORDS_AND_PATIENTS**: doctor.notes
- **READ_NURSING_WORK_LISTS**: nurse.create_task
- **READ_NURSING_PATIENT_SURFACES**: nurse.record_vital_signs
- **READ_LAB_WORKLIST_AND_RESULTS**: lab.worklist_complete
- **READ_LAB_CATALOGUE_AND_QUALITY**: lab.test_catalog_add, lab.test_panels_add
- **READ_LAB_PRINTABLES**: lab.worklist_complete
- **READ_RADIOLOGY_WORKLIST_AND_REPORTS**: api_radiology.amend_radiology_result
- **READ_RADIOLOGY_PRINTABLES_AND_FILES**: api_radiology.amend_radiology_result
- **READ_PHARMACY_CATALOGUE_AND_STOCK**: medication.add_medication, medication.add_supplier, medication.add_purchase
- **READ_PHARMACY_SALES_AND_PRESCRIPTIONS**: medication.pharmacy_pos_charge
- **READ_PHARMACY_RECEIPTS**: medication.pharmacy_pos_charge
- **READ_EMERGENCY_TRIAGE_AND_QUEUE**: emergency.start_treatment
- **READ_EMERGENCY_CASE_DETAIL**: emergency.start_treatment
- **READ_EMERGENCY_PATIENT_CONTEXT**: emergency.prescription
- **READ_FINANCE_OPS_AND_SLOW_QUERIES**: finance.archive_visit
- **READ_MANAGER_REPORT_CENTRE**: report_builder.templates_save
- **READ_MANAGER_STAFF_AND_DEPARTMENTS**: manager.staff_schedule
- **READ_MANAGER_PRICING_AND_SATISFACTION**: manager.seed_pricing
- **READ_PATIENT_PORTAL_RECORDS**: portal.link_account
- **READ_PATIENT_PORTAL_BILLS_AND_BOOKING**: portal.link_account, booking.create_booking
- **READ_CLINICAL_CODING_LOOKUPS**: doctor.diagnosis
- **READ_QUALITY_DASHBOARD**: doctor.notes
- **READ_SECURITY_SURFACES**: auth.login
- **READ_WHAT_IF_SCENARIO_MODELLING**: what_if.new_scenario
- **READ_OWNER_TENANT_DIRECTORY**: owner.owner_create_tenant
- **READ_OWNER_PLATFORM_OBSERVABILITY**: owner.owner_create_tenant
- **READ_OWNER_BILLING_AND_VAULT**: owner.owner_renew_subscription
- **READ_OWNER_CONFIGURATION_AND_INTEGRATIONS**: owner.owner_save_system_config
- **READ_SUPERADMIN_SECURITY_SURFACES**: super_admin.edit_user
- **READ_SUPERADMIN_OPERATIONS_SURFACES**: super_admin.system_cleanup
- **READ_SUPERADMIN_BRANDING_AND_SUBSCRIPTION**: super_admin.apply_branding_theme
- **READ_DICOM_STUDY_BROWSER**: doctor.radiology_request, api_radiology.amend_radiology_result
- **READ_SPECIALTY_FORMS_AND_SUBMISSIONS**: specialty_forms.new_form, specialty_forms.fill_form
- **READ_BED_MANAGEMENT_AND_ADMISSIONS**: bed.api_admit
- **READ_CLINICAL_DECISION_SUPPORT**: medication.add_medication
- **READ_CARE_PATHWAYS**: doctor.diagnosis
- **READ_POPULATION_HEALTH_AND_REGISTRY**: doctor.diagnosis, super_admin.seed_users
- **READ_REFERRAL_TRACKING**: doctor.diagnosis
- **READ_OPERATING_ROOM_SURGICAL_RECORDS**: doctor.notes, handover.handover_open
- **READ_HANDOVER_AND_NURSING_ASSESSMENT**: handover.handover_open, nursing_assessment.new_assessment
- **READ_KIOSK_AND_BARCODE_REGISTRY**: reception.add_patient_to_queue
- **READ_AI_IMAGING_CONSOLE**: ai_imaging.request_analysis, ai_imaging.review
- **READ_GLOBAL_SEARCH**: reception.add_patient
- **READ_FHIR_BUNDLE_ENDPOINTS**: reception.add_patient
- **READ_IHE_PATIENT_AND_DOCUMENT_QUERIES**: reception.add_patient
- **READ_PROCUREMENT_AND_SUPPLIER_VIEWS**: medication.add_purchase
- **READ_ROOT_LEVEL_SHORTCUTS**: reception.add_patient
- **READ_DASHBOARD_SNAPSHOT_AND_PATIENT_SEARCH_API**: reception.add_patient
- **READ_QUEUE_DISPLAY_AND_DEPARTMENT_STATUS**: reception.add_patient_to_queue
- **READ_PATIENT_EDUCATION_LIBRARY**: patient_education.new_material, patient_education.assign_material
- **READ_TELEMEDICINE_CONSULTATION_ROOM**: telemedicine.new_appointment, telemedicine.start_consult
- **READ_REPORT_BUILDER_INTERFACES**: report_builder.templates_save
- **READ_SUPERADMIN_EXPORT_AND_ACCOUNT_ACTIONS**: super_admin.create_user
- **READ_SUBSCRIPTION_RENEWAL_IS_A_WRITE_ON_GET**: owner.owner_create_tenant, owner.owner_create_plan, owner.owner_renew_subscription
- **READ_DOCTOR_AND_LAB_CATALOGUE_SURFACES**: lab.test_catalog_add
- **READ_RADIOLOGY_TEST_CATALOGUE**: radiology.add_scan_post, api_radiology.amend_radiology_result
- **READ_PHARMACY_EXTERNAL_CATALOGUE_AND_EMERGENCY_PRINTS**: medication.add_medication, emergency.prescription
- **READ_PORTAL_BOOKING_AND_DOCUMENTS**: portal.link_account
- **READ_CLINICAL_CODING_DRG_LIST**: doctor.diagnosis
- **READ_FINANCE_WEEKLY_SLOW_QUERY_DETAIL**: finance.capture_slow_queries_weekly

## API Cross-Reference Matrix

| Frontend Page | Blueprint | API Calls | Matched Templates | Missing |
|---------------|-----------|-----------|-------------------|---------|
| accountant/dashboard_new | accountant | __M0__ |  | __M0__ |
| accountant/pending_payments | accountant |  |  |  |
| accountant/process_payment | accountant | __M0__, reception_currency.check_rate |  | __M0__, reception_currency.check_rate |
| barcode/scan | barcode | __M0__, __M1__ |  | __M0__, __M1__ |
| biometric/status | biometric | __M0__ |  | __M0__ |
| booking/create | booking | __M4__, __M0__, __M2__... |  | __M4__, __M0__... |
| booking/index | booking | __M0__, __M1__ |  | __M0__, __M1__ |
| doctor/dashboard | doctor | __M5__, __M4__, __M0__... |  | __M5__, __M4__... |
| doctor/dental_chart | doctor | __M5__, __M4__, __M0__... |  | __M5__, __M4__... |
| doctor/diagnosis | doctor |  |  |  |
| doctor/notes | doctor | __M0__, __M2__, __M1__ |  | __M0__, __M2__... |
| doctor/patient_details | doctor | __M0__, __M1__ |  | __M0__, __M1__ |
| doctor/patient_queue | doctor | __M0__, __M2__, reception.get_smart_queue_management... |  | __M0__, __M2__... |
| doctor/prescription | doctor | __M0__ |  | __M0__ |
| doctor/visit_summary | doctor | __M0__, __M1__ |  | __M0__, __M1__ |
| emergency/dashboard_new | emergency |  |  |  |
| emergency/edit | emergency | __M0__, __M1__ |  | __M0__, __M1__ |
| emergency/emergency_treatment | emergency | __M0__, __M1__ |  | __M0__, __M1__ |
| emergency/emergency_visits | emergency | __M0__, __M1__ |  | __M0__, __M1__ |
| emergency/list | emergency |  |  |  |
| emergency/patient_queue | emergency |  |  |  |
| emergency/triage | emergency | __M0__, __M1__ |  | __M0__, __M1__ |
| emergency/view | emergency | __M0__ |  | __M0__ |
| kiosk/check_in | kiosk |  |  |  |
| lab/dashboard_new | lab |  |  |  |
| lab/lab_requests_results_print | lab |  |  |  |
| manager/dashboard | manager | __M0__ |  | __M0__ |
| manager/monitoring | manager | __M5__, __M4__, __M0__... |  | __M5__, __M4__... |
| manager/pricing | manager | manager.get_services_api, __M0__, __M1__ |  | manager.get_services_api, __M0__... |
| manager/reports | manager |  |  |  |
| manager/unit_control | manager | manager.unit_toggle | READ_MANAGER_PRICING_AND_SATISFACTION |  |
| manager/user_management | manager |  |  |  |
| medication/interactions | medication | __M0__, medication.toggle_interaction |  | __M0__, medication.toggle_interaction |
| medication/supply_request_detail | medication | __M0__, __M1__ |  | __M0__, __M1__ |
| nurse/dashboard_new | nurse | __M0__ |  | __M0__ |
| nurse/vital_signs | nurse |  |  |  |
| owner/dashboard | owner | __M0__ |  | __M0__ |
| pharmacy/pos | pharmacy |  |  |  |
| portal/base | portal |  |  |  |
| print/emergency_report | print |  |  |  |
| print/invoice | print |  |  |  |
| print/prescription | print |  |  |  |
| print/radiology_report | print |  |  |  |
| print/receipt | print |  |  |  |
| print/report | print |  |  |  |
| quality_compliance/dashboard | quality_compliance | __M0__ |  | __M0__ |
| radiology/add_scan | radiology |  |  |  |
| radiology/dashboard_new | radiology |  |  |  |
| radiology/process | radiology | __M5__, __M4__, __M0__... |  | __M5__, __M4__... |
| reception/add_patient_to_queue | reception | reception.api_doctors, reception.queue_management |  | reception.api_doctors, reception.queue_management |
| reception/appointments | reception | reception.appointments, __M0__, reception.create_appointment... | READ_DASHBOARD_SNAPSHOT_AND_PATIENT_SEARCH_API, READ_LANDING_AND_ACCOUNT_PAGES... | reception.appointments, __M0__... |
| reception/calls_display | reception | __M0__ |  | __M0__ |
| reception/create_appointment | reception | __M0__, booking.api_available_doctors, booking.api_available_times |  | __M0__, booking.api_available_doctors... |
| reception/create_visit | reception | reception.pos_charge, __M0__, reception.api_visit_pricing... |  | reception.pos_charge, __M0__... |
| reception/patients | reception | reception.api_smart_patient_search, __M0__, __M1__ |  | reception.api_smart_patient_search, __M0__... |
| reception/queue_management | reception | reception.approve_emergency_debt, reception.api_queue_wait_metrics, reception.transfer_visit... |  | reception.approve_emergency_debt, reception.api_queue_wait_metrics... |
| reception/view_appointment | reception | reception.cancel_appointment, reception.no_show_appointment, reception.confirm_appointment |  | reception.cancel_appointment, reception.no_show_appointment... |
| reception/visits | reception | reception.edit_visit, reception.export_visits, reception.print_receipt... | READ_ACCOUNTANT_DASHBOARDS_AND_REPORTS, READ_PAYMENT_CONSOLE... | reception.edit_visit, reception.export_visits... |
| reception/waiting_display | reception | __M0__ |  | __M0__ |
| report_builder/builder | report_builder | __M5__, __M4__, __M0__... |  | __M5__, __M4__... |
| super_admin/analytics | super_admin |  |  |  |
| super_admin/audit_trail | super_admin | __M0__ |  | __M0__ |
| super_admin/branch_templates | super_admin | __M0__ |  | __M0__ |
| super_admin/branding | super_admin | __M0__, __M2__, __M1__ |  | __M0__, __M2__... |
| super_admin/create_user | super_admin |  |  |  |
| super_admin/department_detail | super_admin | super_admin.deactivate_department, super_admin.activate_department |  | super_admin.deactivate_department, super_admin.activate_department |
| super_admin/department_staff | super_admin | __M0__, super_admin.remove_staff_from_department, super_admin.add_staff_to_department... |  | __M0__, super_admin.remove_staff_from_department... |
| super_admin/departments | super_admin | super_admin.department_staff, super_admin.export_departments, super_admin.deactivate_department... | READ_SUPERADMIN_CATALOGUE_AND_PRICING | super_admin.department_staff, super_admin.export_departments... |
| super_admin/maintenance_automation | super_admin | __M0__ |  | __M0__ |
| super_admin/performance | super_admin |  |  |  |
| super_admin/permissions | super_admin |  |  |  |
| super_admin/queue_settings | super_admin | __M0__, __M1__ |  | __M0__, __M1__ |
| super_admin/roles | super_admin | super_admin.manage_role_department_permissions, super_admin.manage_role_permissions, super_admin.edit_role |  | super_admin.manage_role_department_permissions, super_admin.manage_role_permissions... |
| super_admin/security_logs | super_admin |  |  |  |
| super_admin/service_detail | super_admin | super_admin.activate_service, super_admin.deactivate_service |  | super_admin.activate_service, super_admin.deactivate_service |
| super_admin/service_pricing | super_admin |  |  |  |
| super_admin/services | super_admin | super_admin.service_pricing, super_admin.edit_service, super_admin.view_service... | READ_SUPERADMIN_CATALOGUE_AND_PRICING | super_admin.service_pricing, super_admin.edit_service... |
| super_admin/system_backup | super_admin | super_admin.cancel_backup, super_admin.delete_backup, super_admin.create_backup... | READ_BACKUP_CONSOLE_VIEWS, READ_SUPERADMIN_SYSTEM_AND_BACKUP_VIEWS | super_admin.cancel_backup, super_admin.delete_backup... |
| super_admin/system_config | super_admin | __M5__, __M4__, __M0__... |  | __M5__, __M4__... |
| super_admin/system_maintenance | super_admin | main.health |  | main.health |
| super_admin/users | super_admin | super_admin.reset_user_password, super_admin.delete_user |  | super_admin.reset_user_password, super_admin.delete_user |