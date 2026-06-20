import re, os

def fix_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Pattern: except Exception: (or except:) followed by optional blank lines then pass
    # We need to replace the pass with proper logging at the correct indent level
    
    def replace_pass(match):
        except_line = match.group(1)  # the "except ..." line with its indent
        pass_line = match.group(2)    # the "pass" line
        # The indent of the pass line tells us the block indent
        block_indent = re.match(r'^(\s*)', pass_line).group(1)
        # The logging line should be one level deeper
        log_indent = block_indent + '    '
        log_line = f'{log_indent}logging.warning(f"Error in {{__name__}}: {{e}}")'
        return except_line + '\n' + log_line + '\n'
    
    # Match: except line, then any whitespace/empty lines, then pass line
    pattern = r'(^(\s*)except\s+(?:Exception\s*)?:\n)((?:\s*\n)*)(\s*pass\s*\n)'
    
    new_content = re.sub(pattern, replace_pass, content, flags=re.MULTILINE)
    
    if new_content != content:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
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