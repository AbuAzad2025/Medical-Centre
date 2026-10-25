import re, json

# Read the base.html content
with open('templates/base.html', encoding='utf-8') as f:
    content = f.read()

# Find the window.API_ROUTES object
match = re.search(r'window\.API_ROUTES\s*=\s*({.*?})\s*;', content, re.DOTALL)
if not match:
    print("Could not find API_ROUTES")
    exit(1)

api_routes_str = match.group(1)

# Convert JS object to valid JSON
def js_to_json(js_str):
    # Step 1: Quote unquoted keys
    s = re.sub(r'(\w+)\s*:', r'"\1":', js_str)
    # Step 2: Replace single quotes with double quotes
    s = re.sub(r"'([^']*)'", r'"\1"', s)
    # Step 3: Remove trailing commas before } or ]
    s = re.sub(r',\s*([}\]])', r'\1', s)
    # Step 4: Handle template literals like `...` - replace with placeholder
    s = re.sub(r'`[^`]*`', '"TEMPLATE_LITERAL"', s)
    return s

fixed_json = js_to_json(api_routes_str)

try:
    api_routes = json.loads(fixed_json)
except json.JSONDecodeError as e:
    print(f"JSON parse error: {e}")
    # Fallback: extract key-value pairs manually
    api_routes = {}
    pairs = re.findall(r'(\w+)\s*:\s*([^,\}]+)', api_routes_str)
    for k, v in pairs:
        api_routes[k.strip()] = v.strip().strip('\'"')

with open('frontend_api_routes.json', 'w', encoding='utf-8') as f:
    json.dump(api_routes, f, ensure_ascii=False, indent=2)

print(f'Found {len(api_routes)} API routes in frontend')
for k, v in sorted(api_routes.items()):
    print(f'  {k}: {v}')