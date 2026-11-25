# جرد صفحات النظام وروابطه

إجمالي المسارات المسجّلة: **967** — منها **697** مسار GET (صفحات/واجهات قابلة للفتح).

المصدر: `route_inventory.json` المولّد من التطبيق الحيّ، مع تصنيف المسار إلى وحدة منتج ودور مستخدم عبر `app/core/module_route_map.py`.

## توزيع المسارات حسب الدور

| الدور | إجمالي المسارات | صفحات GET |
|---|---:|---:|
| `accountant` | 69 | 54 |
| `any` | 164 | 123 |
| `doctor` | 79 | 64 |
| `emergency` | 32 | 25 |
| `lab` | 53 | 39 |
| `manager` | 59 | 42 |
| `nurse` | 44 | 32 |
| `patient` | 15 | 15 |
| `pharmacist` | 55 | 44 |
| `radiology` | 34 | 25 |
| `reception` | 109 | 78 |
| `super_admin` | 251 | 154 |
| `technician` | 3 | 2 |

## توزيع المسارات حسب الوحدة

| الوحدة | المسارات |
|---|---:|
| `owner` | 184 |
| `reception` | 84 |
| `doctor` | 76 |
| `billing` | 69 |
| `integration` | 59 |
| `reporting` | 59 |
| `pharmacy` | 55 |
| `lab` | 53 |
| `uncategorized:compliance` | 50 |
| `nursing` | 44 |
| `radiology` | 34 |
| `emergency` | 32 |
| `appointments` | 25 |
| `portal` | 15 |
| `uncategorized:main` | 13 |
| `uncategorized:device_integration` | 12 |
| `uncategorized:auth` | 10 |
| `uncategorized:specialty_forms` | 8 |
| `uncategorized:backup` | 7 |
| `uncategorized:insurance` | 6 |
| `uncategorized:saas_billing` | 5 |
| `uncategorized:biometric` | 5 |
| `uncategorized:mfa` | 5 |
| `uncategorized:procurement` | 5 |
| `uncategorized:handover` | 4 |
| `uncategorized:security` | 4 |
| `ai_imaging` | 3 |
| `inventory` | 3 |
| `uncategorized:hl7` | 3 |
| `uncategorized:ihe` | 3 |
| `uncategorized:api_lab` | 2 |
| `uncategorized:api_radiology` | 2 |
| `uncategorized:saas` | 2 |
| `uncategorized:kiosk` | 2 |
| `uncategorized:pwa` | 2 |
| `uncategorized:__health` | 1 |
| `uncategorized:_ghost_whoami` | 1 |
| `uncategorized:api_dashboard` | 1 |
| `uncategorized:api_search` | 1 |
| `uncategorized:api_user` | 1 |
| `uncategorized:backup_restore` | 1 |
| `uncategorized:favicon` | 1 |
| `uncategorized:health` | 1 |
| `uncategorized:inbox` | 1 |
| `uncategorized:monitoring` | 1 |
| `uncategorized:_root_patients` | 1 |
| `uncategorized:static` | 1 |
| `uncategorized:check_g_trace` | 1 |
| `uncategorized:trigger_idem_error` | 1 |
| `uncategorized:trigger_idem_error_html` | 1 |
| `uncategorized:log_something` | 1 |
| `uncategorized:trigger_module_error` | 1 |
| `uncategorized:trigger_module_error_html` | 1 |
| `uncategorized:trigger_perm_error` | 1 |
| `uncategorized:trigger_tenant_ctx_error` | 1 |
| `uncategorized:trigger_tenant_iso_error` | 1 |
| `uncategorized:_root_visits` | 1 |

## قائمة الصفحات التفصيلية

الرموز: `GET` صفحة/واجهة، `POST` إجراء، `API` واجهة JSON، `page` واجهة HTML.

### الدور: `accountant` (54 صفحة)

| الوحدة | المسار | Endpoint | النوع |
|---|---|---|---|
| `billing` | `/accountant/` | `accountant.index` | page |
| `billing` | `/accountant/accounts` | `accountant.accounts` | page |
| `billing` | `/accountant/accounts/<int:account_id>` | `accountant.account_ledger` | page |
| `billing` | `/accountant/api/erp/export` | `accountant.api_erp_export` | API |
| `billing` | `/accountant/audit/daily` | `accountant.daily_audit_report` | page |
| `billing` | `/accountant/audit/debts` | `accountant.debt_tracking_report` | page |
| `billing` | `/accountant/audit/export/<report_type>` | `accountant.export_audit_report` | page |
| `billing` | `/accountant/audit/monthly` | `accountant.monthly_audit_report` | page |
| `billing` | `/accountant/daily-summary` | `accountant.daily_summary` | page |
| `billing` | `/accountant/dashboard` | `accountant.dashboard` | page |
| `billing` | `/accountant/financial` | `accountant.financial` | page |
| `billing` | `/accountant/financial-report` | `accountant.financial_report` | page |
| `billing` | `/accountant/invoices` | `accountant.invoices` | page |
| `billing` | `/accountant/journals` | `accountant.journals` | page |
| `billing` | `/accountant/open-invoices` | `accountant.open_invoices` | page |
| `billing` | `/accountant/patient-accounts` | `accountant.patient_accounts` | page |
| `billing` | `/accountant/payment-documentation/<int:payment_id>` | `accountant.payment_documentation` | page |
| `billing` | `/accountant/payments` | `accountant.payments` | page |
| `billing` | `/accountant/receipt/<int:payment_id>` | `accountant.receipt` | page |
| `billing` | `/accountant/refunds` | `accountant.refund_requests` | page |
| `billing` | `/accountant/reports` | `accountant.reports` | page |
| `billing` | `/accountant/trial-balance` | `accountant.trial_balance` | page |
| `billing` | `/finance/` | `finance.index` | page |
| `billing` | `/finance/audit` | `finance.audit` | page |
| `billing` | `/finance/billing-summary` | `finance.billing_summary` | page |
| `billing` | `/finance/billing/payment-plans` | `finance.payment_plans` | page |
| `billing` | `/finance/billing/summary` | `finance.billing_summary` | page |
| `billing` | `/finance/claims/status` | `finance.finance_insurance_claims` | page |
| `billing` | `/finance/dashboard` | `finance.dashboard` | page |
| `billing` | `/finance/insurance-claims` | `finance.finance_insurance_claims` | page |
| `billing` | `/finance/insurance-claims/<int:claim_id>/status` | `finance.finance_insurance_claim_status` | page |
| `billing` | `/finance/insurance/claims` | `finance.finance_insurance_claims` | page |
| `billing` | `/finance/insurance/claims/<int:claim_id>/status` | `finance.finance_insurance_claim_status` | page |
| `billing` | `/finance/invoice/<int:invoice_id>/pdf` | `finance.invoice_pdf` | page |
| `billing` | `/finance/invoices` | `finance.invoices` | page |
| `billing` | `/finance/invoices/<int:invoice_id>/download` | `finance.invoice_pdf` | page |
| `billing` | `/finance/invoices/<int:invoice_id>/pdf` | `finance.invoice_pdf` | page |
| `billing` | `/finance/payment-plans` | `finance.payment_plans` | page |
| `billing` | `/finance/payment-plans/<int:plan_id>` | `finance.get_payment_plan` | page |
| `billing` | `/finance/payment_plans` | `finance.payment_plans` | page |
| `billing` | `/finance/payment_plans/<int:plan_id>` | `finance.get_payment_plan` | page |
| `billing` | `/finance/payments` | `finance.payments` | page |
| `billing` | `/finance/slow-queries` | `finance.slow_queries` | page |
| `billing` | `/finance/slow-queries/weekly` | `finance.slow_queries_weekly` | page |
| `billing` | `/finance/slow-queries/weekly/<int:report_id>` | `finance.slow_queries_weekly_detail` | page |
| `billing` | `/finance/summary` | `finance.billing_summary` | page |
| `billing` | `/payment/` | `payment.index` | page |
| `billing` | `/payment/api/insurance/claims/<int:claim_id>` | `payment.get_insurance_claim` | API |
| `billing` | `/payment/api/pos/prescriptions/<int:prescription_id>/lookup` | `payment.lookup_prescription_for_pos` | API |
| `billing` | `/payment/dashboard` | `payment.dashboard` | page |
| `billing` | `/payment/history` | `payment.payment_history` | page |
| `billing` | `/payment/methods` | `payment.payment_methods` | page |
| `billing` | `/payment/process/<int:visit_id>` | `payment.process_payment` | page |
| `billing` | `/payment/reports` | `payment.payment_reports` | page |

### الدور: `any` (123 صفحة)

| الوحدة | المسار | Endpoint | النوع |
|---|---|---|---|
| `uncategorized:main` | `/` | `main.index` | page |
| `uncategorized:__health` | `/__health` | `__health` | page |
| `uncategorized:_ghost_whoami` | `/_ghost_whoami` | `_ghost_whoami` | page |
| `uncategorized:main` | `/about-system` | `main.about_system` | page |
| `uncategorized:insurance` | `/api/claims` | `insurance.list_claims` | API |
| `uncategorized:api_dashboard` | `/api/dashboard/snapshot` | `api_dashboard.dashboard_snapshot` | API |
| `uncategorized:main` | `/api/search` | `main.api_search` | API |
| `uncategorized:api_search` | `/api/search/patients` | `api_search.search_patients` | API |
| `uncategorized:main` | `/api/tenants/search` | `main.api_search_tenants` | API |
| `uncategorized:api_user` | `/api/user/preferences` | `api_user.user_preferences` | API |
| `uncategorized:main` | `/appointments` | `main.appointments_redirect` | page |
| `uncategorized:auth` | `/auth/api/tenants-list` | `auth.api_tenants_list` | API |
| `uncategorized:auth` | `/auth/forgot-password` | `auth.forgot_password` | page |
| `uncategorized:auth` | `/auth/login` | `auth.login` | page |
| `uncategorized:auth` | `/auth/logout` | `auth.logout` | page |
| `uncategorized:auth` | `/auth/profile` | `auth.profile` | page |
| `uncategorized:auth` | `/auth/register` | `auth.register` | page |
| `uncategorized:auth` | `/auth/reset-password/<token>/<int:user_id>` | `auth.reset_password` | page |
| `uncategorized:biometric` | `/biometric/` | `biometric.status` | page |
| `uncategorized:compliance` | `/compliance/access-control` | `compliance.access_control_review` | page |
| `uncategorized:compliance` | `/compliance/access-control-review` | `compliance.access_control` | page |
| `uncategorized:compliance` | `/compliance/access-control-review` | `compliance.access_control_review` | page |
| `uncategorized:compliance` | `/compliance/access-control-review` | `compliance.review_access_control` | page |
| `uncategorized:compliance` | `/compliance/access_control_review` | `compliance.access_control_review` | page |
| `uncategorized:compliance` | `/compliance/audit-log-retention` | `compliance.audit_log_retention` | page |
| `uncategorized:compliance` | `/compliance/audit-log-retention` | `compliance.audit_log_retention_check` | page |
| `uncategorized:compliance` | `/compliance/audit-log-retention` | `compliance.audit_retention` | page |
| `uncategorized:compliance` | `/compliance/audit-log-retention` | `compliance.audit_retention_check` | page |
| `uncategorized:compliance` | `/compliance/audit-log-retention-check` | `compliance.audit_log_retention_check` | page |
| `uncategorized:compliance` | `/compliance/audit-retention` | `compliance.audit_log_retention_check` | page |
| `uncategorized:compliance` | `/compliance/audit-retention-check` | `compliance.audit_log_retention_check` | page |
| `uncategorized:compliance` | `/compliance/audit-summary` | `compliance.audit_summary` | page |
| `uncategorized:compliance` | `/compliance/audit_retention` | `compliance.audit_log_retention_check` | page |
| `uncategorized:compliance` | `/compliance/breach-check` | `compliance.breach_check` | page |
| `uncategorized:compliance` | `/compliance/consent-management` | `compliance.consent_management_verification` | page |
| `uncategorized:compliance` | `/compliance/consent-management-verification` | `compliance.consent_management_verification` | page |
| `uncategorized:compliance` | `/compliance/consent-verification` | `compliance.consent_management_verification` | page |
| `uncategorized:compliance` | `/compliance/consent-verification` | `compliance.consent_verification` | page |
| `uncategorized:compliance` | `/compliance/consent-verification` | `compliance.verify_consent` | page |
| `uncategorized:compliance` | `/compliance/consent-verification` | `compliance.verify_consent_management` | page |
| `uncategorized:compliance` | `/compliance/consent_management_verification` | `compliance.consent_management_verification` | page |
| `uncategorized:compliance` | `/compliance/data-export` | `compliance.data_export` | page |
| `uncategorized:compliance` | `/compliance/data-export` | `compliance.export_data` | page |
| `uncategorized:compliance` | `/compliance/data-export` | `compliance.export_patient_data` | page |
| `uncategorized:compliance` | `/compliance/data-export` | `compliance.patient_data_export` | page |
| `uncategorized:compliance` | `/compliance/data-export/<int:patient_id>` | `compliance.data_export` | page |
| `uncategorized:compliance` | `/compliance/data-retention` | `compliance.data_retention` | page |
| `uncategorized:compliance` | `/compliance/data_export` | `compliance.data_export` | page |
| `uncategorized:compliance` | `/compliance/encryption-at-rest` | `compliance.encryption_at_rest` | page |
| `uncategorized:compliance` | `/compliance/encryption-at-rest` | `compliance.encryption_at_rest_verification` | page |
| `uncategorized:compliance` | `/compliance/encryption-at-rest` | `compliance.encryption_verification` | page |
| `uncategorized:compliance` | `/compliance/encryption-at-rest` | `compliance.verify_encryption_at_rest` | page |
| `uncategorized:compliance` | `/compliance/encryption-at-rest-verification` | `compliance.encryption_at_rest_verification` | page |
| `uncategorized:compliance` | `/compliance/encryption-verification` | `compliance.encryption_at_rest_verification` | page |
| `uncategorized:compliance` | `/compliance/encryption_at_rest` | `compliance.encryption_at_rest_verification` | page |
| `uncategorized:compliance` | `/compliance/encryption_at_rest_verification` | `compliance.encryption_at_rest_verification` | page |
| `uncategorized:compliance` | `/compliance/export-patient-data` | `compliance.data_export` | page |
| `uncategorized:compliance` | `/compliance/patient-data-export` | `compliance.data_export` | page |
| `uncategorized:compliance` | `/compliance/soc2/cc1-control-environment` | `compliance.soc2_cc1_control_environment` | page |
| `uncategorized:compliance` | `/compliance/soc2/cc2-communication` | `compliance.soc2_cc2_communication` | page |
| `uncategorized:compliance` | `/compliance/soc2/cc3-risk-assessment` | `compliance.soc2_cc3_risk_assessment` | page |
| `uncategorized:compliance` | `/compliance/soc2/cc4-monitoring` | `compliance.soc2_cc4_monitoring` | page |
| `uncategorized:compliance` | `/compliance/soc2/cc5-control-activities` | `compliance.soc2_cc5_control_activities` | page |
| `uncategorized:compliance` | `/compliance/soc2/cc6-logical-access` | `compliance.soc2_cc6_logical_access` | page |
| `uncategorized:compliance` | `/compliance/soc2/cc7-system-operations` | `compliance.soc2_cc7_system_operations` | page |
| `uncategorized:compliance` | `/compliance/soc2/cc8-change-management` | `compliance.soc2_cc8_change_management` | page |
| `uncategorized:compliance` | `/compliance/soc2/cc9-risk-mitigation` | `compliance.soc2_cc9_risk_mitigation` | page |
| `uncategorized:compliance` | `/compliance/soc2/score` | `compliance.soc2_score` | page |
| `uncategorized:compliance` | `/compliance/verify-consent` | `compliance.consent_management_verification` | page |
| `uncategorized:main` | `/dashboard` | `main.dashboard` | page |
| `uncategorized:device_integration` | `/device-integration/iot/alerts` | `device_integration.iot_alerts` | page |
| `uncategorized:device_integration` | `/device-integration/iot/devices` | `device_integration.iot_list_devices` | page |
| `uncategorized:device_integration` | `/device-integration/iot/devices/<device_id>/status` | `device_integration.iot_device_status` | page |
| `uncategorized:device_integration` | `/device-integration/mdi/alarms` | `device_integration.mdi_alarms` | page |
| `uncategorized:device_integration` | `/device-integration/mdi/dashboard` | `device_integration.mdi_dashboard` | page |
| `uncategorized:device_integration` | `/device-integration/mdi/devices` | `device_integration.mdi_list_devices` | page |
| `uncategorized:favicon` | `/favicon.ico` | `favicon` | page |
| `uncategorized:handover` | `/handover/` | `handover.handover_dashboard` | page |
| `uncategorized:health` | `/health` | `health` | page |
| `uncategorized:main` | `/health` | `main.health` | page |
| `uncategorized:hl7` | `/hl7/status` | `hl7.hl7_status` | page |
| `uncategorized:ihe` | `/ihe/pdq/query` | `ihe.pdq_query` | page |
| `uncategorized:ihe` | `/ihe/pix/query` | `ihe.pix_query` | page |
| `uncategorized:inbox` | `/inbox` | `inbox.dashboard` | page |
| `uncategorized:kiosk` | `/kiosk/check-in` | `kiosk.check_in` | page |
| `uncategorized:monitoring` | `/metrics` | `monitoring.metrics` | page |
| `uncategorized:mfa` | `/mfa/setup` | `mfa.setup` | page |
| `uncategorized:mfa` | `/mfa/status` | `mfa.status` | page |
| `uncategorized:mfa` | `/mfa/verify` | `mfa.verify` | page |
| `uncategorized:main` | `/package-restricted` | `main.package_restricted` | page |
| `uncategorized:_root_patients` | `/patients` | `_root_patients` | page |
| `uncategorized:main` | `/privacy-policy` | `main.privacy_policy` | page |
| `uncategorized:procurement` | `/procurement/` | `procurement.list_purchases` | page |
| `uncategorized:procurement` | `/procurement/new` | `procurement.new_po_form` | page |
| `uncategorized:procurement` | `/procurement/supplier/<int:supplier_id>/summary` | `procurement.supplier_summary` | page |
| `uncategorized:pwa` | `/pwa/manifest.webmanifest` | `pwa.manifest` | page |
| `uncategorized:pwa` | `/pwa/offline` | `pwa.offline` | page |
| `uncategorized:saas` | `/saas/signup` | `saas.signup_organization` | page |
| `uncategorized:security` | `/security/password-policy` | `security.password_policy` | page |
| `uncategorized:security` | `/security/sessions` | `security.sessions` | page |
| `uncategorized:security` | `/security/signatures` | `security.signatures` | page |
| `uncategorized:main` | `/set-language/<lang_code>` | `main.set_language` | page |
| `uncategorized:main` | `/settings` | `main.settings` | page |
| `uncategorized:specialty_forms` | `/specialty-forms` | `specialty_forms.list_forms` | page |
| `uncategorized:specialty_forms` | `/specialty-forms/<int:form_id>` | `specialty_forms.view_form` | page |
| `uncategorized:specialty_forms` | `/specialty-forms/<int:form_id>/fill` | `specialty_forms.fill_form` | page |
| `uncategorized:specialty_forms` | `/specialty-forms/<int:form_id>/submissions` | `specialty_forms.list_submissions` | page |
| `uncategorized:specialty_forms` | `/specialty-forms/<int:form_id>/versions/<int:version_id>/edit` | `specialty_forms.edit_version` | page |
| `uncategorized:specialty_forms` | `/specialty-forms/new` | `specialty_forms.new_form` | page |
| `uncategorized:specialty_forms` | `/specialty-forms/submissions/<int:submission_id>` | `specialty_forms.view_submission` | page |
| `uncategorized:static` | `/static/<path:filename>` | `static` | page |
| `uncategorized:main` | `/technical-support` | `main.technical_support` | page |
| `uncategorized:main` | `/terms-of-use` | `main.terms_of_use` | page |
| `uncategorized:check_g_trace` | `/test/g-trace` | `check_g_trace` | page |
| `uncategorized:trigger_idem_error` | `/test/idempotency-error` | `trigger_idem_error` | page |
| `uncategorized:trigger_idem_error_html` | `/test/idempotency-error-html` | `trigger_idem_error_html` | page |
| `uncategorized:log_something` | `/test/log-trace` | `log_something` | page |
| `uncategorized:trigger_module_error` | `/test/module-error` | `trigger_module_error` | page |
| `uncategorized:trigger_module_error_html` | `/test/module-error-html` | `trigger_module_error_html` | page |
| `uncategorized:trigger_perm_error` | `/test/perm-error` | `trigger_perm_error` | page |
| `uncategorized:trigger_tenant_ctx_error` | `/test/tenant-ctx-error` | `trigger_tenant_ctx_error` | page |
| `uncategorized:trigger_tenant_iso_error` | `/test/tenant-iso-error` | `trigger_tenant_iso_error` | page |
| `uncategorized:_root_visits` | `/visits` | `_root_visits` | page |

### الدور: `doctor` (64 صفحة)

| الوحدة | المسار | Endpoint | النوع |
|---|---|---|---|
| `ai_imaging` | `/ai-imaging/` | `ai_imaging.index` | page |
| `doctor` | `/cds/alerts` | `cds.alerts` | page |
| `doctor` | `/cds/patient/<int:patient_id>/alerts` | `cds.patient_alerts` | page |
| `doctor` | `/cds/rules` | `cds.rules` | page |
| `doctor` | `/clinical-coding/api/cpt/search` | `clinical_coding.api_cpt_search` | API |
| `doctor` | `/clinical-coding/api/icd10/search` | `clinical_coding.api_icd10_search` | API |
| `doctor` | `/clinical-coding/cpt` | `clinical_coding.cpt_list` | page |
| `doctor` | `/clinical-coding/drg` | `clinical_coding.drg_list` | page |
| `doctor` | `/clinical-coding/icd10` | `clinical_coding.icd10_list` | page |
| `doctor` | `/clinical-coding/icd10/<int:id>` | `clinical_coding.icd10_detail` | page |
| `doctor` | `/clinical-coding/patient/<int:patient_id>/diagnoses` | `clinical_coding.patient_diagnoses` | page |
| `doctor` | `/clinical-coding/patient/<int:patient_id>/procedures` | `clinical_coding.patient_procedures` | page |
| `doctor` | `/doctor/` | `doctor.index` | page |
| `doctor` | `/doctor/api/dashboard-layout` | `doctor.api_dashboard_layout` | API |
| `doctor` | `/doctor/api/dashboard-stats` | `doctor.api_dashboard_stats` | API |
| `doctor` | `/doctor/api/note-templates` | `doctor.api_note_templates` | API |
| `doctor` | `/doctor/api/patient-search` | `doctor.api_patient_search` | API |
| `doctor` | `/doctor/api/today-visits` | `doctor.api_today_visits` | API |
| `doctor` | `/doctor/appointments` | `doctor.appointments` | page |
| `doctor` | `/doctor/dashboard` | `doctor.dashboard` | page |
| `doctor` | `/doctor/dashboard-new` | `doctor.dashboard_new` | page |
| `doctor` | `/doctor/dashboard/<int:doctor_id>` | `doctor.dashboard_for_doctor` | page |
| `doctor` | `/doctor/dental-chart/<int:patient_id>` | `doctor.dental_chart` | page |
| `doctor` | `/doctor/diagnosis/<int:visit_id>` | `doctor.diagnosis` | page |
| `doctor` | `/doctor/lab-request/<int:visit_id>` | `doctor.lab_request` | page |
| `doctor` | `/doctor/lab-requests` | `doctor.lab_requests` | page |
| `doctor` | `/doctor/lab-results/<int:patient_id>` | `doctor.lab_results` | page |
| `doctor` | `/doctor/medical-history/<int:patient_id>` | `doctor.medical_history` | page |
| `doctor` | `/doctor/medical-records` | `doctor.medical_records` | page |
| `doctor` | `/doctor/notes/<int:visit_id>` | `doctor.notes` | page |
| `doctor` | `/doctor/patient-details/<int:visit_id>` | `doctor.patient_details` | page |
| `doctor` | `/doctor/patient-queue` | `doctor.patient_queue` | page |
| `doctor` | `/doctor/patient-timeline/<int:patient_id>` | `doctor.patient_timeline` | page |
| `doctor` | `/doctor/patients` | `doctor.patients` | page |
| `doctor` | `/doctor/prescription/<int:visit_id>` | `doctor.prescription` | page |
| `doctor` | `/doctor/prescriptions` | `doctor.prescriptions` | page |
| `doctor` | `/doctor/prescriptions-history/<int:patient_id>` | `doctor.prescriptions_history` | page |
| `doctor` | `/doctor/print-invoice/<int:invoice_id>` | `doctor.print_invoice` | page |
| `doctor` | `/doctor/print-medical-report/<int:visit_id>` | `doctor.print_medical_report` | page |
| `doctor` | `/doctor/print-prescription/<int:prescription_id>` | `doctor.print_prescription` | page |
| `doctor` | `/doctor/download-prescription-pdf/<int:prescription_id>` | `doctor.download_prescription_pdf` | page |
| `doctor` | `/doctor/print-receipt/<int:visit_id>` | `doctor.print_receipt` | page |
| `doctor` | `/doctor/radiology-request/<int:visit_id>` | `doctor.radiology_request` | page |
| `doctor` | `/doctor/radiology-requests` | `doctor.radiology_requests` | page |
| `doctor` | `/doctor/radiology-results/<int:patient_id>` | `doctor.radiology_results` | page |
| `doctor` | `/doctor/view_patient/<int:visit_id>` | `doctor.view_patient` | page |
| `doctor` | `/doctor/visit-summary/<int:visit_id>` | `doctor.visit_summary` | page |
| `doctor` | `/doctor/visits` | `doctor.visits` | page |
| `doctor` | `/pathway/pathway/<int:pathway_id>` | `pathway.pathway_detail` | page |
| `doctor` | `/pathway/pathways` | `pathway.pathways` | page |
| `doctor` | `/pathway/patient/<int:patient_id>/care-plans` | `pathway.patient_care_plans` | page |
| `doctor` | `/patient-education/` | `patient_education.index` | page |
| `doctor` | `/patient-education/edit/<int:material_id>` | `patient_education.edit_material` | page |
| `doctor` | `/patient-education/material/<int:material_id>` | `patient_education.view_material` | page |
| `doctor` | `/patient-education/new` | `patient_education.new_material` | page |
| `doctor` | `/patient-education/patient/<int:patient_id>` | `patient_education.patient_materials` | page |
| `doctor` | `/referral/detail/<int:referral_id>` | `referral.detail` | page |
| `doctor` | `/referral/list` | `referral.list_referrals` | page |
| `doctor` | `/telemedicine/` | `telemedicine.index` | page |
| `doctor` | `/telemedicine/<int:tm_id>` | `telemedicine.view_appointment` | page |
| `doctor` | `/telemedicine/consult/<int:consultation_id>` | `telemedicine.consult_room` | page |
| `doctor` | `/telemedicine/new` | `telemedicine.new_appointment` | page |
| `doctor` | `/vaccination/patient/<int:patient_id>` | `vaccination.patient_immunizations` | page |
| `doctor` | `/vaccination/vaccines` | `vaccination.vaccines` | page |

### الدور: `emergency` (25 صفحة)

| الوحدة | المسار | Endpoint | النوع |
|---|---|---|---|
| `emergency` | `/emergency/` | `emergency.index` | page |
| `emergency` | `/emergency/cases` | `emergency.list_emergency_cases` | page |
| `emergency` | `/emergency/cases/<int:id>` | `emergency.view_emergency_case` | page |
| `emergency` | `/emergency/cases/<int:id>/edit` | `emergency.edit_emergency_case` | page |
| `emergency` | `/emergency/dashboard` | `emergency.dashboard` | page |
| `emergency` | `/emergency/emergency-report/<int:emergency_id>` | `emergency.emergency_report` | page |
| `emergency` | `/emergency/emergency-treatment/<int:visit_id>` | `emergency.emergency_treatment` | page |
| `emergency` | `/emergency/emergency-visits` | `emergency.emergency_visits` | page |
| `emergency` | `/emergency/lab-request/<int:emergency_id>` | `emergency.lab_request` | page |
| `emergency` | `/emergency/lab-results/<int:patient_id>` | `emergency.lab_results` | page |
| `emergency` | `/emergency/medical-history/<int:patient_id>` | `emergency.medical_history` | page |
| `emergency` | `/emergency/patient-details/<int:emergency_id>` | `emergency.patient_details` | page |
| `emergency` | `/emergency/patient-queue` | `emergency.patient_queue` | page |
| `emergency` | `/emergency/patients` | `emergency.patients` | page |
| `emergency` | `/emergency/prescription/<int:emergency_id>` | `emergency.prescription` | page |
| `emergency` | `/emergency/prescriptions-history/<int:patient_id>` | `emergency.prescriptions_history` | page |
| `emergency` | `/emergency/print-emergency-report/<int:emergency_id>` | `emergency.print_emergency_report` | page |
| `emergency` | `/emergency/print-prescription/<int:prescription_id>` | `emergency.print_prescription` | page |
| `emergency` | `/emergency/queue` | `emergency.queue` | page |
| `emergency` | `/emergency/radiology-request/<int:emergency_id>` | `emergency.radiology_request` | page |
| `emergency` | `/emergency/radiology-results/<int:patient_id>` | `emergency.radiology_results` | page |
| `emergency` | `/emergency/reports` | `emergency.reports` | page |
| `emergency` | `/emergency/treatment/<int:emergency_id>` | `emergency.treatment` | page |
| `emergency` | `/emergency/triage` | `emergency.triage_list` | page |
| `emergency` | `/emergency/triage/<int:emergency_id>` | `emergency.triage` | page |

### الدور: `lab` (39 صفحة)

| الوحدة | المسار | Endpoint | النوع |
|---|---|---|---|
| `lab` | `/lab/` | `lab.index` | page |
| `lab` | `/lab/api/critical-alerts` | `lab.critical_value_alerts` | API |
| `lab` | `/lab/api/critical-values` | `lab.critical_value_alerts` | API |
| `lab` | `/lab/api/derived-values` | `lab.derived_values` | API |
| `lab` | `/lab/api/fhir/diagnosticreport/lab/<int:result_id>` | `lab.api_fhir_lab_diagnostic_report` | API |
| `lab` | `/lab/api/fhir/observation/lab/<int:result_id>` | `lab.api_fhir_lab_observation` | API |
| `lab` | `/lab/api/result-templates` | `lab.result_templates` | API |
| `lab` | `/lab/api/results/<int:result_id>/history` | `lab.result_history` | API |
| `lab` | `/lab/api/test-catalog` | `lab.api_test_catalog` | API |
| `lab` | `/lab/api/test-catalog/<int:id>` | `lab.api_test_catalog_item` | API |
| `lab` | `/lab/api/worklist` | `lab.api_worklist` | API |
| `lab` | `/lab/auto-calculate` | `lab.derived_values` | page |
| `lab` | `/lab/barcode/print/<int:request_id>` | `lab.barcode_print` | page |
| `lab` | `/lab/barcode/scan/<barcode>` | `lab.barcode_scan` | page |
| `lab` | `/lab/calculate` | `lab.derived_values` | page |
| `lab` | `/lab/critical-alerts` | `lab.critical_value_alerts` | page |
| `lab` | `/lab/critical-values` | `lab.critical_value_alerts` | page |
| `lab` | `/lab/dashboard` | `lab.dashboard` | page |
| `lab` | `/lab/derived-values` | `lab.derived_values` | page |
| `lab` | `/lab/print_request/<int:id>` | `lab.print_request` | page |
| `lab` | `/lab/print_request/<int:id>/pdf` | `lab.print_request_pdf` | page |
| `lab` | `/lab/quality` | `lab.quality` | page |
| `lab` | `/lab/quality-control` | `lab.quality_control` | page |
| `lab` | `/lab/reagents` | `lab.reagents` | page |
| `lab` | `/lab/reagents/<int:reagent_id>/edit` | `lab.edit_reagent` | page |
| `lab` | `/lab/reagents/add` | `lab.add_reagent` | page |
| `lab` | `/lab/reports` | `lab.reports` | page |
| `lab` | `/lab/requests` | `lab.requests` | page |
| `lab` | `/lab/result-history/<int:result_id>` | `lab.result_history` | page |
| `lab` | `/lab/result-templates` | `lab.result_templates` | page |
| `lab` | `/lab/result-templates/<int:template_id>` | `lab.result_template_detail` | page |
| `lab` | `/lab/results` | `lab.results` | page |
| `lab` | `/lab/results/<int:result_id>/history` | `lab.result_history` | page |
| `lab` | `/lab/templates` | `lab.result_templates` | page |
| `lab` | `/lab/test-catalog/` | `lab.test_catalog` | page |
| `lab` | `/lab/test-panels/` | `lab.test_panels` | page |
| `lab` | `/lab/tests` | `lab.tests` | page |
| `lab` | `/lab/worklist` | `lab.worklist` | page |
| `lab` | `/lab/worklist/request/<int:request_id>` | `lab.worklist_request` | page |

### الدور: `manager` (42 صفحة)

| الوحدة | المسار | Endpoint | النوع |
|---|---|---|---|
| `reporting` | `/data-warehouse/` | `data_warehouse.dashboard` | page |
| `reporting` | `/manager/analytics` | `manager.analytics` | page |
| `reporting` | `/manager/api/pricing/services` | `manager.get_services_api` | API |
| `reporting` | `/manager/branding` | `manager.manager_branding` | page |
| `reporting` | `/manager/branding/preview` | `manager.manager_branding_preview` | page |
| `reporting` | `/manager/budget` | `manager.budget_dashboard` | page |
| `reporting` | `/manager/custom-service-approvals` | `manager.custom_service_approvals` | page |
| `reporting` | `/manager/dashboard` | `manager.dashboard` | page |
| `reporting` | `/manager/departments` | `manager.departments` | page |
| `reporting` | `/manager/drill-down/<report_type>` | `manager.drill_down` | page |
| `reporting` | `/manager/exchange-rates` | `manager.exchange_rates` | page |
| `reporting` | `/manager/financial-reports` | `manager.financial_reports` | page |
| `reporting` | `/manager/force-payment-approvals` | `manager.force_payment_approvals` | page |
| `reporting` | `/manager/kpi-dashboard` | `manager.kpi_dashboard` | page |
| `reporting` | `/manager/monthly-comparison` | `manager.monthly_comparison` | page |
| `reporting` | `/manager/patient-satisfaction` | `manager.patient_satisfaction_dashboard` | page |
| `reporting` | `/manager/pricing` | `manager.pricing` | page |
| `reporting` | `/manager/reports` | `manager.reports` | page |
| `reporting` | `/manager/reports-center` | `manager.reports_center` | page |
| `reporting` | `/manager/self-service` | `manager.self_service` | page |
| `reporting` | `/manager/settings` | `manager.manager_settings` | page |
| `reporting` | `/manager/settlements` | `manager.settlements` | page |
| `reporting` | `/manager/settlements/export` | `manager.settlements_export` | page |
| `reporting` | `/manager/staff` | `manager.staff` | page |
| `reporting` | `/manager/staff/absence` | `manager.staff_absence` | page |
| `reporting` | `/manager/staff/capacity` | `manager.staff_capacity` | page |
| `reporting` | `/manager/staff/schedule` | `manager.staff_schedule` | page |
| `reporting` | `/manager/unit-control` | `manager.unit_control` | page |
| `reporting` | `/manager/user-management` | `manager.user_management` | page |
| `reporting` | `/population-health/dashboard` | `pop_health.dashboard` | page |
| `reporting` | `/population-health/disease-registry` | `pop_health.disease_registry` | page |
| `reporting` | `/population-health/quality-measures` | `pop_health.quality_measures` | page |
| `reporting` | `/quality/api/quality-metrics` | `quality.api_quality_metrics` | API |
| `reporting` | `/quality/audits` | `quality.audits` | page |
| `reporting` | `/quality/dashboard` | `quality.dashboard` | page |
| `reporting` | `/quality/incidents` | `quality.incidents` | page |
| `reporting` | `/report-builder/` | `report_builder.builder` | page |
| `reporting` | `/report-builder/templates` | `report_builder.templates_list` | page |
| `reporting` | `/report-builder/templates/<int:template_id>` | `report_builder.templates_get` | page |
| `reporting` | `/what-if/` | `what_if.index` | page |
| `reporting` | `/what-if/<int:scenario_id>` | `what_if.view_scenario` | page |
| `reporting` | `/what-if/new` | `what_if.new_scenario` | page |

### الدور: `nurse` (32 صفحة)

| الوحدة | المسار | Endpoint | النوع |
|---|---|---|---|
| `nursing` | `/bed/admission/<int:admission_id>` | `bed.admission_detail` | page |
| `nursing` | `/bed/admissions` | `bed.admissions` | page |
| `nursing` | `/bed/api/available-beds` | `bed.api_available_beds` | API |
| `nursing` | `/bed/api/bed-status` | `bed.api_bed_status` | API |
| `nursing` | `/bed/dashboard` | `bed.dashboard` | page |
| `nursing` | `/bed/room/<int:room_id>` | `bed.room_detail` | page |
| `nursing` | `/bed/ward/<int:ward_id>` | `bed.ward_detail` | page |
| `nursing` | `/bed/wards` | `bed.wards` | page |
| `nursing` | `/emar/dashboard` | `emar.dashboard` | page |
| `nursing` | `/emar/patient/<int:patient_id>` | `emar.patient_mar` | page |
| `nursing` | `/nurse/` | `nurse.index` | page |
| `nursing` | `/nurse/api/protocols` | `nurse.api_nursing_protocols` | API |
| `nursing` | `/nurse/dashboard` | `nurse.dashboard` | page |
| `nursing` | `/nurse/medication-administration` | `nurse.medication_administration` | page |
| `nursing` | `/nurse/medications` | `nurse.medications` | page |
| `nursing` | `/nurse/patient-care` | `nurse.patient_care` | page |
| `nursing` | `/nurse/patient-monitoring` | `nurse.patient_monitoring` | page |
| `nursing` | `/nurse/patients` | `nurse.patients` | page |
| `nursing` | `/nurse/reports` | `nurse.reports` | page |
| `nursing` | `/nurse/tasks` | `nurse.tasks` | page |
| `nursing` | `/nurse/vital-signs` | `nurse.vital_signs` | page |
| `nursing` | `/nurse/vitals` | `nurse.vitals` | page |
| `nursing` | `/nurse/wards` | `nurse.wards` | page |
| `nursing` | `/nursing-assessment/dashboard` | `nursing_assessment.dashboard` | page |
| `nursing` | `/nursing-assessment/new/<int:patient_id>` | `nursing_assessment.new_assessment` | page |
| `nursing` | `/nursing-assessment/patient/<int:patient_id>` | `nursing_assessment.patient_assessments` | page |
| `nursing` | `/nursing-assessment/view/<int:assessment_id>` | `nursing_assessment.view_assessment` | page |
| `nursing` | `/or/schedule` | `or.schedule` | page |
| `nursing` | `/or/surgery/<int:surgery_id>` | `or.surgery_detail` | page |
| `nursing` | `/order-sets/` | `order_set.index` | page |
| `nursing` | `/order-sets/<int:set_id>` | `order_set.detail` | page |
| `nursing` | `/order-sets/api/list` | `order_set.api_list` | API |

### الدور: `patient` (15 صفحة)

| الوحدة | المسار | Endpoint | النوع |
|---|---|---|---|
| `portal` | `/portal/` | `portal.index` | page |
| `portal` | `/portal/appointments` | `portal.appointments` | page |
| `portal` | `/portal/bills` | `portal.bills` | page |
| `portal` | `/portal/book-appointment` | `portal.book_appointment` | page |
| `portal` | `/portal/dashboard` | `portal.dashboard` | page |
| `portal` | `/portal/documents` | `portal.documents` | page |
| `portal` | `/portal/documents/<int:file_id>` | `portal.download_document` | page |
| `portal` | `/portal/feedback` | `portal.feedback` | page |
| `portal` | `/portal/lab-results` | `portal.lab_results` | page |
| `portal` | `/portal/link-account` | `portal.link_account` | page |
| `portal` | `/portal/medical-records` | `portal.medical_records` | page |
| `portal` | `/portal/prescriptions` | `portal.prescriptions` | page |
| `portal` | `/portal/radiology-results` | `portal.radiology_results` | page |
| `portal` | `/portal/settings` | `portal.settings` | page |
| `portal` | `/portal/vaccinations` | `portal.vaccinations` | page |

### الدور: `pharmacist` (44 صفحة)

| الوحدة | المسار | Endpoint | النوع |
|---|---|---|---|
| `pharmacy` | `/medication/` | `medication.index` | page |
| `pharmacy` | `/medication/add` | `medication.add_medication` | page |
| `pharmacy` | `/medication/api/expiry` | `medication.expiry_tracking` | API |
| `pharmacy` | `/medication/api/external-drug-search` | `medication.api_external_drug_search` | API |
| `pharmacy` | `/medication/api/interactions/check` | `medication.check_drug_interactions` | API |
| `pharmacy` | `/medication/api/medications/search` | `medication.api_medications_search` | API |
| `pharmacy` | `/medication/api/prescription-refills` | `medication.list_prescription_refills` | API |
| `pharmacy` | `/medication/api/prescriptions` | `medication.api_prescriptions` | API |
| `pharmacy` | `/medication/api/refills` | `medication.list_prescription_refills` | API |
| `pharmacy` | `/medication/api/stock/alerts` | `medication.stock_alerts_api` | API |
| `pharmacy` | `/medication/consumption-report` | `medication.consumption_report` | page |
| `pharmacy` | `/medication/dashboard` | `medication.dashboard` | page |
| `pharmacy` | `/medication/edit/<int:medication_id>` | `medication.edit_medication` | page |
| `pharmacy` | `/medication/expiries` | `medication.expiry_tracking` | page |
| `pharmacy` | `/medication/expiry` | `medication.expiry_tracking` | page |
| `pharmacy` | `/medication/expiry-tracking` | `medication.expiry_tracking` | page |
| `pharmacy` | `/medication/interactions` | `medication.interactions` | page |
| `pharmacy` | `/medication/interactions/check` | `medication.check_drug_interactions` | page |
| `pharmacy` | `/medication/interactions/check/<int:medication_a_id>/<int:medication_b_id>` | `medication.check_drug_interactions` | page |
| `pharmacy` | `/medication/list` | `medication.list_medications` | page |
| `pharmacy` | `/medication/pos` | `medication.pos` | page |
| `pharmacy` | `/medication/prescription-refills` | `medication.list_prescription_refills` | page |
| `pharmacy` | `/medication/prescriptions` | `medication.prescriptions` | page |
| `pharmacy` | `/medication/purchases` | `medication.purchases` | page |
| `pharmacy` | `/medication/purchases/add` | `medication.add_purchase` | page |
| `pharmacy` | `/medication/refills` | `medication.list_prescription_refills` | page |
| `pharmacy` | `/medication/refills/<int:refill_id>/status` | `medication.update_refill_status` | page |
| `pharmacy` | `/medication/sales-history` | `medication.sales_history` | page |
| `pharmacy` | `/medication/sales/<int:sale_id>` | `medication.sale_detail` | page |
| `pharmacy` | `/medication/sales/<int:sale_id>/print` | `medication.print_sale_receipt` | page |
| `pharmacy` | `/medication/sales/<int:sale_id>/receipt` | `medication.sale_receipt` | page |
| `pharmacy` | `/medication/sales/api/list` | `medication.api_sales_list` | API |
| `pharmacy` | `/medication/sales/api/report` | `medication.api_sales_report` | API |
| `pharmacy` | `/medication/sales/api/totals` | `medication.api_sales_totals` | API |
| `pharmacy` | `/medication/stock-alerts` | `medication.stock_alerts` | page |
| `pharmacy` | `/medication/stock-alerts/api` | `medication.stock_alerts_api` | page |
| `pharmacy` | `/medication/stock/alerts` | `medication.stock_alerts_api` | page |
| `pharmacy` | `/medication/suppliers` | `medication.suppliers` | page |
| `pharmacy` | `/medication/suppliers/<int:supplier_id>/edit` | `medication.edit_supplier` | page |
| `pharmacy` | `/medication/suppliers/add` | `medication.add_supplier` | page |
| `pharmacy` | `/medication/supply-requests` | `medication.supply_requests` | page |
| `pharmacy` | `/medication/supply-requests/<int:request_id>` | `medication.view_supply_request` | page |
| `pharmacy` | `/medication/supply-requests/create` | `medication.create_supply_request` | page |
| `pharmacy` | `/medications` | `_root_medications` | page |

### الدور: `radiology` (25 صفحة)

| الوحدة | المسار | Endpoint | النوع |
|---|---|---|---|
| `radiology` | `/dicom/api/studies/patient/<int:patient_id>` | `dicom.api_patient_studies` | API |
| `radiology` | `/dicom/api/worklist` | `dicom.api_worklist` | API |
| `radiology` | `/dicom/api/worklist/patient/<int:patient_id>` | `dicom.api_worklist_patient` | API |
| `radiology` | `/dicom/studies` | `dicom.studies` | page |
| `radiology` | `/dicom/study/<int:study_id>` | `dicom.study_detail` | page |
| `radiology` | `/dicom/viewer/<int:study_id>` | `dicom.viewer` | page |
| `radiology` | `/radiology/` | `radiology.index` | page |
| `radiology` | `/radiology/api/fhir/diagnosticreport/radiology/<int:result_id>` | `radiology.api_fhir_radiology_diagnostic_report` | API |
| `radiology` | `/radiology/api/fhir/imagingstudy/<int:result_id>` | `radiology.api_fhir_imaging_study` | API |
| `radiology` | `/radiology/api/fhir/observation/radiology/<int:result_id>` | `radiology.api_fhir_radiology_observation` | API |
| `radiology` | `/radiology/api/report-macros` | `radiology.api_report_macros` | API |
| `radiology` | `/radiology/api/report-templates` | `radiology.api_report_templates` | API |
| `radiology` | `/radiology/api/worklist` | `radiology.api_worklist` | API |
| `radiology` | `/radiology/dashboard` | `radiology.dashboard` | page |
| `radiology` | `/radiology/files/<int:file_id>` | `radiology.download_file` | page |
| `radiology` | `/radiology/images` | `radiology.images` | page |
| `radiology` | `/radiology/print_report/<int:radiology_scan_id>` | `radiology.print_report` | page |
| `radiology` | `/radiology/print_report/<int:radiology_scan_id>/pdf` | `radiology.print_report_pdf` | page |
| `radiology` | `/radiology/quality` | `radiology.quality` | page |
| `radiology` | `/radiology/reports` | `radiology.reports` | page |
| `radiology` | `/radiology/requests` | `radiology.requests` | page |
| `radiology` | `/radiology/results` | `radiology.results` | page |
| `radiology` | `/radiology/tests` | `radiology.tests` | page |
| `radiology` | `/radiology/worklist` | `radiology.worklist` | page |
| `radiology` | `/radiology/worklist/request/<int:request_id>` | `radiology.worklist_request` | page |

### الدور: `reception` (78 صفحة)

| الوحدة | المسار | Endpoint | النوع |
|---|---|---|---|
| `appointments` | `/booking/` | `booking.index` | page |
| `appointments` | `/booking/api/available-doctors` | `booking.api_available_doctors` | API |
| `appointments` | `/booking/api/available-times` | `booking.api_available_times` | API |
| `appointments` | `/booking/api/smart-slots` | `booking.api_smart_slots` | API |
| `appointments` | `/booking/appointment-reminders` | `booking.booking_appointment_reminders` | page |
| `appointments` | `/booking/appointments/no-shows` | `booking.booking_no_show_list` | page |
| `appointments` | `/booking/appointments/recurring` | `booking.booking_recurring_appointments` | page |
| `appointments` | `/booking/appointments/reminders` | `booking.booking_appointment_reminders` | page |
| `appointments` | `/booking/appointments/waitlist` | `booking.booking_waitlist_management` | page |
| `appointments` | `/booking/confirmation/<int:booking_id>` | `booking.confirmation` | page |
| `appointments` | `/booking/create` | `booking.create_booking` | page |
| `appointments` | `/booking/dashboard` | `booking.dashboard_portal` | page |
| `appointments` | `/booking/no-shows` | `booking.booking_no_show_list` | page |
| `appointments` | `/booking/payment/<int:booking_id>` | `booking.payment` | page |
| `appointments` | `/booking/recurring-appointments` | `booking.booking_recurring_appointments` | page |
| `appointments` | `/booking/register` | `booking.register` | page |
| `appointments` | `/booking/telemedicine/<int:booking_id>` | `booking.telemedicine_room` | page |
| `appointments` | `/booking/waitlist` | `booking.booking_waitlist_management` | page |
| `reception` | `/reception/` | `reception.index` | page |
| `reception` | `/reception/add_patient` | `reception.add_patient` | page |
| `reception` | `/reception/api/available-times` | `reception.api_available_times` | API |
| `reception` | `/reception/api/check-rate` | `reception_currency.check_rate` | API |
| `reception` | `/reception/api/department-services` | `reception.api_department_services` | API |
| `reception` | `/reception/api/department-staff` | `reception.api_department_staff` | API |
| `reception` | `/reception/api/display/calls` | `reception.api_display_calls` | API |
| `reception` | `/reception/api/display/waiting` | `reception.api_display_waiting` | API |
| `reception` | `/reception/api/doctors` | `reception.api_doctors` | API |
| `reception` | `/reception/api/fhir/appointment/<int:appointment_id>` | `reception.api_fhir_appointment` | API |
| `reception` | `/reception/api/fhir/encounter/<int:visit_id>` | `reception.api_fhir_encounter` | API |
| `reception` | `/reception/api/fhir/organization/<int:department_id>` | `reception.api_fhir_organization` | API |
| `reception` | `/reception/api/fhir/patient/<int:patient_id>` | `reception.api_fhir_patient` | API |
| `reception` | `/reception/api/fhir/practitioner/<int:user_id>` | `reception.api_fhir_practitioner` | API |
| `reception` | `/reception/api/patient-queue-position/<int:patient_id>/<int:department_id>` | `reception.api_patient_queue_position` | API |
| `reception` | `/reception/api/queue-department-status/<int:department_id>` | `reception.api_queue_status` | API |
| `reception` | `/reception/api/queue-snapshot` | `reception.api_queue_snapshot` | API |
| `reception` | `/reception/api/queue-status-all` | `reception.api_queue_status_all` | API |
| `reception` | `/reception/api/queue-status/<int:department_id>` | `reception.get_smart_queue_management` | API |
| `reception` | `/reception/api/queue-wait-metrics` | `reception.api_queue_wait_metrics` | API |
| `reception` | `/reception/api/smart-patient-search` | `reception.api_smart_patient_search` | API |
| `reception` | `/reception/api/visit-pricing` | `reception.api_visit_pricing` | API |
| `reception` | `/reception/appointment-reminders` | `reception.appointment_reminders` | page |
| `reception` | `/reception/appointments` | `reception.appointments` | page |
| `reception` | `/reception/appointments/no-shows` | `reception.no_show_list` | page |
| `reception` | `/reception/appointments/recurring` | `reception.recurring_appointments` | page |
| `reception` | `/reception/appointments/reminders` | `reception.appointment_reminders` | page |
| `reception` | `/reception/appointments/waitlist` | `reception.waitlist_management` | page |
| `reception` | `/reception/cash-register` | `reception.cash_register` | page |
| `reception` | `/reception/create_appointment` | `reception.create_appointment` | page |
| `reception` | `/reception/daily-close` | `reception.daily_close` | page |
| `reception` | `/reception/dashboard` | `reception.dashboard` | page |
| `reception` | `/reception/display/calls` | `reception.calls_display` | page |
| `reception` | `/reception/display/waiting` | `reception.waiting_display` | page |
| `reception` | `/reception/edit_appointment/<int:appointment_id>` | `reception.edit_appointment` | page |
| `reception` | `/reception/edit_patient/<int:patient_id>` | `reception.edit_patient` | page |
| `reception` | `/reception/edit_visit/<int:visit_id>` | `reception.edit_visit` | page |
| `reception` | `/reception/export/visits` | `reception.export_visits` | page |
| `reception` | `/reception/follow-ups` | `reception.follow_ups` | page |
| `reception` | `/reception/no-shows` | `reception.no_show_list` | page |
| `reception` | `/reception/patients` | `reception.patients` | page |
| `reception` | `/reception/payments` | `reception.payments` | page |
| `reception` | `/reception/print_invoice/<int:invoice_id>` | `reception.print_invoice` | page |
| `reception` | `/reception/print_prescription/<int:prescription_id>` | `reception.print_prescription` | page |
| `reception` | `/reception/print_receipt/<int:visit_id>` | `reception.print_receipt` | page |
| `reception` | `/reception/queue` | `reception.queue_management` | page |
| `reception` | `/reception/queue/add-patient` | `reception.add_patient_to_queue` | page |
| `reception` | `/reception/queue/call-next/<int:department_id>` | `reception.call_next_patient` | page |
| `reception` | `/reception/queue/complete-treatment/<int:ticket_id>` | `reception.complete_treatment` | page |
| `reception` | `/reception/queue/start-treatment/<int:ticket_id>` | `reception.start_treatment` | page |
| `reception` | `/reception/recurring-appointments` | `reception.recurring_appointments` | page |
| `reception` | `/reception/staff/absence` | `reception.reception_staff_absence` | page |
| `reception` | `/reception/staff/schedule` | `reception.reception_staff_schedule` | page |
| `reception` | `/reception/survey/<token>` | `reception.survey` | page |
| `reception` | `/reception/view_appointment/<int:appointment_id>` | `reception.view_appointment` | page |
| `reception` | `/reception/view_patient/<int:patient_id>` | `reception.view_patient` | page |
| `reception` | `/reception/view_visit/<int:visit_id>` | `reception.view_visit` | page |
| `reception` | `/reception/visits` | `reception.visits` | page |
| `reception` | `/reception/visits/create` | `reception.create_visit` | page |
| `reception` | `/reception/waitlist` | `reception.waitlist_management` | page |

### الدور: `super_admin` (154 صفحة)

| الوحدة | المسار | Endpoint | النوع |
|---|---|---|---|
| `integration` | `/api/fhir/AllergyIntolerance` | `fhir_ext.fhir_allergies` | API |
| `integration` | `/api/fhir/Appointment` | `fhir_ext.fhir_appointments` | API |
| `integration` | `/api/fhir/AuditEvent` | `fhir_ext2.fhir_audit_events` | API |
| `integration` | `/api/fhir/BodyStructure` | `fhir_ext2.fhir_body_structures` | API |
| `integration` | `/api/fhir/CarePlan` | `fhir_ext.fhir_care_plans` | API |
| `integration` | `/api/fhir/ChargeItem` | `fhir_ext2.fhir_charge_items` | API |
| `integration` | `/api/fhir/Claim` | `fhir_ext2.fhir_claims` | API |
| `integration` | `/api/fhir/Communication` | `fhir_ext.fhir_communications` | API |
| `integration` | `/api/fhir/Condition` | `fhir.fhir_conditions` | API |
| `integration` | `/api/fhir/Consent` | `fhir_ext2.fhir_consents` | API |
| `integration` | `/api/fhir/Coverage` | `fhir_ext.fhir_coverages` | API |
| `integration` | `/api/fhir/Device` | `fhir_ext.fhir_devices` | API |
| `integration` | `/api/fhir/DiagnosticReport` | `fhir_ext.fhir_diagnostic_reports` | API |
| `integration` | `/api/fhir/DocumentReference` | `fhir_ext.fhir_document_references` | API |
| `integration` | `/api/fhir/Encounter` | `fhir.fhir_encounters` | API |
| `integration` | `/api/fhir/Endpoint` | `fhir_ext2.fhir_endpoints` | API |
| `integration` | `/api/fhir/Flag` | `fhir_ext2.fhir_flags` | API |
| `integration` | `/api/fhir/Goal` | `fhir_ext.fhir_goals` | API |
| `integration` | `/api/fhir/Group` | `fhir_ext2.fhir_groups` | API |
| `integration` | `/api/fhir/HealthcareService` | `fhir_ext.fhir_healthcare_services` | API |
| `integration` | `/api/fhir/Immunization` | `fhir_ext.fhir_immunizations` | API |
| `integration` | `/api/fhir/Invoice` | `fhir_ext2.fhir_invoices` | API |
| `integration` | `/api/fhir/List` | `fhir_ext2.fhir_lists` | API |
| `integration` | `/api/fhir/Location` | `fhir_ext2.fhir_locations` | API |
| `integration` | `/api/fhir/Medication` | `fhir_ext2.fhir_medications` | API |
| `integration` | `/api/fhir/MedicationAdministration` | `fhir_ext2.fhir_medication_administrations` | API |
| `integration` | `/api/fhir/MedicationDispense` | `fhir_ext2.fhir_medication_dispenses` | API |
| `integration` | `/api/fhir/MedicationRequest` | `fhir.fhir_medication_requests` | API |
| `integration` | `/api/fhir/MedicationStatement` | `fhir_ext2.fhir_medication_statements` | API |
| `integration` | `/api/fhir/NutritionOrder` | `fhir_ext2.fhir_nutrition_orders` | API |
| `integration` | `/api/fhir/Observation` | `fhir.fhir_observations` | API |
| `integration` | `/api/fhir/OperationOutcome` | `fhir_ext2.fhir_operation_outcome` | API |
| `integration` | `/api/fhir/Organization` | `fhir_ext.fhir_organizations` | API |
| `integration` | `/api/fhir/Patient` | `fhir.fhir_patients` | API |
| `integration` | `/api/fhir/Patient/<int:patient_id>` | `fhir.fhir_patient` | API |
| `integration` | `/api/fhir/Practitioner` | `fhir_ext.fhir_practitioners` | API |
| `integration` | `/api/fhir/Practitioner/<int:pid>` | `fhir_ext.fhir_practitioner` | API |
| `integration` | `/api/fhir/Procedure` | `fhir_ext.fhir_procedures` | API |
| `integration` | `/api/fhir/Provenance` | `fhir_ext2.fhir_provenances` | API |
| `integration` | `/api/fhir/Questionnaire` | `fhir_ext2.fhir_questionnaires` | API |
| `integration` | `/api/fhir/QuestionnaireResponse` | `fhir_ext2.fhir_questionnaire_responses` | API |
| `integration` | `/api/fhir/RelatedPerson` | `fhir_ext.fhir_related_persons` | API |
| `integration` | `/api/fhir/ResearchStudy` | `fhir_ext2.fhir_research_studies` | API |
| `integration` | `/api/fhir/Schedule` | `fhir_ext2.fhir_schedules` | API |
| `integration` | `/api/fhir/ServiceRequest` | `fhir_ext.fhir_service_requests` | API |
| `integration` | `/api/fhir/Specimen` | `fhir_ext.fhir_specimens` | API |
| `integration` | `/api/fhir/Substance` | `fhir_ext2.fhir_substances` | API |
| `integration` | `/api/fhir/Task` | `fhir_ext.fhir_tasks` | API |
| `integration` | `/api/fhir/VisionPrescription` | `fhir_ext2.fhir_vision_prescriptions` | API |
| `integration` | `/api/fhir/metadata` | `fhir_ext.fhir_metadata` | API |
| `integration` | `/api/fhir/metadata` | `fhir_ext2.fhir_metadata` | API |
| `uncategorized:backup_restore` | `/backup-restore/` | `backup_restore.index` | page |
| `uncategorized:backup` | `/backup/backup/dashboard` | `backup.dashboard_legacy` | page |
| `uncategorized:backup` | `/backup/create` | `backup.create_backup` | page |
| `uncategorized:backup` | `/backup/dashboard` | `backup.dashboard` | page |
| `uncategorized:backup` | `/backup/download/<int:backup_id>` | `backup.download_backup` | page |
| `uncategorized:backup` | `/backup/list` | `backup.list_backups` | page |
| `owner` | `/owner/announcements` | `owner.owner_announcements` | page |
| `owner` | `/owner/api-keys` | `owner.owner_api_keys_page` | page |
| `owner` | `/owner/api/assumptions` | `owner.owner_list_assumptions` | API |
| `owner` | `/owner/api/bundles` | `owner.api_list_bundles` | API |
| `owner` | `/owner/api/bundles/<int:bundle_id>` | `owner.api_get_bundle` | API |
| `owner` | `/owner/api/tenants` | `owner.api_tenants` | API |
| `owner` | `/owner/api/tenants/<int:tenant_id>/limits` | `owner.api_tenant_limits` | API |
| `owner` | `/owner/api/tenants/<int:tenant_id>/modules` | `owner.api_tenant_modules` | API |
| `owner` | `/owner/audit-logs` | `owner.owner_audit_logs` | page |
| `owner` | `/owner/backups` | `owner.owner_backups` | page |
| `owner` | `/owner/billing` | `owner.owner_billing` | page |
| `owner` | `/owner/branding` | `owner.owner_branding` | page |
| `owner` | `/owner/bundles` | `owner.owner_bundles` | page |
| `owner` | `/owner/cards-vault` | `owner.owner_cards_vault` | page |
| `owner` | `/owner/company-info` | `owner.owner_company_info` | page |
| `owner` | `/owner/control` | `owner.owner_control` | page |
| `owner` | `/owner/dashboard` | `owner.owner_dashboard` | page |
| `owner` | `/owner/emergency-switches` | `owner.owner_emergency_switches` | page |
| `owner` | `/owner/error-audit-logs` | `owner.owner_error_audit_logs` | page |
| `owner` | `/owner/error-logs` | `owner.owner_error_logs` | page |
| `owner` | `/owner/integrations` | `owner.owner_integrations` | page |
| `owner` | `/owner/modules` | `owner.owner_modules` | page |
| `owner` | `/owner/monitoring` | `owner.owner_monitoring` | page |
| `owner` | `/owner/notifications` | `owner.owner_notifications` | page |
| `owner` | `/owner/packages` | `owner.owner_packages` | page |
| `owner` | `/owner/payment-vault` | `owner.owner_payment_vault` | page |
| `owner` | `/owner/plans` | `owner.owner_plans` | page |
| `owner` | `/owner/provision` | `owner.owner_provision` | page |
| `owner` | `/owner/reports` | `owner.owner_reports` | page |
| `owner` | `/owner/resource-usage` | `owner.owner_resource_usage` | page |
| `owner` | `/owner/subscriptions` | `owner.owner_subscriptions` | page |
| `owner` | `/owner/support-tickets` | `owner.owner_support_tickets` | page |
| `owner` | `/owner/system-config` | `owner.owner_system_config` | page |
| `owner` | `/owner/system-stats` | `owner.owner_system_stats` | page |
| `owner` | `/owner/tasks` | `owner.owner_tasks` | page |
| `owner` | `/owner/tenant-usage/<int:tenant_id>` | `owner.owner_tenant_usage` | page |
| `owner` | `/owner/tenants/` | `owner.owner_tenant_list` | page |
| `owner` | `/owner/tenants/<int:tenant_id>` | `owner.owner_tenant_detail` | page |
| `owner` | `/owner/tenants/create` | `owner.owner_create_tenant` | page |
| `owner` | `/owner/themes` | `owner.owner_themes` | page |
| `owner` | `/owner/users` | `owner.owner_users` | page |
| `owner` | `/owner/users-list` | `owner.owner_users_list` | page |
| `owner` | `/owner/webhooks` | `owner.owner_webhooks` | page |
| `integration` | `/sso/config` | `sso.config` | page |
| `owner` | `/super-admin/analytics` | `super_admin.analytics` | page |
| `owner` | `/super-admin/api/performance` | `super_admin.performance_metrics` | API |
| `owner` | `/super-admin/api/recent-activities` | `super_admin.api_recent_activities` | API |
| `owner` | `/super-admin/api/security-logs` | `super_admin.list_security_logs` | API |
| `owner` | `/super-admin/api/security-logs/summary` | `super_admin.security_summary` | API |
| `owner` | `/super-admin/audit-trail` | `super_admin.audit_trail` | page |
| `owner` | `/super-admin/backup` | `super_admin.backup` | page |
| `owner` | `/super-admin/backup/export-logs` | `super_admin.export_backup_logs` | page |
| `owner` | `/super-admin/backup/history` | `super_admin.backup_history` | page |
| `owner` | `/super-admin/backup/report` | `super_admin.backup_report` | page |
| `owner` | `/super-admin/backup/schedule` | `super_admin.backup_schedule` | page |
| `owner` | `/super-admin/branch-templates` | `super_admin.branch_templates` | page |
| `owner` | `/super-admin/branding` | `super_admin.branding` | page |
| `owner` | `/super-admin/branding/preview` | `super_admin.branding_print_preview` | page |
| `owner` | `/super-admin/change-plan` | `super_admin.change_plan` | page |
| `owner` | `/super-admin/dashboard` | `super_admin.dashboard` | page |
| `owner` | `/super-admin/data-warehouse` | `super_admin.data_warehouse` | page |
| `owner` | `/super-admin/data-warehouse/export` | `super_admin.data_warehouse_export` | page |
| `owner` | `/super-admin/department-staff/<int:department_id>` | `super_admin.department_staff` | page |
| `owner` | `/super-admin/department/<int:department_id>` | `super_admin.view_department` | page |
| `owner` | `/super-admin/departments` | `super_admin.departments` | page |
| `owner` | `/super-admin/download-export/<filename>` | `super_admin.download_export` | page |
| `owner` | `/super-admin/edit-department/<int:department_id>` | `super_admin.edit_department` | page |
| `owner` | `/super-admin/edit-service/<int:service_id>` | `super_admin.edit_service` | page |
| `owner` | `/super-admin/export-departments` | `super_admin.export_departments` | page |
| `owner` | `/super-admin/export-services` | `super_admin.export_services` | page |
| `owner` | `/super-admin/maintenance/automation` | `super_admin.maintenance_automation` | page |
| `owner` | `/super-admin/performance` | `super_admin.performance` | page |
| `owner` | `/super-admin/permissions` | `super_admin.permissions` | page |
| `owner` | `/super-admin/permissions-matrix` | `super_admin.permissions_matrix` | page |
| `owner` | `/super-admin/pricing` | `super_admin.pricing` | page |
| `owner` | `/super-admin/queue-settings` | `super_admin.queue_settings` | page |
| `owner` | `/super-admin/reports` | `super_admin.reports` | page |
| `owner` | `/super-admin/roles` | `super_admin.roles` | page |
| `owner` | `/super-admin/roles/<int:role_id>/department-permissions` | `super_admin.manage_role_department_permissions` | page |
| `owner` | `/super-admin/roles/<int:role_id>/edit` | `super_admin.edit_role` | page |
| `owner` | `/super-admin/roles/<int:role_id>/permissions` | `super_admin.manage_role_permissions` | page |
| `owner` | `/super-admin/roles/create` | `super_admin.create_role` | page |
| `owner` | `/super-admin/security-center` | `super_admin.security_center` | page |
| `owner` | `/super-admin/security-logs` | `super_admin.security_logs` | page |
| `owner` | `/super-admin/service-pricing/<int:service_id>` | `super_admin.service_pricing` | page |
| `owner` | `/super-admin/service/<int:service_id>` | `super_admin.view_service` | page |
| `owner` | `/super-admin/services` | `super_admin.services` | page |
| `owner` | `/super-admin/subscription-status` | `super_admin.subscription_status` | page |
| `owner` | `/super-admin/system` | `super_admin.system` | page |
| `owner` | `/super-admin/system-backup` | `super_admin.system_backup` | page |
| `owner` | `/super-admin/system-config` | `super_admin.system_config` | page |
| `owner` | `/super-admin/system-monitor` | `super_admin.system_monitor` | page |
| `owner` | `/super-admin/system/maintenance` | `super_admin.system_maintenance` | page |
| `owner` | `/super-admin/usage` | `super_admin.tenant_usage` | page |
| `owner` | `/super-admin/users` | `super_admin.users` | page |
| `owner` | `/super-admin/users/<int:user_id>/edit` | `super_admin.edit_user` | page |
| `owner` | `/super-admin/users/create` | `super_admin.create_user` | page |

### الدور: `technician` (2 صفحة)

| الوحدة | المسار | Endpoint | النوع |
|---|---|---|---|
| `inventory` | `/barcode/registry` | `barcode.registry` | page |
| `inventory` | `/barcode/scan` | `barcode.scan_page` | page |
