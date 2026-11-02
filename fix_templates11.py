with open('tools/scenario_gen/templates.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix NURSING_ASSESSMENT_NEW - add 2 more steps
old = """_s(NURSE, 'POST /nursing-assessment/new/<patient_id>', 'assessment created'),
            ),"""
new = """_s(NURSE, 'POST /nursing-assessment/new/<patient_id>', 'assessment created'),
                _s(NURSE, 'GET /nursing-assessment/new/<patient_id>', 'assessment details retrieved'),
                _s(NURSE, 'POST /nursing-assessment/new/<patient_id>', 'assessment updated'),
            ),"""
content = content.replace(old, new)

with open('tools/scenario_gen/templates.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done')