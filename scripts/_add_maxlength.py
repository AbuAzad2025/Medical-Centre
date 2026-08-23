"""
Add maxlength to text inputs in critical templates.
Maps field names -> DB column lengths from model definitions.
Only touches high-traffic forms (patient, visit, appointment, user, medication).
"""
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent / 'templates'

# Field name -> max length (from DB schema / models)
FIELD_LENGTHS = {
    'first_name': 200,
    'last_name': 200,
    'first_name_ar': 200,
    'last_name_ar': 200,
    'full_name': 120,
    'username': 80,
    'email': 120,
    'phone': 20,
    'emergency_contact_phone': 20,
    'emergency_contact_name': 100,
    'national_id': 32,
    'passport_number': 20,
    'address': 500,
    'insurance_number': 50,
    'insurance_policy_number': 60,
    'insurance_provider': 200,
    'insurance_company_id': None,
    'card_last_digits': 4,
    'card_holder_name': 100,
    'trade_name': 200,
    'scientific_name': 200,
    'batch_number': 100,
    'invoice_number': 100,
    'receipt_number': 50,
    'name': 100,
    'name_ar': 100,
    'description': None,  # Text field — no limit needed
    'notes': None,
    'symptoms': None,
    'diagnosis': None,
    'title': 200,
}

# Only patch these critical templates
TARGETS = [
    'reception/patients.html',
    'reception/create_visit.html',
    'reception/create_appointment.html',
    'auth/reset_password.html',
    'medication/inventory.html' if (ROOT / 'medication/inventory.html').exists() else None,
]

# Filter existing files
targets = [ROOT / t for t in TARGETS if t and (ROOT / t).exists()]

total_added = 0
for tpl in targets:
    rel = tpl.relative_to(ROOT)
    content = tpl.read_text(encoding='utf-8')
    modified = False

    # Find <input type="text" ... name="FIELD" ...> without maxlength
    pattern = re.compile(
        r'(<input\s[^>]*type="(?:text|tel|email)"[^>]*name="(\w+)"[^>]*?)(\s*/?>)',
        re.IGNORECASE
    )

    def add_maxlen(match):
        global total_added
        tag = match.group(1)
        field_name = match.group(2)
        closing = match.group(3)

        # Skip if already has maxlength
        if 'maxlength' in tag.lower():
            return match.group(0)

        # Look up length
        maxlen = FIELD_LENGTHS.get(field_name)
        if not maxlen:
            return match.group(0)

        # Don't add to hidden fields
        if 'type="hidden"' in tag:
            return match.group(0)

        total_added += 1
        modified_flag[0] = True
        return f'{tag} maxlength="{maxlen}"{closing}'

    modified_flag = [False]
    new_content = pattern.sub(add_maxlen, content)

    if modified_flag[0]:
        tpl.write_text(new_content, encoding='utf-8')
        print(f'  patched {rel}')

print(f'Total maxlength attributes added: {total_added}')
