"""
Module → Route mapping for route-based module gating
"""
MODULE_ROUTE_MAP: dict[str, dict] = {
    "reception": {"blueprints": ["reception_bp", "reception_currency_bp"], "prefixes": ["/reception"]},
    "doctor": {"blueprints": ["doctor_bp", "vaccination_bp", "referral_bp", "pathway_bp", "cds_bp", "patient_education_bp", "telemedicine_bp", "clinical_coding_bp"], "prefixes": ["/doctor", "/vaccination", "/referral", "/pathway", "/cds", "/patient-education", "/telemedicine", "/clinical-coding"]},
    "lab": {"blueprints": ["lab_bp"], "prefixes": ["/lab"]},
    "radiology": {"blueprints": ["radiology_bp", "dicom_bp"], "prefixes": ["/radiology", "/dicom"]},
    "pharmacy": {"blueprints": ["medication_bp"], "prefixes": ["/medication"]},
    "emergency": {"blueprints": ["emergency_bp"], "prefixes": ["/emergency"]},
    "nursing": {"blueprints": ["nurse_bp", "emar_bp", "bed_bp", "or_bp", "nursing_assessment_bp"], "prefixes": ["/nurse", "/emar", "/bed", "/or", "/nursing-assessment"]},
    "billing": {"blueprints": ["finance_bp", "accountant_bp", "payment_bp"], "prefixes": ["/finance", "/accountant", "/payment"]},
    "inventory": {"blueprints": ["barcode_bp"], "prefixes": ["/barcode"]},
    "appointments": {"blueprints": ["booking_bp"], "prefixes": ["/booking"]},
    "reporting": {"blueprints": ["manager_bp", "report_builder_bp", "data_warehouse_bp", "pop_health_bp", "quality_bp", "what_if_bp"], "prefixes": ["/manager", "/report-builder", "/data-warehouse", "/population-health", "/quality", "/what-if"]},
    "owner": {"blueprints": ["owner_bp", "super_admin_bp"], "prefixes": ["/owner", "/super-admin"]},
    "portal": {"blueprints": ["portal_bp"], "prefixes": ["/portal"]},
    "ai_imaging": {"blueprints": ["ai_imaging_bp"], "prefixes": ["/ai-imaging"]},
    "integration": {"blueprints": ["fhir_bp", "sso_bp"], "prefixes": ["/api/fhir", "/sso"]},
}

CORE_BLUEPRINTS = {"main_bp", "auth_bp", "security_bp", "mfa_bp", "backup_bp", "backup_restore_bp", "biometric_bp"}

def get_module_for_prefix(prefix: str) -> str | None:
    for module, info in MODULE_ROUTE_MAP.items():
        if prefix in info["prefixes"]:
            return module
    return None

def get_prefixes_for_module(module: str) -> list[str]:
    info = MODULE_ROUTE_MAP.get(module)
    return info["prefixes"] if info else []

def is_core_blueprint(bp_name: str) -> bool:
    return bp_name in CORE_BLUEPRINTS