"""Wrap navbar labels and aria text in gettext."""

from pathlib import Path

path = Path('templates/partials/_navbar.html')
text = path.read_text(encoding='utf-8')
pairs = [
    ('aria-label="البحث في النظام"', 'aria-label="{{ _(\'البحث في النظام\') }}"'),
    (
        'aria-label="الإشعارات" title="الإشعارات"',
        'aria-label="{{ _(\'الإشعارات\') }}" title="{{ _(\'الإشعارات\') }}"',
    ),
    ('aria-label="تبديل الوضع الليلي"', 'aria-label="{{ _(\'تبديل الوضع الليلي\') }}"'),
    (
        'title="مظهر الواجهة" aria-label="إعدادات الواجهة"',
        'title="{{ _(\'مظهر الواجهة\') }}" aria-label="{{ _(\'إعدادات الواجهة\') }}"',
    ),
    ('title="كثافة الواجهة"', 'title="{{ _(\'كثافة الواجهة\') }}"'),
    ('title="انحناء الحواف"', 'title="{{ _(\'انحناء الحواف\') }}"'),
    ('aria-label="قائمة المستخدم"', 'aria-label="{{ _(\'قائمة المستخدم\') }}"'),
    ('{{ current_user.role }}', '{{ _(current_user.role) }}'),
    (
        'searchResults.innerHTML = \'<div class="p-3 text-center text-muted small">لا توجد نتائج</div>\';',
        "searchResults.innerHTML = '<div class=\"p-3 text-center text-muted small\">' + {{ _('لا توجد نتائج')|tojson }} + '</div>';",
    ),
]
for old, new in pairs:
    text = text.replace(old, new)
path.write_text(text, encoding='utf-8', newline='')
print('patched navbar i18n')
