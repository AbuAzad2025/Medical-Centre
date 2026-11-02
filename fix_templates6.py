with open('tools/scenario_gen/templates.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix LAB_BARCODE_PRINT_SCAN - add 3rd step
old = """_s(LAB, 'POST /lab/barcode/print/<request_id>', 'barcode printed'),
                _s(LAB, 'POST /lab/barcode/scan/<barcode>', 'sample scanned'),
            ),"""
new = """_s(LAB, 'POST /lab/barcode/print/<request_id>', 'barcode printed'),
                _s(LAB, 'POST /lab/barcode/scan/<barcode>', 'sample scanned'),
                _s(LAB, 'GET /lab/barcode/print/<request_id>', 'verify barcode printed'),
            ),"""
content = content.replace(old, new)

# Fix API_SAAS_REGISTER_PREFERENCES - change family to platform
old2 = """key='API_SAAS_REGISTER_PREFERENCES',
            family='clinical',"""
new2 = """key='API_SAAS_REGISTER_PREFERENCES',
            family='platform',"""
content = content.replace(old2, new2)

with open('tools/scenario_gen/templates.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done')