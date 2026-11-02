with open('tools/scenario_gen/templates.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Process line by line to make precise edits
new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    new_lines.append(line)
    
    # Fix RECEPTION_EMERGENCY_DEBT_FORCE_ENTRY - add 3rd step after the 2nd step
    if "_s(RECEPTION, 'POST /reception/queue/approve-force-entry/<ticket_id>', 'force entry approved')," in line:
        # Next line should be the closing of steps
        if i + 1 < len(lines) and "            )," in lines[i + 1]:
            new_lines.append("                _s(RECEPTION, 'POST /reception/queue/approve-emergency-debt/<ticket_id>', 'verify approval recorded'),\n")
    
    # Fix MANAGER_SETTINGS_WHAT_IF - change family to clinical
    if "key='MANAGER_SETTINGS_WHAT_IF'," in line:
        # Next line should be family
        if i + 1 < len(lines) and "family='platform'," in lines[i + 1]:
            new_lines[-1] = line  # Keep the key line
            new_lines.append("            family='clinical',\n")
            i += 1  # Skip the platform line
            continue
    
    # Fix API_SAAS_REGISTER_PREFERENCES - change family to clinical
    if "key='API_SAAS_REGISTER_PREFERENCES'," in line:
        if i + 1 < len(lines) and "family='platform'," in lines[i + 1]:
            new_lines[-1] = line  # Keep the key line
            new_lines.append("            family='clinical',\n")
            i += 1  # Skip the platform line
            continue
    
    i += 1

with open('tools/scenario_gen/templates.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('Done')