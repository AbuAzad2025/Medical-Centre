"""Fix remaining weak test passwords."""
import os

replacements = {
    'tests/test_e2e_production_flow.py': [
        ("super_admin.set_password('sapass1')", "super_admin.set_password('ValidPass123!')"),
    ],
    'tests/test_custom_service_lifecycle.py': [
        ("user.set_password('test')", "user.set_password('ValidPass123!')"),
    ],
    'tests/test_platform_tenant_assumption.py': [
        ("u.set_password('test123')", "u.set_password('ValidPass123!')"),
    ],
    'tests/test_pre_pilot_deployment_gates.py': [
        ("u.set_password('short')", "u.set_password('ValidPass123!')"),
    ],
    'tests/test_smart_ai_engine.py': [
        ("u.set_password('x')", "u.set_password('ValidPass123!')"),
        ("d.set_password('x')", "d.set_password('ValidPass123!')"),
    ],
    'tests/test_ux0_tenant_ui.py': [
        ("u.set_password('sa123456')", "u.set_password('ValidPass123!')"),
    ],
    'tests/test_ux1_shell.py': [
        ("u.set_password('owner123')", "u.set_password('ValidPass123!')"),
    ],
}

for fp, reps in replacements.items():
    if not os.path.exists(fp):
        print(f'MISSING: {fp}')
        continue
    with open(fp, 'r', encoding='utf-8') as f:
        content = f.read()
    for old, new in reps:
        content = content.replace(old, new)
    with open(fp, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'Fixed {fp}')
