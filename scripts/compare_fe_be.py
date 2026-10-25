import re, json

# Extract API_ROUTES from base.html
with open('templates/base.html', encoding='utf-8') as f:
    content = f.read()

# Extract the window.API_ROUTES object
match = re.search(r'window\.API_ROUTES\s*=\s*({.*?})\s*;', content, re.DOTALL)
if match:
    api_routes_str = match.group(1)
    # Convert JS object to valid JSON
    api_routes_str = re.sub(r"'([^']+)':", r'"\1":', api_routes_str)
    api_routes_str = re.sub(r',\s*([}\]])', r'\1', api_routes_str)
    api_routes_str = re.sub(r',\s*}', '}', api_routes_str)
    api_routes_str = re.sub(r',\s*]', ']', api_routes_str)
    
    try:
        api_routes = json.loads(api_routes_str)
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        api_routes_str = re.sub(r'(\w+):', r'"\1":', api_routes_str)
        api_routes_str = re.sub(r',\s*([}\]])', r'\1', api_routes_str)
        try:
            api_routes = json.loads(api_routes_str)
        except json.JSONDecodeError as e2:
            print(f"Still failing: {e2}")
            api_routes = {}
            pairs = re.findall(r'(\w+)\s*:\s*([^,\}]+)', api_routes_str)
            for k, v in pairs:
                api_routes[k.strip()] = v.strip().strip('\'"')
    
    with open('frontend_api_routes.json', 'w', encoding='utf-8') as f:
        json.dump(api_routes, f, ensure_ascii=False, indent=2)
    
    print(f'Found {len(api_routes)} API routes in frontend')
    for k, v in sorted(api_routes.items()):
        print(f'  {k}: {v}')

# Also load backend routes
with open('backend_routes_complete.json', encoding='utf-8') as f:
    backend_routes = json.load(f)

# Build backend route map
backend_routes_map = {}
for r in backend_routes:
    rule = r['rule']
    normalized = re.sub(r'<[^:]+:([^>]+)>', r'{\1}', rule)
    backend_routes_map[normalized] = {
        'methods': r['methods'],
        'endpoint': r['endpoint'],
        'blueprint': r['blueprint'],
        'original_rule': r['rule']
    }

# Now compare
frontend_routes = {}
with open('frontend_api_routes.json', encoding='utf-8') as f:
    frontend_routes = json.load(f)

print("=== COMPARISON REPORT ===\n")

# 1. Frontend routes not in backend
print("=== FRONTEND ROUTES NOT IN BACKEND ===")
frontend_not_in_backend = []
for fr_route, fr_value in frontend_routes.items():
    normalized_fr = re.sub(r'/0(?=/|$)', '/{id}', fr_value)
    normalized_fr = re.sub(r'__MODULE__', '{module}', normalized_fr)
    normalized_fr = normalized_fr.rstrip('/')
    
    found = False
    for be in backend_routes:
        be_normalized = re.sub(r'<[^:]+:([^>]+)>', r'{\1}', be['rule']).rstrip('/')
        if be_normalized == normalized_fr:
            found = True
            break
    if not found:
        frontend_not_in_backend.append((fr_route, normalized_fr))

if frontend_not_in_backend:
    for route, norm in frontend_not_in_backend[:30]:
        print(f'  MISSING: {route} -> {norm}')
else:
    print("  All frontend routes found in backend!")

print()

# 2. Backend routes not used in frontend
print("=== BACKEND ROUTES NOT USED IN FRONTEND ===")
backend_not_in_frontend = []
for be in backend_routes:
    be_normalized = re.sub(r'<[^:]+:([^>]+)>', r'{\1}', be['rule']).rstrip('/')
    found = False
    for fr_key, fr_value in frontend_routes.items():
        normalized_fr = re.sub(r'/0(?=/|$)', '/{id}', fr_value)
        normalized_fr = re.sub(r'__MODULE__', '{module}', normalized_fr)
        normalized_fr = normalized_fr.rstrip('/')
        if be_normalized == normalized_fr:
            found = True
            break
    if not found:
        backend_not_in_frontend.append((be['rule'], be['endpoint'], be['methods']))

for rule, endpoint, methods in backend_not_in_frontend[:50]:
    print(f'  UNUSED: {rule} ({methods}) [{endpoint}]')

if len(backend_not_in_frontend) > 50:
    print(f'  ... and {len(backend_not_in_frontend) - 50} more')

print()
print(f'Total backend routes: {len(backend_routes)}')
print(f'Frontend API_ROUTES: {len(frontend_routes)}')
print(f'Backend unused in frontend: {len(backend_not_in_frontend)}')
print(f'Frontend missing in backend: {len(frontend_not_in_backend)}')