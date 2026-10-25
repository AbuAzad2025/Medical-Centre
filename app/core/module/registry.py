"""
Module Registry — single source of truth for all platform modules
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModuleMeta:
    name: str
    name_ar: str
    category: str  # clinical | administrative | financial | integration
    required_modules: tuple = ()
    required_any_of: tuple = ()
    capabilities: tuple = ()
    standalone_allowed: bool = True
    default_route: str = ''
    route_prefixes: tuple = ()
    feature_flags: tuple = ()
    icon: str = ''
    description_ar: str = ''
    # The tables this module touches.
    #
    # The list is NOT exclusive: a table belongs to every module that touches
    # it. ``prescriptions`` are written by the doctor and dispensed by the
    # pharmacy, ``visits`` are opened by reception and written by every
    # clinical module, and the intake modules are entry points into the same
    # tables as the functional modules they front. A table is therefore out of
    # a tenant's reach only when NO active module touches it - which is a
    # different and much safer question than "which module owns this table".
    #
    # Every name here must exist in the schema. The table list is checked
    # against the live schema by tests/test_module_table_ownership.py, because
    # a name that exists in no table is a silent hole: the table it was meant
    # to protect is not protected at all.
    #
    # Empty means "no dedicated tables" (e.g. owner, portal, integration).
    tables: tuple[str, ...] = ()


# Central registry — hardcoded, version-controlled
MODULE_REGISTRY: dict[str, ModuleMeta] = {
    'reception': ModuleMeta(
        name='reception',
        name_ar='الاستقبال',
        category='administrative',
        required_modules=(),
        required_any_of=(),
        capabilities=('patient_lookup', 'visit_create', 'appointment_manage'),
        standalone_allowed=True,
        default_route='/reception/dashboard',
        route_prefixes=('/reception',),
        icon='fas fa-user-plus',
        description_ar='تسجيل المرضى والزيارات والمواعيد',
        tables=(
            'patients',
            'patient_search_ngrams',
            'patient_visit_counters',
            'patient_accounts',
            'patient_allergies',
            'visits',
            'queue_management',
            'queue_settings',
            'departments',
            'workflow_queues',
            'workflow_steps',
            'workflow_transfers',
            'patient_workflows',
            'visit_workflow_events',
            'request_workflows',
            'department_workflows',
            # Claimed from orphan list (used by booking_routes, queue_management_service):
            'staff_absences',
            'staff_work_schedules',
            'visit_transfer_logs',
        ),
    ),
    'doctor': ModuleMeta(
        name='doctor',
        name_ar='الأطباء',
        category='clinical',
        required_modules=(),
        required_any_of=(),
        capabilities=('clinical_encounter', 'prescription', 'order_lab', 'order_radiology'),
        standalone_allowed=True,
        default_route='/doctor/dashboard',
        route_prefixes=(
            '/doctor',
            '/vaccination',
            '/referral',
            '/pathway',
            '/cds',
            '/patient-education',
            '/telemedicine',
            '/clinical-coding',
            '/specialty-forms',
        ),
        feature_flags=('soap_notes', 'diagnosis_coding', 'e_signature'),
        icon='fas fa-user-md',
        description_ar='الفحوصات والتشخيص والروشيتات',
        tables=(
            'patients',
            'visits',
            'medical_records',
            'medical_reports',
            'consultations',
            'coded_diagnoses',
            'coded_procedures',
            'prescriptions',
            'prescription_items',
            'lab_requests',
            'radiology_requests',
            'follow_up_requests',
            'referrals',
            'treatments',
            'patient_allergies',
            'allergy_intolerances',
            'patient_problems',
            'patient_care_plans',
            'care_plan_tasks',
            'clinical_pathways',
            'clinical_pathway_steps',
            'consent_templates',
            'patient_consents',
            'consent_audit_logs',
            'specialty_forms',
            'specialty_form_fields',
            'specialty_form_submissions',
            'specialty_form_versions',
            'digital_signatures',
            'immunizations',
            'vaccination_schedules',
            'vaccines',
            'patient_education_materials',
            'patient_education_assignments',
            'dental_charts',
            'dental_teeth',
            'surgery_checklists',
            'surgery_schedules',
            'cds_alert_rules',
            'cds_fired_alerts',
            'patient_insights',
            'patient_satisfaction_surveys',
        ),
    ),
    'lab': ModuleMeta(
        name='lab',
        name_ar='المختبر',
        category='clinical',
        required_modules=(),
        required_any_of=(),
        capabilities=(
            'patient_lookup',
            'lab_order',
            'sample_collection',
            'result_entry',
            'result_validation',
            'report_delivery',
        ),
        standalone_allowed=True,
        default_route='/lab/worklist',
        route_prefixes=('/lab',),
        feature_flags=('allow_walkin_lab', 'requires_payment_before_sample', 'enable_lab_qc'),
        icon='fas fa-flask',
        description_ar='طلبات التحاليل والعينات والنتائج والجودة',
        tables=(
            'lab_requests',
            'lab_results',
            'lab_test_catalog',
            'lab_test_panels',
            'lab_test_panel_items',
            'lab_quality_control_entries',
            'lab_reagents',
        ),
    ),
    'radiology': ModuleMeta(
        name='radiology',
        name_ar='الأشعة',
        category='clinical',
        required_modules=(),
        required_any_of=(),
        capabilities=(
            'patient_lookup',
            'radiology_order',
            'image_upload',
            'report_draft',
            'report_sign',
        ),
        standalone_allowed=True,
        default_route='/radiology/worklist',
        route_prefixes=('/radiology', '/dicom'),
        feature_flags=('dicom_enabled', 'ai_imaging_enabled'),
        icon='fas fa-x-ray',
        description_ar='طلبات الأشعة والتقارير والصور',
        tables=(
            'radiology_requests',
            'radiology_results',
            'dicom_instances',
            'dicom_series',
            'dicom_studies',
            'pacs_configurations',
        ),
    ),
    'pharmacy': ModuleMeta(
        name='pharmacy',
        name_ar='الصيدلية',
        category='clinical',
        required_modules=(),
        required_any_of=(),
        capabilities=('dispense', 'pos_sale', 'stock_view', 'substitution'),
        standalone_allowed=True,
        default_route='/medication/pos',
        route_prefixes=('/medication',),
        feature_flags=('controlled_medications', 'batch_tracking', 'auto_reorder'),
        icon='fas fa-pills',
        description_ar='إدارة الأدوية والمخزون والصرف',
        tables=(
            'patients',
            'medications',
            'prescriptions',
            'prescription_items',
            'pharmacy_sales',
            'pharmacy_sale_items',
            'pharmacy_returns',
            'prescription_dispense_logs',
            'suppliers',
            'medication_purchases',
            'drug_interactions',
            'medication_supply_requests',
            'medication_supply_request_items',
            'medication_reconciliations',
            'medication_schedules',
            'cash_registers',
            'pricing_catalog',
            'temporary_services',
            'patient_accounts',
        ),
    ),
    'emergency': ModuleMeta(
        name='emergency',
        name_ar='الطوارئ',
        category='clinical',
        required_modules=(),
        required_any_of=(),
        capabilities=('triage', 'emergency_care', 'rapid_assessment'),
        standalone_allowed=True,
        default_route='/emergency/dashboard',
        route_prefixes=('/emergency',),
        icon='fas fa-ambulance',
        description_ar='حالات الطوارئ والأولوية',
        tables=(
            'emergency_cases',
            'emergency_status_history',
            'patients',
            'visits',
        ),
    ),
    'nursing': ModuleMeta(
        name='nursing',
        name_ar='التمريض',
        category='clinical',
        required_modules=(),
        required_any_of=(),
        capabilities=('vital_signs', 'triage', 'medication_admin', 'nursing_notes'),
        standalone_allowed=True,
        default_route='/nurse/dashboard',
        route_prefixes=('/nurse', '/emar', '/bed', '/or', '/nursing-assessment'),
        feature_flags=('emar_enabled', 'bed_management'),
        icon='fas fa-user-nurse',
        description_ar='رعاية المرضى والتمريض والعلاجات',
        tables=(
            'vital_signs',
            'emar_administrations',
            'nursing_assessments',
            'shift_handovers',
            'medication_administration_logs',
            'medication_schedules',
            'medical_records',
            'visits',
            # Claimed from orphan list (used by nursing_service, task management):
            'nurses',
            'tasks',
            'task_comments',
            'task_attachments',
        ),
    ),
    'billing': ModuleMeta(
        name='billing',
        name_ar='الفوترة',
        category='financial',
        required_modules=(),
        required_any_of=(),
        capabilities=('invoice', 'payment', 'receipt', 'debt_management'),
        standalone_allowed=True,
        default_route='/finance/dashboard',
        route_prefixes=('/finance', '/accountant', '/payment'),
        feature_flags=('insurance_billing', 'installments', 'force_payment'),
        icon='fas fa-file-invoice-dollar',
        description_ar='الفواتير والدفعات والتأمين',
        tables=(
            'patients',
            'invoices',
            'invoice_services',
            'payments',
            'receipts',
            'payment_cards',
            'insurance_claims',
            'insurance_claim_lines',
            'insurance_companies',
            'insurance_payouts',
            'eobs',
            'insurance_providers',
            'refund_requests',
            'service_prices',
            'service_master',
            'doctor_pricing',
            'expenses',
            'budgets',
            'financial_periods',
            'gl_journals',
            'gl_journal_lines',
            'accounts',
            'exchange_rates',
            'pricing_management',
            'pricing_rules',
            'online_booking_payment_transactions',
            'patient_accounts',
        ),
    ),
    'inventory': ModuleMeta(
        name='inventory',
        name_ar='المخزون',
        category='administrative',
        required_modules=(),
        required_any_of=(),
        capabilities=('stock_manage', 'purchase_order', 'barcode_scan', 'inventory_report'),
        standalone_allowed=True,
        default_route='/barcode/registry',
        route_prefixes=('/barcode',),
        feature_flags=('auto_reorder', 'low_stock_alerts'),
        icon='fas fa-boxes',
        description_ar='المستودعات والمشتريات والمخزون',
        tables=(
            'stock_movements',
            'medications',
            'barcode_registry',
            'barcode_scan_logs',
            'medication_purchases',
            'suppliers',
            'file_categories',
            'file_permissions',
            'file_uploads',
            'temporary_services',
            'pricing_catalog',
        ),
    ),
    'appointments': ModuleMeta(
        name='appointments',
        name_ar='المواعيد',
        category='administrative',
        required_modules=(),
        required_any_of=(),
        capabilities=('schedule', 'reminder', 'online_booking'),
        standalone_allowed=True,
        default_route='/booking/dashboard',
        route_prefixes=('/booking',),
        feature_flags=('online_booking', 'sms_reminder', 'telemedicine'),
        icon='fas fa-calendar-alt',
        description_ar='جدولة المواعيد والتذكير',
        tables=(
            'appointments',
            'telemedicine_appointments',
            'online_bookings',
            'online_booking_payment_transactions',
            'patient_visit_counters',
        ),
    ),
    'reporting': ModuleMeta(
        name='reporting',
        name_ar='التقارير',
        category='administrative',
        required_modules=(),
        required_any_of=(),
        capabilities=('report_view', 'report_create', 'report_export', 'analytics'),
        standalone_allowed=True,
        default_route='/manager/dashboard',
        route_prefixes=(
            '/manager',
            '/report-builder',
            '/data-warehouse',
            '/population-health',
            '/quality',
            '/what-if',
        ),
        feature_flags=('advanced_analytics', 'custom_reports', 'data_warehouse'),
        icon='fas fa-chart-bar',
        description_ar='التقارير الطبية والمالية والإدارية',
        tables=(
            'reports',
            'report_templates',
            'report_executions',
            'performance_analytics',
            'population_health_indicators',
            'quality_measures',
            'what_if_scenarios',
            'disease_registries',
            'disease_patterns',
            'data_warehouse_syncs',
            'dw_daily_visit_summary',
            'dw_monthly_finance_summary',
            'patient_insights',
            'patient_satisfaction_surveys',
        ),
    ),
    'owner': ModuleMeta(
        name='owner',
        name_ar='المالك',
        category='integration',
        required_modules=(),
        required_any_of=(),
        capabilities=('platform_manage', 'tenant_manage', 'billing_manage', 'analytics_global'),
        standalone_allowed=True,
        default_route='/owner/dashboard',
        route_prefixes=('/owner', '/super-admin'),
        icon='fas fa-crown',
        description_ar='لوحة تحكم المالك والمنصة السحابية',
    ),
    'portal': ModuleMeta(
        name='portal',
        name_ar='بوابة المرضى',
        category='clinical',
        required_modules=(),
        required_any_of=(),
        capabilities=('patient_self_service', 'view_results', 'book_appointment', 'view_bills'),
        standalone_allowed=True,
        default_route='/portal/dashboard',
        route_prefixes=('/portal',),
        feature_flags=('patient_portal', 'online_payment'),
        icon='fas fa-user-circle',
        description_ar='بوابة المريض الإلكترونية',
        tables=(
            'patient_accounts',
            'online_bookings',
            'appointments',
            'invoices',
            'payments',
        ),
    ),
    'ai_imaging': ModuleMeta(
        name='ai_imaging',
        name_ar='التصوير بالذكاء الاصطناعي',
        category='clinical',
        required_modules=(),
        required_any_of=(),
        capabilities=('ai_analysis', 'image_enhancement', 'auto_report'),
        standalone_allowed=True,
        default_route='/ai-imaging',
        route_prefixes=('/ai-imaging',),
        feature_flags=('ai_assisted_diagnosis',),
        icon='fas fa-robot',
        description_ar='تحليل الصور الطبية بالذكاء الاصطناعي',
        tables=(
            'ai_imaging_analyses',
            'ai_recommendations',
            'model_predictions',
            'radiology_requests',
            'radiology_results',
        ),
    ),
    'integration': ModuleMeta(
        name='integration',
        name_ar='التكامل',
        category='integration',
        required_modules=(),
        required_any_of=(),
        capabilities=('fhir_api', 'sso', 'dicom_listener'),
        standalone_allowed=True,
        default_route='/sso/config',
        route_prefixes=('/sso', '/api/fhir'),
        feature_flags=('sso_enabled', 'fhir_enabled'),
        icon='fas fa-plug',
        description_ar='التكامل مع الأنظمة الخارجية (SSO, FHIR)',
        tables=(
            'fhir_patients',
            'fhir_encounters',
            'fhir_observations',
            'fhir_document_references',
            'fhir_audit_logs',
            'sso_configurations',
            'sso_user_mappings',
            'api_keys',
            'whatsapp_config',
            'whatsapp_integration_messages',
            'whatsapp_templates',
            'email_messages',
        ),
    ),
    # Intake modules (lightweight entry points for standalone workflows)
    'clinic_intake': ModuleMeta(
        name='clinic_intake',
        name_ar='استقبال العيادة',
        category='clinical',
        required_modules=(),
        required_any_of=(),
        capabilities=('patient_checkin', 'visit_start', 'quick_triage'),
        standalone_allowed=True,
        default_route='/clinic/intake',
        route_prefixes=('/clinic',),
        icon='fas fa-clipboard-check',
        description_ar='تسجيل دخول المريض للعيادة - سريع ومستقل',
        tables=(
            'patients',
            'visits',
            'queue_management',
        ),
    ),
    'lab_intake': ModuleMeta(
        name='lab_intake',
        name_ar='استقبال المختبر',
        category='clinical',
        required_modules=(),
        required_any_of=(),
        capabilities=('sample_receive', 'walkin_lab', 'quick_order'),
        standalone_allowed=True,
        default_route='/lab/intake',
        route_prefixes=('/lab',),
        icon='fas fa-vial',
        description_ar='استقبال العينات للمختبر - دخول مباشر',
        tables=(
            'lab_requests',
            'lab_results',
            'lab_test_catalog',
            'patients',
        ),
    ),
    'radiology_intake': ModuleMeta(
        name='radiology_intake',
        name_ar='استقبال الأشعة',
        category='clinical',
        required_modules=(),
        required_any_of=(),
        capabilities=('study_receive', 'walkin_radiology', 'quick_order'),
        standalone_allowed=True,
        default_route='/radiology/intake',
        route_prefixes=('/radiology',),
        icon='fas fa-image',
        description_ar='استقبال طلبات الأشعة - دخول مباشر',
        tables=(
            'radiology_requests',
            'radiology_results',
            'patients',
        ),
    ),
    'pharmacy_pos': ModuleMeta(
        name='pharmacy_pos',
        name_ar='نقطة بيع الصيدلية',
        category='clinical',
        required_modules=(),
        required_any_of=(),
        capabilities=('direct_sale', 'otc_sale', 'walkin_pharmacy'),
        standalone_allowed=True,
        default_route='/medication/pos',
        route_prefixes=('/medication',),
        icon='fas fa-cash-register',
        description_ar='بيع مباشر في الصيدلية بدون وصفة طبية',
        tables=(
            'pharmacy_sales',
            'pharmacy_sale_items',
            'medications',
            'cash_registers',
            'pricing_catalog',
            'patient_accounts',
        ),
    ),
    'pharmacy_customer_intake': ModuleMeta(
        name='pharmacy_customer_intake',
        name_ar='تسجيل عميل الصيدلية',
        category='clinical',
        required_modules=(),
        required_any_of=(),
        capabilities=('customer_register', 'loyalty', 'prescription_drop'),
        standalone_allowed=True,
        default_route='/pharmacy/intake',
        route_prefixes=('/pharmacy',),
        icon='fas fa-user-plus',
        description_ar='تسجيل عميل الصيدلية السريع - اسم ورقم فقط',
        tables=(
            'patients',
            'patient_accounts',
        ),
    ),
    'standalone_intake': ModuleMeta(
        name='standalone_intake',
        name_ar='استقبال مستقل',
        category='clinical',
        required_modules=(),
        required_any_of=(),
        capabilities=('patient_register', 'visit_create', 'quick_encounter'),
        standalone_allowed=True,
        default_route='/intake',
        route_prefixes=('/intake',),
        icon='fas fa-door-open',
        description_ar='تسجيل مريض وزيارة سريع - مستقل عن الاستقبال الكامل',
        tables=(
            'patients',
            'visits',
        ),
    ),
    'inpatient': ModuleMeta(
        name='inpatient',
        name_ar='الإقامة الداخلية',
        category='clinical',
        required_modules=(),
        required_any_of=(),
        capabilities=('admission', 'discharge', 'bed_management', 'rounding'),
        standalone_allowed=True,
        default_route='/inpatient/dashboard',
        route_prefixes=('/inpatient', '/bed', '/admission'),
        feature_flags=('bed_management', 'nursing_handover'),
        icon='fas fa-bed',
        description_ar='إدارة الإقامة الداخلية والأسرة والتنويم',
        tables=(
            'admissions',
            'beds',
            'wards',
            'bed_transfers',
            'rooms',
            'visits',
            'medical_records',
            'vital_signs',
            'shift_handovers',
        ),
    ),
}


# The inverse of the table lists above: table name -> the modules that touch
# it. Built once at import so the tenant filter does not walk the registry on
# every statement.
_TABLE_MODULES: dict[str, frozenset[str]] = {}
for _meta in MODULE_REGISTRY.values():
    for _table in _meta.tables:
        _TABLE_MODULES[_table] = _TABLE_MODULES.get(_table, frozenset()) | {_meta.name}
del _meta, _table


def get_module_for_table(table_name: str) -> str | None:
    """The first module that touches this table, or None if none does.

    Prefer :func:`get_modules_for_table`: a table usually belongs to more than
    one module, and the first name in the registry is not the owner.
    """
    for meta in MODULE_REGISTRY.values():
        if table_name in meta.tables:
            return meta.name
    return None


def get_modules_for_table(table_name: str) -> frozenset[str]:
    """Every module that touches this table.

    The table lists are not exclusive - the doctor writes the prescriptions the
    pharmacy dispenses, and every clinical module writes the visit - so the
    table belongs to all of them. The tenant filter uses this to answer one
    question: is there an ACTIVE module that touches this table? A table with
    no active module behind it is out of the tenant's reach.
    """
    return _TABLE_MODULES.get(table_name, frozenset())


def get_tables_for_module(module_name: str) -> tuple[str, ...]:
    """The tables a module touches."""
    meta = MODULE_REGISTRY.get(module_name)
    return meta.tables if meta else ()


def get_module_metadata(name: str) -> ModuleMeta | None:
    return MODULE_REGISTRY.get(name)


def get_all_module_names() -> list[str]:
    return list(MODULE_REGISTRY.keys())


def get_clinical_modules() -> list[str]:
    return [m.name for m in MODULE_REGISTRY.values() if m.category == 'clinical']


def get_modules_by_capability(capability: str) -> list[str]:
    return [m.name for m in MODULE_REGISTRY.values() if capability in m.capabilities]


def get_standalone_modules() -> list[str]:
    return [m.name for m in MODULE_REGISTRY.values() if m.standalone_allowed]


def get_feature_flags_for_module(module: str) -> tuple:
    meta = MODULE_REGISTRY.get(module)
    return meta.feature_flags if meta else ()
