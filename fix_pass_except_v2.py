import re, os

def fix_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    modified = False
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Match "except Exception:" or "except:" with optional spaces
        if re.match(r'^(\s*)except\s+(?:Exception\s*)?:', line):
            indent = re.match(r'^(\s*)', line).group(1)
            # Look ahead for "pass" at the next non-empty line
            j = i + 1
            while j < len(lines) and lines[j].strip() == '':
                j += 1
            if j < len(lines) and lines[j].strip() == 'pass':
                # Replace the "pass" line with logging
                lines[j] = f'{indent}    logging.warning(f"Error in {__name__}: {e}")\n'
                modified = True
                i = j + 1
                continue
        
        i += 1
    
    if modified:
        with open(path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        return True
    return False

fixed_count = 0
for root, dirs, files in os.walk('routes'):
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            if fix_file(path):
                fixed_count += 1
                print(f'Fixed: {path}')

print(f'Total files fixed: {fixed_count}')