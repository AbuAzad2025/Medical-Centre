"""
Module Registry — single source of truth for all platform modules
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModuleMeta:
    name: str
    name_ar: str
    category: str  # clinical | administrative | financial | integration
    required_modules: tuple
    required_any_of: tuple = ()
    capabilities: tuple = ()
    standalone_allowed: bool = True
    default_route: str = ''
    route_prefixes: tuple = ()
    feature_flags: tuple = ()
    icon: str = ''
    description_ar: str = ''


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
    ),
}


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
