with open('tools/scenario_gen/templates.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix RECEPTION_SURVEY_FEEDBACK - add 2 more steps
old = """_s(RECEPTION, 'POST /reception/survey/<token>', 'survey submitted'),
            ),"""
new = """_s(RECEPTION, 'POST /reception/survey/<token>', 'survey submitted'),
                _s(RECEPTION, 'GET /reception/survey/<token>', 'survey details retrieved'),
                _s(RECEPTION, 'POST /reception/survey/<token>', 'survey response recorded'),
            ),"""
content = content.replace(old, new)

with open('tools/scenario_gen/templates.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done')