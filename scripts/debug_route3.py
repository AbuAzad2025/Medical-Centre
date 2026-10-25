with open('routes/reception/api.py', encoding='utf-8') as f:
    lines = f.readlines()

with open('debug_output3.txt', 'w', encoding='utf-8') as out:
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        if '@' in line_stripped and 'route' in line_stripped and '.route(' in line_stripped:
            out.write(f'=== Route at Line {i + 1}: {line}')
            # Show 20 lines before AND 10 lines after
            for j in range(max(0, i - 20), min(len(lines), i + 15)):
                prefix = '>>> ' if j == i else '    '
                out.write(f'{prefix} {j + 1}: {lines[j]}')
            out.write('\n\n')
