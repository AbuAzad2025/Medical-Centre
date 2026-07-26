"""Fix weak passwords in test fixtures after password policy enforcement."""
import re

FILES = [
    'tests/test_booking_conversion_service.py',
    'tests/test_access_control_service.py',
    'tests/test_financial_services.py',
    'tests/test_financial_service_expenses.py',
    'tests/test_gatekeeper_service.py',
    'tests/test_lab_radiology_services.py',
    'tests/test_notification_service.py',
    'tests/test_nursing_service.py',
    'tests/test_queue_management_service.py',
    'tests/test_pricing_service.py',
    'tests/test_report_service.py',
    'tests/test_payment_refund_services.py',
]

for fp in FILES:
    with open(fp, 'r', encoding='utf-8') as f:
        content = f.read()
    new_content = content.replace(".set_password('p')", ".set_password('ValidPass123!')")
    if new_content != content:
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f'Fixed {fp}')
    else:
        print(f'No changes in {fp}')
