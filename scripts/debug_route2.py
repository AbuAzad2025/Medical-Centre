with open('routes/reception/api.py', encoding='utf-8') as f:
    lines = f.readlines()

with open('debug_output2.txt', 'w', encoding='utf-8') as out:
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        if '@' in line_stripped and 'route' in line_stripped and '.route(' in line_stripped:
            out.write(f'Line {i + 1}: {line}')
            # Show 20 lines before
            for j in range(i - 1, max(-1, i - 30), -1):
                out.write(f'  {j + 1}: {lines[j]}')
            out.write('\n\n')
