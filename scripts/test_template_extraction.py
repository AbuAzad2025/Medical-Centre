import os, re, sys
sys.path.insert(0, r'D:\recovers\data\medical')

from babel.messages.extract import parse_template_string

# Test different template syntaxes
templates = [
    # Standard syntax
    '''
{% trans %}Hello World{% endtrans %}
{{ _('Hello World') }}
{{ gettext('Hello World') }}
{% trans %}Hello {{ name }}{% endtrans %}
''',
    # Test with double quotes
    '''
{% trans %}Hello World{% endtrans %}
{{ _("Hello World") }}
{{ gettext("Hello World") }}
{% trans %}Hello {{ name }}{% endtrans %}
''',
    # Test with single quotes
    '''
{% trans %}Hello World{% endtrans %}
{{ _('Hello World') }}
{{ gettext('Hello World') }}
{% trans %}Hello {{ name }}{% endtrans %}
''',
]

for i, template in enumerate(templates):
    try:
        result = list(parse_template_string(
            template,
            keywords={'_': None, 'gettext': None, 'ngettext': (1, 2)},
            comment_tags=(),
            options={}
        ))
        print(f'Template {i}: {result}')
    except Exception as e:
        print(f'Error: {e}')