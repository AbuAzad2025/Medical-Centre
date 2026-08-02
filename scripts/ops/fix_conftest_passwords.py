"""Fix weak passwords in conftest.py"""

with open('tests/conftest.py', encoding='utf-8') as f:
    content = f.read()
content = content.replace("u.set_password('test123')", "u.set_password('ValidPass123!')")
with open('tests/conftest.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed conftest.py')
