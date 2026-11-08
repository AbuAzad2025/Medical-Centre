with open('static/js/pages/radiology/process.js', encoding='utf-8') as f:
    lines = f.read().splitlines()
with open('proc_tail.txt', 'w', encoding='utf-8') as out:
    for i in range(412, len(lines)):
        out.write('%d: %s\n' % (i + 1, lines[i]))
print('ok', len(lines))
