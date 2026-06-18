## إحصاء الاندبوينتس ومطابقتها مع الباكند

**تاريخ الإنشاء:** 2026-01-23

### الملخص
- إجمالي الاندبوينتس في الباكند: 383
- إجمالي استدعاءات url_for في القوالب: 628
- إجمالي الاندبوينتس المميزة المستخدمة في القوالب: 229
- الاندبوينتس المستخدمة ولا تظهر في الباكند: 0

> ملاحظة: كان هناك مرجع واحد إلى `static` في القوالب، وهو اندبوينت افتراضي في Flask وليس مسارًا مخصصًا.

### توزيع الاندبوينتس حسب الـ Blueprint
- accountant: 16
- auth: 4
- backup: 6
- booking: 19
- doctor: 34
- emergency: 32
- finance: 11
- lab: 22
- main: 8
- manager: 28
- medication: 19
- nurse: 17
- payment: 6
- radiology: 27
- reception: 64
- super_admin: 78

### اندبوينتس باكند غير مستخدمة في القوالب (كاملة)
- accountant.daily_summary
- accountant.financial_report
- accountant.index
- accountant.invoices
- accountant.monthly_audit_report
- accountant.open_invoices
- accountant.payment_documentation
- accountant.receipt
- accountant.reports
- auth.change_password
- booking.telemedicine_room
- doctor.index
- doctor.lab_requests
- doctor.lab_results
- doctor.medical_records
- doctor.print_medical_report
- doctor.radiology_requests
- doctor.radiology_results
- doctor.view_patient
- doctor.visits
- emergency.api_ems_intake
- emergency.create_emergency_case
- emergency.emergency_report
- emergency.index
- emergency.lab_results
- emergency.patients
- emergency.print_emergency_report
- emergency.print_prescription
- emergency.queue
- emergency.radiology_results
- finance.archive_visit
- finance.index
- finance.post_gl
- lab.api_fhir_lab_diagnostic_report
- lab.api_fhir_lab_observation
- lab.api_fhir_lab_observation_import
- lab.api_fhir_lab_service_request
- lab.api_hl7_import
- lab.api_worklist
- lab.index
- lab.worklist_complete
- main.api_search
- main.health
- main.settings
- manager.add_service_api
- manager.analytics
- manager.delete_service_api
- manager.departments
- manager.financial_reports
- manager.force_payment_approvals
- manager.get_services_api
- manager.index
- manager.seed_pricing
- manager.staff
- manager.unit_control
- manager.update_service_api
- manager.user_management
- medication.api_external_drug_import
- medication.api_external_drug_search
- medication.api_prescriptions
- medication.dispense_prescription
- medication.index
- medication.prescriptions
- medication.toggle_interaction
- nurse.api_nursing_protocols
- nurse.index
- nurse.vitals
- nurse.wards
- payment.index
- payment.payment_history
- payment.payment_methods
- payment.payment_reports
- radiology.api_fhir_imaging_study
- radiology.api_fhir_radiology_diagnostic_report
- radiology.api_fhir_radiology_observation
- radiology.api_worklist
- radiology.images
- radiology.index
- radiology.results
- radiology.second_review_result
- reception.api_available_times
- reception.api_department_services
- reception.api_department_staff
- reception.api_doctors
- reception.api_fhir_appointment
- reception.api_fhir_encounter
- reception.api_fhir_organization
- reception.api_fhir_patient
- reception.api_fhir_practitioner
- reception.api_patient_queue_position
- reception.api_queue_status
- reception.api_queue_status_all
- reception.api_queue_wait_metrics
- reception.api_smart_patient_search
- reception.api_visit_pricing
- reception.approve_emergency_debt
- reception.approve_force_entry
- reception.call_next_patient
- reception.cancel_appointment
- reception.cancel_ticket
- reception.complete_treatment
- reception.confirm_appointment
- reception.end_visit
- reception.export_visits
- reception.index
- reception.no_show_appointment
- reception.payments
- reception.pos_charge
- reception.print_invoice
- reception.print_prescription
- reception.return_to_queue
- reception.save_queue_settings
- reception.skip_patient
- reception.start_treatment
- reception.survey
- reception.transfer_visit
- reception.view_visit
- super_admin.activate_department
- super_admin.activate_service
- super_admin.add_staff_to_department
- super_admin.api_ai_assistant
- super_admin.api_audit_log
- super_admin.api_recent_activities
- super_admin.backup
- super_admin.backup_history
- super_admin.backup_report
- super_admin.backup_schedule
- super_admin.branding
- super_admin.cancel_backup
- super_admin.create_backup
- super_admin.create_department
- super_admin.create_permission_simple
- super_admin.create_role_simple
- super_admin.create_service
- super_admin.deactivate_department
- super_admin.deactivate_service
- super_admin.delete_backup
- super_admin.delete_permission
- super_admin.delete_role
- super_admin.delete_user
- super_admin.download_export
- super_admin.edit_permission
- super_admin.export_backup_logs
- super_admin.export_departments
- super_admin.export_services
- super_admin.export_system_data
- super_admin.manage_role_department_permissions
- super_admin.performance
- super_admin.pricing
- super_admin.remove_staff_from_department
- super_admin.reset_user_password
- super_admin.restore_backup
- super_admin.save_backup_settings
- super_admin.system
- super_admin.system_maintenance

### تصنيف غير المستخدمة ولماذا
- API-only: مسارات تبدأ بـ /api أو اندبوينت يبدأ بـ api_، لا تحتاج قالب لأنها تُستهلك برمجيًا أو تكامل خارجي
  - أمثلة: lab.api_fhir_lab_observation, radiology.api_fhir_radiology_observation, reception.api_queue_status
- Action-only: مسارات POST/PUT/DELETE بلا GET، لا تحتاج قالب لأنها تُستدعى من فورم/زر
  - أمثلة: reception.cancel_ticket, manager.update_service_api, super_admin.delete_user
- صفحات تعمل كتحويل/مدخل: index/queue/health وغيرها غالبًا تعيد التوجيه داخليًا أو تُستخدم كمدخل للنظام
  - أمثلة: doctor.index, lab.index, finance.index, emergency.queue
- صفحات طباعة/تصدير: تُفتح غالبًا من زر أو رابط مباشر وتستخدم قوالب طباعة منفصلة
  - أمثلة: emergency.print_prescription, reception.print_invoice, super_admin.download_export
- صفحات موجود لها قوالب لكن غير مرتبطة في القوائم: يمكن ربطها في الواجهات إن رغبت
  - أمثلة: accountant.invoices, accountant.reports, payment.payment_methods

### تفاصيل الاندبوينتس (كامل)
لكل اندبوينت: المسارات، الطرق، الملفات، والاستخدام في القوالب.

#### accountant

| الاندبوينت | الطرق | المسارات | القوالب | الملف |
|---|---|---|---|---|
| accountant.api_erp_export | GET | /api/erp/export | 1 | accountant.py |
| accountant.daily_audit_report | GET | /audit/daily | 1 | accountant.py |
| accountant.daily_summary | GET | /daily-summary | 0 | accountant.py |
| accountant.dashboard | GET | /dashboard | 9 | accountant.py |
| accountant.debt_tracking_report | GET | /audit/debts | 2 | accountant.py |
| accountant.export_audit_report | GET | /audit/export/<report_type> | 3 | accountant.py |
| accountant.financial | GET | /financial | 2 | accountant.py |
| accountant.financial_report | GET | /financial-report | 0 | accountant.py |
| accountant.index | GET | / | 0 | accountant.py |
| accountant.invoices | GET | /invoices | 0 | accountant.py |
| accountant.monthly_audit_report | GET | /audit/monthly | 0 | accountant.py |
| accountant.open_invoices | GET | /open-invoices | 0 | accountant.py |
| accountant.payment_documentation | GET | /payment-documentation/<int:payment_id> | 0 | accountant.py |
| accountant.payments | GET | /payments | 1 | accountant.py |
| accountant.receipt | GET | /receipt/<int:payment_id> | 0 | accountant.py |
| accountant.reports | GET | /reports | 0 | accountant.py |

#### auth

| الاندبوينت | الطرق | المسارات | القوالب | الملف |
|---|---|---|---|---|
| auth.change_password | POST | /change-password | 0 | auth_routes.py |
| auth.login | GET,POST | /login | 4 | auth_routes.py |
| auth.logout | GET | /logout | 3 | auth_routes.py |
| auth.profile | GET,POST | /profile | 6 | auth_routes.py |

#### backup

| الاندبوينت | الطرق | المسارات | القوالب | الملف |
|---|---|---|---|---|
| backup.create_backup | GET,POST | /create | 3 | backup_routes.py |
| backup.dashboard | GET | /backup/dashboard | 2 | backup_routes.py |
| backup.delete_backup | POST | /delete/<int:backup_id> | 2 | backup_routes.py |
| backup.download_backup | GET | /download/<int:backup_id> | 3 | backup_routes.py |
| backup.list_backups | GET | /list | 1 | backup_routes.py |
| backup.restore_backup | POST | /restore/<int:backup_id> | 2 | backup_routes.py |

#### booking

| الاندبوينت | الطرق | المسارات | القوالب | الملف |
|---|---|---|---|---|
| booking.api_available_doctors | GET | /api/available-doctors | 2 | booking_routes.py |
| booking.api_available_times | GET | /api/available-times | 2 | booking_routes.py |
| booking.api_smart_slots | GET | /api/smart-slots | 1 | booking_routes.py |
| booking.cancel_booking | POST | /cancel/<int:booking_id> | 1 | booking_routes.py |
| booking.cancel_booking | POST | /booking/cancel/<int:booking_id> | 1 | booking_routes.py |
| booking.confirmation | GET | /confirmation/<int:booking_id> | 1 | booking_routes.py |
| booking.confirmation | GET | /booking/confirmation/<int:booking_id> | 1 | booking_routes.py |
| booking.create_booking | GET,POST | /create | 2 | booking_routes.py |
| booking.create_booking | GET,POST | /booking/create | 2 | booking_routes.py |
| booking.dashboard_portal | GET | /dashboard | 2 | booking_routes.py |
| booking.dashboard_portal | GET | /booking/dashboard | 2 | booking_routes.py |
| booking.index | GET | / | 5 | booking_routes.py |
| booking.index | GET | /booking | 5 | booking_routes.py |
| booking.payment | GET,POST | /payment/<int:booking_id> | 2 | booking_routes.py |
| booking.payment | GET,POST | /booking/payment/<int:booking_id> | 2 | booking_routes.py |
| booking.register | GET,POST | /register | 1 | booking_routes.py |
| booking.register | GET,POST | /booking/register | 1 | booking_routes.py |
| booking.telemedicine_room | GET | /telemedicine/<int:booking_id> | 0 | booking_routes.py |
| booking.telemedicine_room | GET | /booking/telemedicine/<int:booking_id> | 0 | booking_routes.py |

#### finance

| الاندبوينت | الطرق | المسارات | القوالب | الملف |
|---|---|---|---|---|
| finance.archive_visit | POST | /visits/<int:visit_id>/archive | 0 | finance.py |
| finance.audit | GET | /audit | 2 | finance.py |
| finance.capture_slow_queries_weekly | POST | /slow-queries/capture | 1 | finance.py |
| finance.dashboard | GET | /dashboard | 2 | finance.py |
| finance.index | GET | / | 0 | finance.py |
| finance.invoices | GET | /invoices | 1 | finance.py |
| finance.payments | GET | /payments | 2 | finance.py |
| finance.post_gl | POST | /post | 0 | finance.py |
| finance.slow_queries | GET | /slow-queries | 2 | finance.py |
| finance.slow_queries_weekly | GET | /slow-queries/weekly | 2 | finance.py |
| finance.slow_queries_weekly_detail | GET | /slow-queries/weekly/<int:report_id> | 1 | finance.py |

#### main

| الاندبوينت | الطرق | المسارات | القوالب | الملف |
|---|---|---|---|---|
| main.about_system | GET | /about-system | 1 | main.py |
| main.api_search | GET | /api/search | 0 | main.py |
| main.dashboard | GET | /dashboard | 3 | main.py |
| main.health | GET | /health | 0 | main.py |
| main.privacy_policy | GET | /privacy-policy | 1 | main.py |
| main.settings | GET | /settings | 0 | main.py |
| main.technical_support | GET | /technical-support | 1 | main.py |
| main.terms_of_use | GET | /terms-of-use | 1 | main.py |

#### payment

| الاندبوينت | الطرق | المسارات | القوالب | الملف |
|---|---|---|---|---|
| payment.dashboard | GET | /dashboard | 1 | payment_routes.py |
| payment.index | GET | / | 0 | payment_routes.py |
| payment.payment_history | GET | /history | 0 | payment_routes.py |
| payment.payment_methods | - | /methods | 0 | payment_routes.py |
| payment.payment_reports | GET | /reports | 0 | payment_routes.py |
| payment.process_payment | GET,POST | /process/<int:visit_id> | 2 | payment_routes.py |

#### doctor

| الاندبوينت | الطرق | المسارات | القوالب | الملف |
|---|---|---|---|---|
| doctor.api_dashboard_layout | GET,POST | /api/dashboard-layout | 1 | doctor.py |
| doctor.api_note_templates | GET | /api/note-templates | 1 | doctor.py |
| doctor.api_patient_search | GET | /api/patient-search | 1 | doctor.py |
| doctor.appointments | GET | /appointments | 1 | doctor.py |
| doctor.dashboard | GET | /dashboard | 6 | doctor.py |
| doctor.dashboard_for_doctor | GET | /dashboard/<int:doctor_id> | 1 | doctor.py |
| doctor.delete_note_template | POST | /api/note-templates/<string:template_id>/delete | 1 | doctor.py |
| doctor.diagnosis | GET,POST | /diagnosis/<int:visit_id> | 1 | doctor.py |
| doctor.end_treatment | POST | /end-treatment/<int:visit_id> | 2 | doctor.py |
| doctor.index | GET | / | 0 | doctor.py |
| doctor.lab_request | GET,POST | /lab-request/<int:visit_id> | 2 | doctor.py |
| doctor.lab_requests | GET | /lab-requests | 0 | doctor.py |
| doctor.lab_results | GET | /lab-results/<int:patient_id> | 0 | doctor.py |
| doctor.medical_history | GET | /medical-history/<int:patient_id> | 4 | doctor.py |
| doctor.medical_records | GET | /medical-records | 0 | doctor.py |
| doctor.notes | GET,POST | /notes/<int:visit_id> | 4 | doctor.py |
| doctor.patient_details | GET | /patient-details/<int:visit_id> | 3 | doctor.py |
| doctor.patient_queue | GET | /patient-queue | 5 | doctor.py |
| doctor.patient_timeline | GET | /patient-timeline/<int:patient_id> | 3 | doctor.py |
| doctor.patients | GET | /patients | 3 | doctor.py |
| doctor.prescription | GET,POST | /prescription/<int:visit_id> | 2 | doctor.py |
| doctor.prescriptions | GET | /prescriptions | 2 | doctor.py |
| doctor.prescriptions_history | GET | /prescriptions-history/<int:patient_id> | 3 | doctor.py |
| doctor.print_medical_report | GET | /print-medical-report/<int:visit_id> | 0 | doctor.py |
| doctor.print_prescription | GET | /print-prescription/<int:prescription_id> | 3 | doctor.py |
| doctor.radiology_request | GET,POST | /radiology-request/<int:visit_id> | 2 | doctor.py |
| doctor.radiology_requests | GET | /radiology-requests | 0 | doctor.py |
| doctor.radiology_results | GET | /radiology-results/<int:patient_id> | 0 | doctor.py |
| doctor.save_visit_summary | POST | /save-visit-summary/<int:visit_id> | 1 | doctor.py |
| doctor.start_treatment | POST | /start-treatment/<int:visit_id> | 2 | doctor.py |
| doctor.upsert_note_template | POST | /api/note-templates | 1 | doctor.py |
| doctor.view_patient | GET | /view_patient/<int:visit_id> | 0 | doctor.py |
| doctor.visit_summary | GET | /visit-summary/<int:visit_id> | 1 | doctor.py |
| doctor.visits | GET | /visits | 0 | doctor.py |

#### emergency

| الاندبوينت | الطرق | المسارات | القوالب | الملف |
|---|---|---|---|---|
| emergency.api_ems_intake | POST | /api/ems/intake | 0 | emergency.py |
| emergency.complete_visit | POST | /emergency-visits/<int:visit_id>/complete | 1 | emergency.py |
| emergency.convert_emergency_case | POST | /cases/<int:id>/convert | 3 | emergency.py |
| emergency.create_emergency_case | POST | /cases/create | 0 | emergency.py |
| emergency.dashboard | GET | /dashboard | 4 | emergency.py |
| emergency.edit_emergency_case | GET,POST | /cases/<int:id>/edit | 3 | emergency.py |
| emergency.emergency_report | GET | /emergency-report/<int:emergency_id> | 0 | emergency.py |
| emergency.emergency_treatment | GET,POST | /emergency-treatment/<int:visit_id> | 2 | emergency.py |
| emergency.emergency_visits | GET | /emergency-visits | 4 | emergency.py |
| emergency.end_treatment | POST | /end-treatment/<int:emergency_id> | 2 | emergency.py |
| emergency.index | GET | / | 0 | emergency.py |
| emergency.lab_request | GET,POST | /lab-request/<int:emergency_id> | 1 | emergency.py |
| emergency.lab_results | GET | /lab-results/<int:patient_id> | 0 | emergency.py |
| emergency.list_emergency_cases | GET | /cases | 3 | emergency.py |
| emergency.medical_history | GET | /medical-history/<int:patient_id> | 2 | emergency.py |
| emergency.patient_details | GET | /patient-details/<int:emergency_id> | 1 | emergency.py |
| emergency.patient_queue | GET | /patient-queue | 5 | emergency.py |
| emergency.patients | GET | /patients | 0 | emergency.py |
| emergency.prescription | GET,POST | /prescription/<int:emergency_id> | 2 | emergency.py |
| emergency.prescriptions_history | GET | /prescriptions-history/<int:patient_id> | 1 | emergency.py |
| emergency.print_emergency_report | GET | /print-emergency-report/<int:emergency_id> | 0 | emergency.py |
| emergency.print_prescription | GET | /print-prescription/<int:prescription_id> | 0 | emergency.py |
| emergency.queue | GET | /queue | 0 | emergency.py |
| emergency.radiology_request | GET,POST | /radiology-request/<int:emergency_id> | 2 | emergency.py |
| emergency.radiology_results | GET | /radiology-results/<int:patient_id> | 0 | emergency.py |
| emergency.reports | GET | /reports | 2 | emergency.py |
| emergency.resolve_emergency_case | POST | /cases/<int:id>/resolve | 4 | emergency.py |
| emergency.start_treatment | POST | /start-treatment/<int:emergency_id> | 2 | emergency.py |
| emergency.treatment | GET,POST | /treatment/<int:emergency_id> | 2 | emergency.py |
| emergency.triage | GET,POST | /triage/<int:emergency_id> | 3 | emergency.py |
| emergency.triage_list | GET | /triage | 1 | emergency.py |
| emergency.view_emergency_case | GET | /cases/<int:id> | 2 | emergency.py |

#### lab

| الاندبوينت | الطرق | المسارات | القوالب | الملف |
|---|---|---|---|---|
| lab.add_reagent | GET,POST | /reagents/add | 1 | lab.py |
| lab.api_fhir_lab_diagnostic_report | GET | /api/fhir/diagnosticreport/lab/<int:result_id> | 0 | lab.py |
| lab.api_fhir_lab_observation | GET | /api/fhir/observation/lab/<int:result_id> | 0 | lab.py |
| lab.api_fhir_lab_observation_import | POST | /api/fhir/observation | 0 | lab.py |
| lab.api_fhir_lab_service_request | POST | /api/fhir/servicerequest | 0 | lab.py |
| lab.api_hl7_import | POST | /api/hl7/import | 0 | lab.py |
| lab.api_worklist | GET | /api/worklist | 0 | lab.py |
| lab.dashboard | GET | /dashboard | 7 | lab.py |
| lab.edit_reagent | GET,POST | /reagents/<int:reagent_id>/edit | 1 | lab.py |
| lab.index | GET | / | 0 | lab.py |
| lab.print_request | GET | /print_request/<int:id> | 4 | lab.py |
| lab.quality | GET | /quality | 2 | lab.py |
| lab.quality_control | GET,POST | /quality-control | 2 | lab.py |
| lab.reagents | GET | /reagents | 2 | lab.py |
| lab.reports | GET | /reports | 1 | lab.py |
| lab.requests | GET | /requests | 1 | lab.py |
| lab.results | GET | /results | 1 | lab.py |
| lab.tests | GET | /tests | 1 | lab.py |
| lab.worklist | GET | /worklist | 4 | lab.py |
| lab.worklist_claim | POST | /worklist/claim/<int:request_id> | 1 | lab.py |
| lab.worklist_complete | POST | /worklist/complete/<int:request_id> | 0 | lab.py |
| lab.worklist_request | GET,POST | /worklist/request/<int:request_id> | 1 | lab.py |

#### manager

| الاندبوينت | الطرق | المسارات | القوالب | الملف |
|---|---|---|---|---|
| manager.add_service_api | POST | /api/pricing/services | 0 | manager.py |
| manager.analytics | GET | /analytics | 0 | manager.py |
| manager.api_what_if | POST | /api/what-if | 1 | manager.py |
| manager.approve_force_payment | POST | /approve-force-payment/<int:visit_id> | 1 | manager.py |
| manager.dashboard | GET | /dashboard | 3 | manager.py |
| manager.delete_service_api | DELETE | /api/pricing/services/<int:id> | 0 | manager.py |
| manager.departments | GET | /departments | 0 | manager.py |
| manager.financial_reports | GET | /financial-reports | 0 | manager.py |
| manager.force_payment_approvals | GET | /force-payment-approvals | 0 | manager.py |
| manager.get_services_api | GET | /api/pricing/services | 0 | manager.py |
| manager.index | GET | / | 0 | manager.py |
| manager.kpi_dashboard | GET | /kpi-dashboard | 2 | manager.py |
| manager.monitoring | GET | /monitoring | 3 | manager.py |
| manager.pricing | GET | /pricing | 1 | manager.py |
| manager.reject_force_payment | POST | /reject-force-payment/<int:visit_id> | 1 | manager.py |
| manager.reports | GET | /reports | 1 | manager.py |
| manager.reports_center | GET | /reports-center | 1 | manager.py |
| manager.seed_pricing | POST | /seed-pricing | 0 | manager.py |
| manager.self_service | GET | /self-service | 1 | manager.py |
| manager.settlements | GET | /settlements | 1 | manager.py |
| manager.settlements_export | GET | /settlements/export | 1 | manager.py |
| manager.staff | GET | /staff | 0 | manager.py |
| manager.staff_absence | GET,POST | /staff/absence | 2 | manager.py |
| manager.staff_capacity | GET | /staff/capacity | 1 | manager.py |
| manager.staff_schedule | GET,POST | /staff/schedule | 3 | manager.py |
| manager.unit_control | GET | /unit-control | 0 | manager.py |
| manager.update_service_api | PUT | /api/pricing/services/<int:id> | 0 | manager.py |
| manager.user_management | GET | /user-management | 0 | manager.py |

#### medication

| الاندبوينت | الطرق | المسارات | القوالب | الملف |
|---|---|---|---|---|
| medication.add_medication | GET,POST | /add | 2 | medication_routes.py |
| medication.api_external_drug_import | POST | /api/external-drug-import | 0 | medication_routes.py |
| medication.api_external_drug_search | GET | /api/external-drug-search | 0 | medication_routes.py |
| medication.api_prescriptions | GET | /api/prescriptions | 0 | medication_routes.py |
| medication.approve_supply_request | POST | /supply-requests/<int:request_id>/approve | 1 | medication_routes.py |
| medication.consumption_report | GET | /consumption-report | 1 | medication_routes.py |
| medication.create_supply_request | GET,POST | /supply-requests/create | 2 | medication_routes.py |
| medication.dashboard | GET | /dashboard | 4 | medication_routes.py |
| medication.dispense_prescription | POST | /prescriptions/dispense/<int:prescription_id> | 0 | medication_routes.py |
| medication.edit_medication | GET,POST | /edit/<int:medication_id> | 2 | medication_routes.py |
| medication.fulfill_supply_request | POST | /supply-requests/<int:request_id>/fulfill | 1 | medication_routes.py |
| medication.index | GET | / | 0 | medication_routes.py |
| medication.interactions | GET,POST | /interactions | 1 | medication_routes.py |
| medication.list_medications | GET | /list | 4 | medication_routes.py |
| medication.prescriptions | GET | /prescriptions | 0 | medication_routes.py |
| medication.stock_alerts | GET | /stock-alerts | 3 | medication_routes.py |
| medication.supply_requests | GET | /supply-requests | 3 | medication_routes.py |
| medication.toggle_interaction | POST | /interactions/<int:interaction_id>/toggle | 0 | medication_routes.py |
| medication.view_supply_request | GET | /supply-requests/<int:request_id> | 1 | medication_routes.py |

#### nurse

| الاندبوينت | الطرق | المسارات | القوالب | الملف |
|---|---|---|---|---|
| nurse.administer_medication | POST | /administer-medication/<int:prescription_item_id> | 1 | nurse_routes.py |
| nurse.api_nursing_protocols | GET,POST | /api/protocols | 0 | nurse_routes.py |
| nurse.create_task | POST | /tasks/create | 1 | nurse_routes.py |
| nurse.dashboard | GET | /dashboard | 7 | nurse_routes.py |
| nurse.index | GET | / | 0 | nurse_routes.py |
| nurse.medication_administration | GET | /medication-administration | 1 | nurse_routes.py |
| nurse.medications | GET | /medications | 2 | nurse_routes.py |
| nurse.patient_care | GET | /patient-care | 2 | nurse_routes.py |
| nurse.patient_monitoring | GET | /patient-monitoring | 1 | nurse_routes.py |
| nurse.patients | GET | /patients | 1 | nurse_routes.py |
| nurse.record_vital_signs | POST | /record-vital-signs/<int:patient_id> | 1 | nurse_routes.py |
| nurse.reports | GET | /reports | 1 | nurse_routes.py |
| nurse.tasks | GET | /tasks | 2 | nurse_routes.py |
| nurse.update_task_status | POST | /tasks/<int:task_id>/status | 1 | nurse_routes.py |
| nurse.vital_signs | GET | /vital-signs | 4 | nurse_routes.py |
| nurse.vitals | GET | /vitals | 0 | nurse_routes.py |
| nurse.wards | GET | /wards | 0 | nurse_routes.py |

#### radiology

| الاندبوينت | الطرق | المسارات | القوالب | الملف |
|---|---|---|---|---|
| radiology.add_scan_post | POST | /tests/add | 1 | radiology.py |
| radiology.api_ai_assist | POST | /api/ai-assist | 1 | radiology.py |
| radiology.api_fhir_imaging_study | GET | /api/fhir/imagingstudy/<int:result_id> | 0 | radiology.py |
| radiology.api_fhir_radiology_diagnostic_report | GET | /api/fhir/diagnosticreport/radiology/<int:result_id> | 0 | radiology.py |
| radiology.api_fhir_radiology_observation | GET | /api/fhir/observation/radiology/<int:result_id> | 0 | radiology.py |
| radiology.api_report_macros | GET | /api/report-macros | 1 | radiology.py |
| radiology.api_report_templates | GET | /api/report-templates | 1 | radiology.py |
| radiology.api_worklist | GET | /api/worklist | 0 | radiology.py |
| radiology.dashboard | GET | /dashboard | 5 | radiology.py |
| radiology.delete_report_macro | POST | /api/report-macros/<string:macro_id>/delete | 1 | radiology.py |
| radiology.delete_report_template | POST | /api/report-templates/<string:template_id>/delete | 1 | radiology.py |
| radiology.download_file | GET | /files/<int:file_id> | 1 | radiology.py |
| radiology.images | GET | /images | 0 | radiology.py |
| radiology.index | GET | / | 0 | radiology.py |
| radiology.print_report | GET | /print_report/<int:radiology_scan_id> | 2 | radiology.py |
| radiology.quality | GET | /quality | 1 | radiology.py |
| radiology.reports | GET | /reports | 2 | radiology.py |
| radiology.requests | GET | /requests | 2 | radiology.py |
| radiology.results | GET | /results | 0 | radiology.py |
| radiology.second_review_result | POST | /results/<int:result_id>/second-review | 0 | radiology.py |
| radiology.tests | GET | /tests | 1 | radiology.py |
| radiology.upsert_report_macro | POST | /api/report-macros | 1 | radiology.py |
| radiology.upsert_report_template | POST | /api/report-templates | 1 | radiology.py |
| radiology.worklist | GET | /worklist | 5 | radiology.py |
| radiology.worklist_claim | POST | /worklist/claim/<int:request_id> | 1 | radiology.py |
| radiology.worklist_complete | POST | /worklist/complete/<int:request_id> | 1 | radiology.py |
| radiology.worklist_request | GET | /worklist/request/<int:request_id> | 2 | radiology.py |

#### reception

| الاندبوينت | الطرق | المسارات | القوالب | الملف |
|---|---|---|---|---|
| reception.add_patient | GET,POST | /add_patient | 1 | reception.py |
| reception.add_patient_to_queue | GET,POST | /queue/add-patient | 1 | reception.py |
| reception.api_available_times | GET | /api/available-times | 0 | reception.py |
| reception.api_department_services | GET | /api/department-services | 0 | reception.py |
| reception.api_department_staff | GET | /api/department-staff | 0 | reception.py |
| reception.api_display_calls | GET | /api/display/calls | 1 | reception.py |
| reception.api_display_waiting | GET | /api/display/waiting | 1 | reception.py |
| reception.api_doctors | GET | /api/doctors | 0 | reception.py |
| reception.api_fhir_appointment | GET | /api/fhir/appointment/<int:appointment_id> | 0 | reception.py |
| reception.api_fhir_encounter | GET | /api/fhir/encounter/<int:visit_id> | 0 | reception.py |
| reception.api_fhir_organization | GET | /api/fhir/organization/<int:department_id> | 0 | reception.py |
| reception.api_fhir_patient | GET | /api/fhir/patient/<int:patient_id> | 0 | reception.py |
| reception.api_fhir_practitioner | GET | /api/fhir/practitioner/<int:user_id> | 0 | reception.py |
| reception.api_patient_queue_position | GET | /api/patient-queue-position/<int:patient_id>/<int:department_id> | 0 | reception.py |
| reception.api_queue_snapshot | GET | /api/queue-snapshot | 1 | reception.py |
| reception.api_queue_status | GET | /api/queue-status/<int:department_id> | 0 | reception.py |
| reception.api_queue_status_all | GET | /api/queue-status-all | 0 | reception.py |
| reception.api_queue_wait_metrics | GET | /api/queue-wait-metrics | 0 | reception.py |
| reception.api_smart_patient_search | GET | /api/smart-patient-search | 0 | reception.py |
| reception.api_visit_pricing | GET | /api/visit-pricing | 0 | reception.py |
| reception.appointments | GET | /appointments | 4 | reception.py |
| reception.approve_emergency_debt | POST | /queue/approve-emergency-debt/<int:ticket_id> | 0 | reception.py |
| reception.approve_force_entry | POST | /queue/approve-force-entry/<int:ticket_id> | 0 | reception.py |
| reception.archive_visit | POST | /visits/<int:visit_id>/archive | 1 | reception.py |
| reception.call_next_patient | GET | /queue/call-next/<int:department_id> | 0 | reception.py |
| reception.calls_display | GET | /display/calls | 1 | reception.py |
| reception.cancel_appointment | POST | /appointments/<int:appointment_id>/cancel | 0 | reception.py |
| reception.cancel_ticket | POST | /queue/cancel-ticket/<int:ticket_id> | 0 | reception.py |
| reception.checkin_appointment | POST | /appointments/<int:appointment_id>/checkin | 2 | reception.py |
| reception.checkin_online_booking | POST | /online-bookings/checkin | 1 | reception.py |
| reception.complete_treatment | GET | /queue/complete-treatment/<int:ticket_id> | 0 | reception.py |
| reception.confirm_appointment | POST | /appointments/<int:appointment_id>/confirm | 0 | reception.py |
| reception.create_appointment | GET,POST | /create_appointment | 5 | reception.py |
| reception.create_visit | GET,POST | /visits/create | 4 | reception.py |
| reception.dashboard | GET | /dashboard | 2 | reception.py |
| reception.delete_patient | POST | /delete_patient/<int:patient_id> | 1 | reception.py |
| reception.edit_appointment | GET,POST | /edit_appointment/<int:appointment_id> | 3 | reception.py |
| reception.edit_patient | GET,POST | /edit_patient/<int:patient_id> | 1 | reception.py |
| reception.end_visit | POST | /visits/<int:visit_id>/end | 0 | reception.py |
| reception.export_visits | GET | /export/visits | 0 | reception.py |
| reception.follow_ups | GET | /follow-ups | 1 | reception.py |
| reception.index | GET | / | 0 | reception.py |
| reception.no_show_appointment | POST | /appointments/<int:appointment_id>/no-show | 0 | reception.py |
| reception.patients | GET | /patients | 4 | reception.py |
| reception.payments | GET | /payments | 0 | reception.py |
| reception.pos_charge | POST | /api/pos/charge | 0 | reception.py |
| reception.print_invoice | GET | /print_invoice/<int:invoice_id> | 0 | reception.py |
| reception.print_prescription | GET | /print_prescription/<int:prescription_id> | 0 | reception.py |
| reception.print_receipt | GET | /print_receipt/<int:visit_id> | 3 | reception.py |
| reception.process_payment | POST | /process_payment/<int:visit_id> | 1 | reception.py |
| reception.queue_management | GET | /queue | 4 | reception.py |
| reception.reception_staff_absence | GET,POST | /staff/absence | 1 | reception.py |
| reception.reception_staff_schedule | GET,POST | /staff/schedule | 2 | reception.py |
| reception.return_to_queue | POST | /queue/return-to-queue/<int:ticket_id> | 0 | reception.py |
| reception.save_queue_settings | POST | /queue/save-settings/<int:department_id> | 0 | reception.py |
| reception.skip_patient | POST | /queue/skip-patient/<int:ticket_id> | 0 | reception.py |
| reception.start_treatment | GET | /queue/start-treatment/<int:ticket_id> | 0 | reception.py |
| reception.survey | GET,POST | /survey/<token> | 0 | reception.py |
| reception.transfer_visit | POST | /visits/<int:visit_id>/transfer | 0 | reception.py |
| reception.view_appointment | GET | /view_appointment/<int:appointment_id> | 2 | reception.py |
| reception.view_patient | GET | /view_patient/<int:patient_id> | 9 | reception.py |
| reception.view_visit | GET | /view_visit/<int:visit_id> | 0 | reception.py |
| reception.visits | GET | /visits | 4 | reception.py |
| reception.waiting_display | GET | /display/waiting | 1 | reception.py |

#### super_admin

| الاندبوينت | الطرق | المسارات | القوالب | الملف |
|---|---|---|---|---|
| super_admin.activate_department | POST | /activate-department/<int:department_id> | 0 | super_admin.py |
| super_admin.activate_service | POST | /activate-service/<int:service_id> | 0 | super_admin.py |
| super_admin.add_staff_to_department | POST | /department-staff/<int:department_id>/add | 0 | super_admin.py |
| super_admin.analytics | GET | /analytics | 1 | super_admin.py |
| super_admin.api_ai_assistant | POST | /api/ai-assistant | 0 | super_admin.py |
| super_admin.api_audit_log | POST | /api/audit-log | 0 | super_admin.py |
| super_admin.api_recent_activities | GET | /api/recent-activities | 0 | super_admin.py |
| super_admin.audit_trail | GET | /audit-trail | 2 | super_admin.py |
| super_admin.backup | GET | /backup | 0 | super_admin.py |
| super_admin.backup_history | GET | /backup/history | 0 | super_admin.py |
| super_admin.backup_report | GET | /backup/report | 0 | super_admin.py |
| super_admin.backup_schedule | GET,POST | /backup/schedule | 0 | super_admin.py |
| super_admin.ban_user | GET | /users/ban/<int:user_id> | 1 | super_admin.py |
| super_admin.branch_templates | GET,POST | /branch-templates | 2 | super_admin.py |
| super_admin.branding | GET | /branding | 0 | super_admin.py |
| super_admin.cancel_backup | POST | /backup/cancel/<int:backup_id> | 0 | super_admin.py |
| super_admin.create_backup | POST | /backup/create | 0 | super_admin.py |
| super_admin.create_department | POST | /departments/create | 0 | super_admin.py |
| super_admin.create_permission | POST | /permissions/create | 1 | super_admin.py |
| super_admin.create_permission_simple | POST | /create-permission-simple | 0 | super_admin.py |
| super_admin.create_role | GET,POST | /roles/create | 1 | super_admin.py |
| super_admin.create_role_simple | POST | /create-role-simple | 0 | super_admin.py |
| super_admin.create_service | POST | /services/create | 0 | super_admin.py |
| super_admin.create_user | GET,POST | /users/create | 1 | super_admin.py |
| super_admin.dashboard | GET | /dashboard | 11 | super_admin.py |
| super_admin.data_warehouse | GET | /data-warehouse | 1 | super_admin.py |
| super_admin.data_warehouse_export | GET | /data-warehouse/export | 1 | super_admin.py |
| super_admin.deactivate_department | POST | /deactivate-department/<int:department_id> | 0 | super_admin.py |
| super_admin.deactivate_service | POST | /deactivate-service/<int:service_id> | 0 | super_admin.py |
| super_admin.delete_backup | POST | /backup/delete/<int:backup_id> | 0 | super_admin.py |
| super_admin.delete_permission | POST | /permissions/<int:permission_id>/delete | 0 | super_admin.py |
| super_admin.delete_role | POST | /roles/<int:role_id>/delete | 0 | super_admin.py |
| super_admin.delete_user | POST | /users/<int:user_id>/delete | 0 | super_admin.py |
| super_admin.department_staff | GET | /department-staff/<int:department_id> | 1 | super_admin.py |
| super_admin.departments | GET | /departments | 3 | super_admin.py |
| super_admin.download_export | GET | /download-export/<filename> | 0 | super_admin.py |
| super_admin.edit_department | GET,POST | /edit-department/<int:department_id> | 1 | super_admin.py |
| super_admin.edit_permission | POST | /permissions/<int:permission_id>/edit | 0 | super_admin.py |
| super_admin.edit_role | GET,POST | /roles/<int:role_id>/edit | 1 | super_admin.py |
| super_admin.edit_service | GET,POST | /edit-service/<int:service_id> | 2 | super_admin.py |
| super_admin.edit_user | GET,POST | /users/<int:user_id>/edit | 1 | super_admin.py |
| super_admin.export_backup_logs | GET | /backup/export-logs | 0 | super_admin.py |
| super_admin.export_departments | GET | /export-departments | 0 | super_admin.py |
| super_admin.export_services | GET | /export-services | 0 | super_admin.py |
| super_admin.export_system_data | POST | /export-data | 0 | super_admin.py |
| super_admin.force_logout_user | GET | /users/force-logout/<int:user_id> | 1 | super_admin.py |
| super_admin.init_notification_templates | POST | /system/notifications/init-templates | 1 | super_admin.py |
| super_admin.maintenance_automation | GET,POST | /maintenance/automation | 2 | super_admin.py |
| super_admin.manage_role_department_permissions | GET,POST | /roles/<int:role_id>/department-permissions | 0 | super_admin.py |
| super_admin.manage_role_permissions | GET,POST | /roles/<int:role_id>/permissions | 1 | super_admin.py |
| super_admin.performance | GET | /performance | 0 | super_admin.py |
| super_admin.permissions | GET | /permissions | 2 | super_admin.py |
| super_admin.permissions_matrix | GET,POST | /permissions-matrix | 1 | super_admin.py |
| super_admin.pricing | GET | /pricing | 0 | super_admin.py |
| super_admin.queue_settings | GET,POST | /queue-settings | 3 | super_admin.py |
| super_admin.remove_staff_from_department | POST | /department-staff/<int:department_id>/remove | 0 | super_admin.py |
| super_admin.reports | GET | /reports | 1 | super_admin.py |
| super_admin.reset_user_password | POST | /users/<int:user_id>/reset-password | 0 | super_admin.py |
| super_admin.restore_backup | POST | /backup/restore/<int:backup_id> | 0 | super_admin.py |
| super_admin.roles | GET | /roles | 6 | super_admin.py |
| super_admin.run_notifications | POST | /system/notifications/run | 1 | super_admin.py |
| super_admin.save_backup_settings | POST | /backup/settings | 0 | super_admin.py |
| super_admin.security_center | GET | /security-center | 1 | super_admin.py |
| super_admin.security_logs | GET | /security-logs | 2 | super_admin.py |
| super_admin.seed_users | POST | /seed/users | 1 | super_admin.py |
| super_admin.service_pricing | GET,POST | /service-pricing/<int:service_id> | 1 | super_admin.py |
| super_admin.services | GET | /services | 4 | super_admin.py |
| super_admin.system | GET | /system | 0 | super_admin.py |
| super_admin.system_backup | GET | /system-backup | 2 | super_admin.py |
| super_admin.system_cleanup | POST | /system/cleanup | 1 | super_admin.py |
| super_admin.system_config | GET,POST | /system-config | 2 | super_admin.py |
| super_admin.system_maintenance | GET | /system/maintenance | 0 | super_admin.py |
| super_admin.system_monitor | GET | /system-monitor | 2 | super_admin.py |
| super_admin.unban_user | GET | /users/unban/<int:user_id> | 1 | super_admin.py |
| super_admin.update_branding | POST | /branding/update | 1 | super_admin.py |
| super_admin.users | GET | /users | 4 | super_admin.py |
| super_admin.view_department | GET | /department/<int:department_id> | 2 | super_admin.py |
| super_admin.view_service | GET | /service/<int:service_id> | 1 | super_admin.py |

### قائمة استخدام الاندبوينتس في القوالب
- accountant.api_erp_export: 1
- accountant.daily_audit_report: 1
- accountant.dashboard: 9
- accountant.debt_tracking_report: 2
- accountant.export_audit_report: 3
- accountant.financial: 2
- accountant.payments: 1
- auth.login: 4
- auth.logout: 3
- auth.profile: 6
- backup.create_backup: 3
- backup.dashboard: 2
- backup.delete_backup: 2
- backup.download_backup: 3
- backup.list_backups: 1
- backup.restore_backup: 2
- booking.api_available_doctors: 2
- booking.api_available_times: 2
- booking.api_smart_slots: 1
- booking.cancel_booking: 1
- booking.confirmation: 1
- booking.create_booking: 2
- booking.dashboard_portal: 2
- booking.index: 5
- booking.payment: 2
- booking.register: 1
- doctor.api_dashboard_layout: 1
- doctor.api_note_templates: 1
- doctor.api_patient_search: 1
- doctor.appointments: 1
- doctor.dashboard: 6
- doctor.dashboard_for_doctor: 1
- doctor.delete_note_template: 1
- doctor.diagnosis: 1
- doctor.end_treatment: 2
- doctor.lab_request: 2
- doctor.medical_history: 4
- doctor.notes: 4
- doctor.patient_details: 3
- doctor.patient_queue: 5
- doctor.patient_timeline: 3
- doctor.patients: 3
- doctor.prescription: 2
- doctor.prescriptions: 2
- doctor.prescriptions_history: 3
- doctor.print_prescription: 3
- doctor.radiology_request: 2
- doctor.save_visit_summary: 1
- doctor.start_treatment: 2
- doctor.upsert_note_template: 1
- doctor.visit_summary: 1
- emergency.complete_visit: 1
- emergency.convert_emergency_case: 3
- emergency.dashboard: 4
- emergency.edit_emergency_case: 3
- emergency.emergency_treatment: 2
- emergency.emergency_visits: 4
- emergency.end_treatment: 2
- emergency.lab_request: 1
- emergency.list_emergency_cases: 3
- emergency.medical_history: 2
- emergency.patient_details: 1
- emergency.patient_queue: 5
- emergency.prescription: 2
- emergency.prescriptions_history: 1
- emergency.radiology_request: 2
- emergency.reports: 2
- emergency.resolve_emergency_case: 4
- emergency.start_treatment: 2
- emergency.treatment: 2
- emergency.triage: 3
- emergency.triage_list: 1
- emergency.view_emergency_case: 2
- finance.audit: 2
- finance.capture_slow_queries_weekly: 1
- finance.dashboard: 2
- finance.invoices: 1
- finance.payments: 2
- finance.slow_queries: 2
- finance.slow_queries_weekly: 2
- finance.slow_queries_weekly_detail: 1
- lab.add_reagent: 1
- lab.dashboard: 7
- lab.edit_reagent: 1
- lab.print_request: 4
- lab.quality: 2
- lab.quality_control: 2
- lab.reagents: 2
- lab.reports: 1
- lab.requests: 1
- lab.results: 1
- lab.tests: 1
- lab.worklist: 4
- lab.worklist_claim: 1
- lab.worklist_request: 1
- main.about_system: 1
- main.dashboard: 3
- main.privacy_policy: 1
- main.technical_support: 1
- main.terms_of_use: 1
- manager.api_what_if: 1
- manager.approve_force_payment: 1
- manager.dashboard: 3
- manager.kpi_dashboard: 2
- manager.monitoring: 3
- manager.pricing: 1
- manager.reject_force_payment: 1
- manager.reports: 1
- manager.reports_center: 1
- manager.self_service: 1
- manager.settlements: 1
- manager.settlements_export: 1
- manager.staff_absence: 2
- manager.staff_capacity: 1
- manager.staff_schedule: 3
- medication.add_medication: 2
- medication.approve_supply_request: 1
- medication.consumption_report: 1
- medication.create_supply_request: 2
- medication.dashboard: 4
- medication.edit_medication: 2
- medication.fulfill_supply_request: 1
- medication.interactions: 1
- medication.list_medications: 4
- medication.stock_alerts: 3
- medication.supply_requests: 3
- medication.view_supply_request: 1
- nurse.administer_medication: 1
- nurse.create_task: 1
- nurse.dashboard: 7
- nurse.medication_administration: 1
- nurse.medications: 2
- nurse.patient_care: 2
- nurse.patient_monitoring: 1
- nurse.patients: 1
- nurse.record_vital_signs: 1
- nurse.reports: 1
- nurse.tasks: 2
- nurse.update_task_status: 1
- nurse.vital_signs: 4
- payment.dashboard: 1
- payment.process_payment: 2
- radiology.add_scan_post: 1
- radiology.api_ai_assist: 1
- radiology.api_report_macros: 1
- radiology.api_report_templates: 1
- radiology.dashboard: 5
- radiology.delete_report_macro: 1
- radiology.delete_report_template: 1
- radiology.download_file: 1
- radiology.print_report: 2
- radiology.quality: 1
- radiology.reports: 2
- radiology.requests: 2
- radiology.tests: 1
- radiology.upsert_report_macro: 1
- radiology.upsert_report_template: 1
- radiology.worklist: 5
- radiology.worklist_claim: 1
- radiology.worklist_complete: 1
- radiology.worklist_request: 2
- reception.add_patient: 1
- reception.add_patient_to_queue: 1
- reception.api_display_calls: 1
- reception.api_display_waiting: 1
- reception.api_queue_snapshot: 1
- reception.appointments: 4
- reception.archive_visit: 1
- reception.calls_display: 1
- reception.checkin_appointment: 2
- reception.checkin_online_booking: 1
- reception.create_appointment: 5
- reception.create_visit: 4
- reception.dashboard: 2
- reception.delete_patient: 1
- reception.edit_appointment: 3
- reception.edit_patient: 1
- reception.follow_ups: 1
- reception.patients: 4
- reception.print_receipt: 3
- reception.process_payment: 1
- reception.queue_management: 4
- reception.reception_staff_absence: 1
- reception.reception_staff_schedule: 2
- reception.view_appointment: 2
- reception.view_patient: 9
- reception.visits: 4
- reception.waiting_display: 1
- static: 5
- super_admin.analytics: 1
- super_admin.audit_trail: 2
- super_admin.ban_user: 1
- super_admin.branch_templates: 2
- super_admin.create_permission: 1
- super_admin.create_role: 1
- super_admin.create_user: 1
- super_admin.dashboard: 11
- super_admin.data_warehouse: 1
- super_admin.data_warehouse_export: 1
- super_admin.department_staff: 1
- super_admin.departments: 3
- super_admin.edit_department: 1
- super_admin.edit_role: 1
- super_admin.edit_service: 2
- super_admin.edit_user: 1
- super_admin.force_logout_user: 1
- super_admin.init_notification_templates: 1
- super_admin.maintenance_automation: 2
- super_admin.manage_role_permissions: 1
- super_admin.permissions: 2
- super_admin.permissions_matrix: 1
- super_admin.queue_settings: 3
- super_admin.reports: 1
- super_admin.roles: 6
- super_admin.run_notifications: 1
- super_admin.security_center: 1
- super_admin.security_logs: 2
- super_admin.seed_users: 1
- super_admin.service_pricing: 1
- super_admin.services: 4
- super_admin.system_backup: 2
- super_admin.system_cleanup: 1
- super_admin.system_config: 2
- super_admin.system_monitor: 2
- super_admin.unban_user: 1
- super_admin.update_branding: 1
- super_admin.users: 4
- super_admin.view_department: 2
- super_admin.view_service: 1
