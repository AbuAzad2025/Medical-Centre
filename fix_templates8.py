with open('tools/scenario_gen/templates.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix MANAGER_USER_DEPT_MANAGEMENT - add 3rd step
old = """_s(MANAGER, 'POST /manager/user-management', 'user managed'),
                _s(MANAGER, 'POST /manager/departments', 'department managed'),
            ),"""
new = """_s(MANAGER, 'POST /manager/user-management', 'user managed'),
                _s(MANAGER, 'POST /manager/departments', 'department managed'),
                _s(MANAGER, 'GET /manager/user-management', 'verify user managed'),
            ),"""
content = content.replace(old, new)

# Fix API_SAAS_REGISTER_PREFERENCES - add /api/saas/ and /api/user/ to clinical routes in test
# Instead, let's change the family to platform and add the routes to platform_prefixes in test
# But easier: change family back to platform and add /api/saas/, /api/user/ to platform_prefixes
# Let's change the family to platform and add the routes to test
old2 = """key='API_SAAS_REGISTER_PREFERENCES',
            family='clinical',"""
new2 = """key='API_SAAS_REGISTER_PREFERENCES',
            family='platform',"""
content = content.replace(old2, new2)

with open('tools/scenario_gen/templates.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done')