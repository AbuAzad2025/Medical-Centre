"""Small UI fixes in the doctor shell: accessible labels, RTL arrows, contrast."""

from pathlib import Path

fixes = {
    'templates/doctor/dashboard.html': [
        ('aria-label="Close"', 'aria-label="{{ _(\'إغلاق\') }}"'),
        ('bg-warning bg-opacity-10 text-warning', 'bg-warning bg-opacity-10 text-warning-emphasis'),
    ],
    'templates/doctor/notes.html': [
        ('aria-label="Close"', 'aria-label="{{ _(\'إغلاق\') }}"'),
        ("'icon': 'fas fa-arrow-left'", "'icon': 'fas fa-arrow-right'"),
    ],
    'templates/doctor/patient_queue.html': [
        ('bg-warning bg-opacity-10 text-warning', 'bg-warning bg-opacity-10 text-warning-emphasis'),
    ],
    'templates/doctor/patient_details.html': [
        (
            "onclick=\"return confirmSubmit(event, '{{ _('هل أنت متأكد من إنهاء العلاج؟') }}')\"",
            'onclick="return confirmSubmit(event, {{ _(\'هل أنت متأكد من إنهاء العلاج؟\')|tojson }})"',
        ),
    ],
    'templates/doctor/patient_timeline.html': [
        ('aria-label="Timeline pagination"', 'aria-label="{{ _(\'تصفح الخط الزمني\') }}"'),
    ],
    'templates/doctor/print_medical_report.html': [
        (
            '<div class="mt-2">{{ current_user.digital_signature }}</div>',
            '<div class="mt-2"><img src="{{ current_user.digital_signature }}" alt="{{ _(\'التوقيع\') }}" class="img-fluid" style="max-height:80px;"></div>',
        ),
    ],
}

for name, pairs in fixes.items():
    path = Path(name)
    text = path.read_text(encoding='utf-8')
    original = text
    for old, new in pairs:
        text = text.replace(old, new)
    if text != original:
        path.write_text(text, encoding='utf-8', newline='')
        print('patched', path)
