import re, json

# Read the base.html content
with open('templates/base.html', encoding='utf-8') as f:
    content = f.read()

# Extract endpoint names from url_for calls in API_ROUTES
# Pattern: url_for('endpoint_name' or url_for("endpoint_name")
endpoint_pattern = r"url_for\(['\"]([^'\"]+)['\"]"

endpoints = re.findall(endpoint_pattern, content)

frontend_endpoints = set(endpoints)
print(f"Frontend endpoints found: {len(frontend_endpoints)}")
for ep in sorted(frontend_endpoints):
    print(f"  {ep}")

# Save
with open('frontend_endpoints.json', 'w', encoding='utf-8') as f:
    json.dump(list(frontend_endpoints), f, ensure_ascii=False, indent=2)

# Load backend routes
with open('backend_routes_complete.json', encoding='utf-8') as f:
    backend_routes = json.load(f)

backend_endpoints = set(r['endpoint'] for r in backend_routes)

print(f"\nFrontend endpoints: {len(frontend_endpoints)}")
print(f"Backend endpoints: {len(backend_endpoints)}")

# Find mismatches
missing = frontend_endpoints - backend_endpoints
extra = backend_endpoints - frontend_endpoints

print(f"\n=== Frontend endpoints NOT in backend ===")
for ep in sorted(missing):
    print(f"  MISSING: {ep}")

print(f"\n=== Backend endpoints NOT in frontend ===")
for ep in sorted(list(extra)[:50]):
    print(f"  UNUSED: {ep}")

if len(backend_endpoints) > 50:
    print(f"  ... and {len(extra) - 50} more")

print(f"\nTotal frontend endpoints: {len(frontend_endpoints)}")
print(f"Total backend endpoints: {len(set(r['endpoint'] for r in json.load(open('backend_routes_complete.json', encoding='utf-8'))))}")
print(f"Missing in backend: {len(missing)}")
print(f"Unused in frontend: {len(extra)}")