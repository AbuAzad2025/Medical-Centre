import json
import re

with open('frontend_endpoints.json', encoding='utf-8') as f:
    frontend_endpoints = set(json.load(f))

with open('backend_routes_complete.json', encoding='utf-8') as f:
    backend_routes = json.load(f)

backend_endpoints_map = {r['endpoint']: r for r in backend_routes}

common = frontend_endpoints & set(r['endpoint'] for r in backend_routes)

print("=== URL PATTERN VERIFICATION ===")
for ep in sorted(common):
    be = [r for r in backend_routes if r['endpoint'] == ep][0]
    be_rule = be['rule']
    params = re.findall(r'<[^:]+:([^>]+)>', be_rule)
    if params:
        print(f'{ep}: {be_rule} -> params: {params}')
    else:
        print(f'{ep}: {be_rule} (no params)')