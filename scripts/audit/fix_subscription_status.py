PATH = 'templates/owner/subscriptions.html'
with open(PATH, encoding='utf-8') as fh:
    text = fh.read()
text = text.replace(
    '                {% set addons =',
    '                {% set status_key = t.status.value|lower %}\n                {% set addons =',
    1,
)
text = text.replace('t.status.value ==', 'status_key ==').replace(
    't.status.value !=', 'status_key !='
)
text = text.replace('{{ t.status.value }}</span>', '{{ status_key }}</span>')
with open(PATH, 'w', encoding='utf-8', newline='') as fh:
    fh.write(text)
print('patched status casing')
