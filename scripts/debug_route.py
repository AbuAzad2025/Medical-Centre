with open('routes/reception/api.py', encoding='utf-8') as f:
    lines = f.readlines()

with open('debug_output.txt', 'w', encoding='utf-8') as out:
    for i, line in enumerate(lines):
        if 'route' in line and '@reception_bp.route' in line:
            out.write(f'Line {i + 1}: {line}')
            for j in range(i - 1, max(-1, i - 10), -1):
                out.write(f'  {j + 1}: {lines[j]}')
            out.write('\n')
