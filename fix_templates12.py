with open('tools/scenario_gen/templates.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix API_SAAS_REGISTER_PREFERENCES - add 3rd step
old = """_s(SYSTEM, 'POST /api/saas/register', 'tenant registered'),
                _s(SYSTEM, 'POST /api/user/preferences', 'preferences updated'),
            ),"""
new = """_s(SYSTEM, 'POST /api/saas/register', 'tenant registered'),
                _s(SYSTEM, 'POST /api/user/preferences', 'preferences updated'),
                _s(SYSTEM, 'GET /api/user/preferences', 'verify preferences retrieved'),
            ),"""
content = content.replace(old, new)

with open('tools/scenario_gen/templates.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done')