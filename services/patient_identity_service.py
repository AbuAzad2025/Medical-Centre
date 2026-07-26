"""Patient portal identity — UX1-006."""

from models.patient import Patient
from models.patient_account import PatientAccount
from app.extensions import db
from utils.db_safety import safe_commit
from sqlalchemy import select


DEFAULT_PORTAL_PREFERENCES = {
    'notify_results': True,
    'notify_appointments': True,
    'marketing_contact': False,
    'telemedicine_consent': False,
}


def resolve_patient_for_user(user):
    """Return the Patient linked to this user via PatientAccount."""
    if not user or not getattr(user, 'is_authenticated', True) or not user.is_authenticated:
        return None
    link = db.session.execute(select(PatientAccount).filter_by(user_id=user.id)).scalars().first()
    return link.patient if link else None


def get_patient_account(user):
    if not user:
        return None
    return db.session.execute(select(PatientAccount).filter_by(user_id=user.id)).scalars().first()


def get_portal_preferences(user):
    link = get_patient_account(user)
    if not link:
        return dict(DEFAULT_PORTAL_PREFERENCES)
    prefs = link.portal_preferences if isinstance(link.portal_preferences, dict) else {}
    merged = dict(DEFAULT_PORTAL_PREFERENCES)
    merged.update(prefs)
    return merged


def save_portal_preferences(user, updates: dict) -> bool:
    link = get_patient_account(user)
    if not link:
        return False
    allowed = set(DEFAULT_PORTAL_PREFERENCES.keys())
    current = get_portal_preferences(user)
    for key, value in updates.items():
        if key in allowed:
            current[key] = bool(value)
    link.portal_preferences = current
    safe_commit(db.session, error_message="Failed to save portal preferences", reraise=True)
    return True


def verify_and_link_patient(user, *, national_id=None, phone=None):
    """
    Match an existing patient record and link to user.
    Returns (patient, error_message).
    """
    national_id = (national_id or '').strip() or None
    phone = (phone or '').strip() or None
    if not national_id and not phone:
        return None, 'يرجى إدخال رقم الهوية أو الهاتف'

    patient = None
    if national_id:
        patient = db.session.execute(select(Patient).filter_by(national_id=national_id)).scalars().first()
    if not patient and phone:
        patient = db.session.execute(select(Patient).filter_by(phone=phone)).scalars().first()
    if not patient:
        return None, 'لم يتم العثور على ملف مريض مطابق. تواصل مع الاستقبال'

    existing = db.session.execute(select(PatientAccount).filter_by(patient_id=patient.id)).scalars().first()
    if existing and existing.user_id != user.id:
        return None, 'هذا الملف مرتبط بحساب آخر'

    if not existing:
        link = PatientAccount(
            user_id=user.id,
            patient_id=patient.id,
            tenant_id=patient.tenant_id or user.tenant_id,
            portal_preferences=dict(DEFAULT_PORTAL_PREFERENCES),
        )
        db.session.add(link)
        safe_commit(db.session, error_message="Failed to link patient account", reraise=True)
    return patient, None
