with open('tools/scenario_gen/templates.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix MEDICATION_EXTERNAL_IMPORT - add 3rd step
old = """_s(PHARMACY, 'POST /medication/api/external-drug-import', 'external drug imported'),
                _s(PHARMACY, 'POST /medication/api/stock/alerts', 'stock alerts checked'),
            ),"""
new = """_s(PHARMACY, 'POST /medication/api/external-drug-import', 'external drug imported'),
                _s(PHARMACY, 'POST /medication/api/stock/alerts', 'stock alerts checked'),
                _s(PHARMACY, 'GET /medication/api/stock/alerts', 'verify stock alerts retrieved'),
            ),"""
content = content.replace(old, new)

# Fix API_SAAS_REGISTER_PREFERENCES - change family to clinical
old2 = """key='API_SAAS_REGISTER_PREFERENCES',
            family='platform',"""
new2 = """key='API_SAAS_REGISTER_PREFERENCES',
            family='clinical',"""
content = content.replace(old2, new2)

with open('tools/scenario_gen/templates.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done')