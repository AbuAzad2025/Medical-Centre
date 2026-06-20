with open(r'D:\Data\MED-2-7-2025\medical_system\routes\auth_routes.py', 'r', encoding='utf-8') as f:
    content = f.read()
idx = content.find('def login')
if idx >= 0:
    print(content[idx:idx+300])