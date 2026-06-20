import re, os

def fix_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # Pattern 1: except Exception: ... pass
    content = re.sub(
        r'(except\s+Exception\s*:)(\s*?\n\s*pass)',
        r'\1\n        logging.warning(f"Error in {__name__}: {e}")',
        content,
        flags=re.MULTILINE | re.DOTALL
    )
    
    # Pattern 2: except: ... pass (bare except)
    content = re.sub(
        r'(except\s*:)(\s*?\n\s*pass)',
        r'\1\n        logging.warning(f"Error in {__name__}: {e}")',
        content,
        flags=re.MULTILINE | re.DOTALL
    )
    
    if content != original:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
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