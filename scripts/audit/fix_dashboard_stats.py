"""Give the command-center stat values the hooks its refresh script expects."""

from pathlib import Path

path = Path('templates/doctor/dashboard.html')
text = path.read_text(encoding='utf-8')
pairs = [
    (
        '{{ stats.today_visits or 0 }}',
        '<span data-stat="today-visits">{{ stats.today_visits or 0 }}</span>',
    ),
    (
        '{{ stats.completed_today or 0 }}',
        '<span data-stat="completed">{{ stats.completed_today or 0 }}</span>',
    ),
    (
        '{{ stats.pending_visits or 0 }}',
        '<span data-stat="waiting">{{ stats.pending_visits or 0 }}</span>',
    ),
    (
        '{{ stats.prescriptions_today or 0 }}',
        '<span data-stat="prescriptions">{{ stats.prescriptions_today or 0 }}</span>',
    ),
]
for old, new in pairs:
    text = text.replace(old, new)
path.write_text(text, encoding='utf-8', newline='')
print('patched dashboard stats')
