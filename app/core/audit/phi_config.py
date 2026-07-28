PHI_FIELD_MAP = {
    "Patient": {
        "national_id", "first_name", "last_name", "first_name_ar", "last_name_ar",
        "phone", "address", "insurance_member_number", "birth_date", "notes",
        "is_pregnant", "pregnancy_weeks", "last_menstruation_date", "pregnancy_notes",
    },
    "OnlineBooking": {
        "first_name", "last_name", "national_id", "phone", "email",
        "date_of_birth", "symptoms", "insurance_number", "notes",
    },
    "PatientConsent": {
        "guardian_name", "guardian_id_number",
    },
}

ALWAYS_PLAIN = {
    "id", "created_at", "updated_at", "tenant_id", "patient_id",
    "status", "version", "gender", "marital_status",
    "consent_type", "scope_description", "capture_method",
}


def is_phi_field(model_name: str, field_name: str) -> bool:
    if field_name in ALWAYS_PLAIN:
        return False
    return field_name in PHI_FIELD_MAP.get(model_name, set())


def redact_value(model_name: str, field_name: str, value):
    if is_phi_field(model_name, field_name):
        return "[REDACTED]"
    return value
