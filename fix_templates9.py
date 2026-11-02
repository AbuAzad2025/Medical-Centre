with open('tools/scenario_gen/templates.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix EMERGENCY_EMS_INTAKE - add 2 more steps
old = """_s(EMERGENCY, 'POST /emergency/api/ems/intake', 'EMS intake processed'),
            ),"""
new = """_s(EMERGENCY, 'POST /emergency/api/ems/intake', 'EMS intake processed'),
                _s(EMERGENCY, 'POST /emergency/cases/create', 'emergency case created from intake'),
                _s(EMERGENCY, 'GET /emergency/cases', 'verify case created'),
            ),"""
content = content.replace(old, new)

with open('tools/scenario_gen/templates.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done')