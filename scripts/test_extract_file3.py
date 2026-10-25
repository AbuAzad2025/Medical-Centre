from babel.messages.extract import extract_from_file

result = list(extract_from_file(
    'templates/print/print_base.html',
    keywords={'_': None, 'gettext': None, 'ngettext': (1, 2)},
    comment_tags=(),
    options={},
    filename='templates/print/print_base.html'
))

print('Result:', result)
for item in result:
    print(f'  Line {item[0]}: {item[1]} = {item[2]}')