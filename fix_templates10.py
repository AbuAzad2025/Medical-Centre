with open('tools/scenario_gen/templates.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix NURSE_PROTOCOLS_API - add 2 more steps
old = """_s(NURSE, 'POST /nurse/api/protocols', 'protocol accessed'),
            ),"""
new = """_s(NURSE, 'POST /nurse/api/protocols', 'protocol accessed'),
                _s(NURSE, 'GET /nurse/api/protocols', 'protocol list retrieved'),
                _s(NURSE, 'POST /nurse/api/protocols', 'protocol search performed'),
            ),"""
content = content.replace(old, new)

with open('tools/scenario_gen/templates.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done')