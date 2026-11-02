with open('tools/scenario_gen/templates.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix RECEPTION_NO_SHOW_HANDLING - add a 3rd step after GET /reception/no-shows
old = """_s(RECEPTION, 'GET /reception/no-shows', 'list no-show appointments'),
            ),"""
new = """_s(RECEPTION, 'GET /reception/no-shows', 'list no-show appointments'),
                _s(RECEPTION, 'POST /reception/appointments/<appointment_id>/no-show', 'verify no-show recorded'),
            ),"""
content = content.replace(old, new)

# Fix MANAGER_SETTINGS_WHAT_IF - change family to clinical
old2 = """key='MANAGER_SETTINGS_WHAT_IF',
            family='platform',"""
new2 = """key='MANAGER_SETTINGS_WHAT_IF',
            family='clinical',"""
content = content.replace(old2, new2)

# Fix API_SAAS_REGISTER_PREFERENCES - change family to clinical
old3 = """key='API_SAAS_REGISTER_PREFERENCES',
            family='platform',"""
new3 = """key='API_SAAS_REGISTER_PREFERENCES',
            family='clinical',"""
content = content.replace(old3, new3)

with open('tools/scenario_gen/templates.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done')