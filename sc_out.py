lines = open('static/js/pages/super_admin/system_config.js', encoding='utf-8').read().splitlines()
with open('sc_out.txt', 'w', encoding='utf-8') as f:
    for i, line in enumerate(lines, 1):
        if i in [10,11,12,23,34,59,64,68,78,82,86,104,122,127,134,156,165,180,182,183,184,186,187,194,204,208,215,220,223,225,239,240]:
            f.write(str(i) + ': ' + line[:200] + '\n')
print('ok')
