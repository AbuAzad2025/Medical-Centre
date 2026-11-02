with open('tools/scenario_gen/templates.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix RECEPTION_STAFF_SCHEDULE - add 3rd step
old = """_s(RECEPTION, 'POST /reception/staff/absence', 'absence recorded'),
                _s(RECEPTION, 'POST /reception/staff/schedule', 'schedule updated'),
            ),"""
new = """_s(RECEPTION, 'POST /reception/staff/absence', 'absence recorded'),
                _s(RECEPTION, 'POST /reception/staff/schedule', 'schedule updated'),
                _s(RECEPTION, 'GET /reception/staff/schedule', 'verify schedule updated'),
            ),"""
content = content.replace(old, new)

# Fix RECEPTION_EMERGENCY_DEBT_FORCE_ENTRY - add 3rd step
old2 = """_s(RECEPTION, 'POST /reception/queue/approve-emergency-debt/<ticket_id>', 'emergency debt approved'),
                _s(RECEPTION, 'POST /reception/queue/approve-force-entry/<ticket_id>', 'force entry approved'),
            ),"""
new2 = """_s(RECEPTION, 'POST /reception/queue/approve-emergency-debt/<ticket_id>', 'emergency debt approved'),
                _s(RECEPTION, 'POST /reception/queue/approve-force-entry/<ticket_id>', 'force entry approved'),
                _s(RECEPTION, 'POST /reception/queue/approve-emergency-debt/<ticket_id>', 'verify approval recorded'),
            ),"""
content = content.replace(old2, new2)

with open('tools/scenario_gen/templates.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done')