import subprocess
import re

# Read endpoints from file
with open('endpoints.txt', 'r') as f:
    endpoints = [line.strip() for line in f if line.strip() and line.strip() != 'static']

# Search each endpoint in routes/
results = []
for ep in endpoints:
    # Search for route definition - look for @bp.route or @blueprint.route with endpoint name
    # The endpoint format is typically "blueprint.function_name"
    # We need to search for the function name part
    parts = ep.split('.')
    if len(parts) >= 2:
        blueprint = parts[0]
        function_name = '.'.join(parts[1:])
    else:
        blueprint = ''
        function_name = ep
    
    # Search in routes/ for the endpoint
    # First try searching for the full endpoint as a string
    result = subprocess.run(['rg', '-n', f"endpoint='{ep}'", 'routes/'], capture_output=True, text=True)
    if result.stdout:
        results.append((ep, 'Y', result.stdout.strip().split('\n')[0]))
        continue
    
    # Try searching for function name in route decorator
    result = subprocess.run(['rg', '-n', f"def {function_name}\\(", 'routes/'], capture_output=True, text=True)
    if result.stdout:
        results.append((ep, 'Y', result.stdout.strip().split('\n')[0]))
        continue
    
    # Try searching for @.*route.*function_name
    result = subprocess.run(['rg', '-n', f"@.*route.*{function_name}", 'routes/'], capture_output=True, text=True)
    if result.stdout:
        results.append((ep, 'Y', result.stdout.strip().split('\n')[0]))
        continue
        
    # Try searching for url_prefix + function_name
    result = subprocess.run(['rg', '-n', f"'{function_name}'", 'routes/'], capture_output=True, text=True)
    if result.stdout:
        # Filter to likely route definitions
        for line in result.stdout.strip().split('\n'):
            if 'route' in line.lower() or 'url' in line.lower() or 'def ' in line:
                results.append((ep, 'Y', line))
                break
        else:
            results.append((ep, 'N', ''))
        continue
    
    results.append((ep, 'N', ''))

# Print results
for ep, exists, location in results:
    if exists == 'Y':
        print(f"{ep}, Y, {location}")
    else:
        print(f"{ep}, N, ")

# Save to file
with open('endpoint_check_results.txt', 'w') as f:
    for ep, exists, location in results:
        if exists == 'Y':
            f.write(f"{ep}, Y, {location}\n")
        else:
            f.write(f"{ep}, N,\n")
