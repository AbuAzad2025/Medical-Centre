"""Remove duplicate /booking/booking/* routes from route_inventory.json."""
import json

with open('route_inventory.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

original_count = len(data['routes'])

data['routes'] = [
    r for r in data['routes']
    if not r['path'].startswith('/booking/booking')
]

removed = original_count - len(data['routes'])
print(f"Removed {removed} duplicate /booking/booking/* routes")

with open('route_inventory.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"Remaining routes: {len(data['routes'])}")
