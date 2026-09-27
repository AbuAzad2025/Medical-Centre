"""Canonical clinical reference data for a fresh install.

This is the single source of truth for the reference rows a medical system needs
before it can be used at all. It lives in its own module rather than inside a
service so that the bootstrap, the pricing service and any future importer all
read the same list, instead of each carrying a private copy that drifts.

What belongs here, and what deliberately does not
-------------------------------------------------
Included: structural clinical reference data whose content is stable, verifiable
and not commercial -- currently the department catalogue.

Excluded on purpose, because seeding them would be fabrication or a security
hazard:

* **Doctors / staff accounts.** A seeded account with a known password is an
  unauthenticated backdoor the moment the port is reachable. Staff are created
  by a real administrator, or through the provisioning flow.
* **Patients and visits.** Fabricated clinical records are a patient-safety
  hazard, not seed data.
* **Insurance companies.** Commercial entities that differ per country and per
  tenant; inventing them produces claims that cannot be reconciled.
* **Wards, rooms, beds.** Physical inventory of a specific building. A platform
  cannot know them, and pre-creating them makes occupancy reporting lie.
* **Lab/drug catalogue codes.** LOINC, CPT and national drug codes must come
  from a maintained terminology source. A plausible-looking but wrong code is
  worse than an empty field, because it will be billed and reported as fact.

The rule applied throughout: seed what is structurally required and factually
stable, and leave everything else to an explicit administrative decision.
"""

from __future__ import annotations

#: (english name, arabic name). Keyed by the English name, which is what the
#: existing code and the rest of the system already treat as the department's
#: identity.
DEFAULT_DEPARTMENTS: tuple[tuple[str, str], ...] = (
    ('General Clinic', 'العيادة العامة'),
    ('Emergency', 'الطوارئ'),
    ('Internal Medicine', 'الباطنية'),
    ('General Surgery', 'الجراحة العامة'),
    ('Orthopedics', 'العظام'),
    ('Cardiology', 'القلبية'),
    ('Pediatrics', 'الأطفال'),
    ('Gynecology', 'النسائية'),
    ('ENT', 'أنف وأذن وحنجرة'),
    ('Ophthalmology', 'العيون'),
    ('Dermatology', 'الجلدة'),
    ('Urology', 'المسالك البولية'),
    ('Neurology', 'الأعصاب'),
    ('Radiology', 'الأشعة'),
    ('Lab', 'المختبر'),
)

#: Departments a clinical unit cannot operate without. Used by the readiness
#: check so a deployment that seeded nothing is reported as not-ready instead of
#: quietly serving an unusable system.
ESSENTIAL_DEPARTMENTS: frozenset[str] = frozenset(
    {'General Clinic', 'Emergency', 'Internal Medicine', 'Radiology', 'Lab'}
)
