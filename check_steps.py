with open('tools/scenario_gen/templates.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find templates with less than 3 steps
import re
lines = content.split('\n')
current_key = None
step_count = 0

for i, line in enumerate(lines):
    # Detect template key
    if 'key=' in line and 'Template(' in content[max(0,i-200):i]:
        match = re.search(r"key='([^']+)'", line)
        if match:
            if current_key and step_count < 3:
                print(f'{current_key}: {step_count} steps')
            current_key = match.group(1)
            step_count = 0
    if '_s(' in line and current_key:
        step_count += 1
    # Detect end of steps (closing of steps tuple)
    if '),' in line and step_count > 0 and step_count < 3:
        # Check if next line has another _s or if this is the end
        if i + 1 < len(lines) and '_s(' not in lines[i+1] and ')' in lines[i+1]:
            if current_key:
                print(f'{current_key}: {step_count} steps')
            step_count = 0
            current_key = None

# Also check for templates with 2 steps at the end
if current_key and step_count < 3:
    print(f'{current_key}: {step_count} steps')