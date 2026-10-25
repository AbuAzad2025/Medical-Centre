import json

with open('frontend_endpoints.json', encoding='utf-8') as f:
    fe = json.load(f)
frontend_endpoints = set(fe)

with open('backend_routes_complete.json', encoding='utf-8') as f:
    backend_routes = json.load(f)

backend_endpoints = {r['endpoint']: r for r in backend_routes}

# Check matches
common = frontend_endpoints & set(backend_endpoints.keys())
missing = frontend_endpoints - set(backend_endpoints.keys())
extra = set(backend_endpoints.keys()) - frontend_endpoints

print(f"Frontend endpoints: {len(frontend_endpoints)}")
print(f"Backend endpoints: {len(backend_endpoints)}")
print(f"Common endpoints: {len(common)}")
print(f"Frontend missing in backend: {len(missing)}")
print(f"Backend unused in frontend: {len(extra)}")

print("\n=== Frontend endpoints NOT in backend ===")
for ep in sorted(missing):
    print(f"  MISSING: {ep}")

print("\n=== Backend endpoints NOT in frontend (first 50) ===")
for ep in sorted(list(extra)[:50]):
    be = backend_endpoints[ep]
    print(f"  UNUSED: {be['rule']} ({be['methods']}) [{be['endpoint']}]")

if len(extra) > 50:
    print(f"  ... and {len(extra) - 50} more")

print(f"\nTotal frontend endpoints: {len(frontend_endpoints)}")
print(f"Total backend endpoints: {len(backend_endpoints)}")
print(f"Common endpoints: {len(common)}")
print(f"Missing in backend: {len(missing)}")
print(f"Unused in frontend: {len(extra)}")