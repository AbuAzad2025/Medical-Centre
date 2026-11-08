import json
d = json.load(open('coverage/coverage-final.json', 'r', encoding='utf-8'))
for path, f in d.items():
    low = path.lower().replace('\\', '/')
    name = low.rsplit('/', 1)[-1]
    if name in ('system_backup.js', 'system_config.js', 'process.js') and 'pages' in low:
        b = f.get('b', {})
        bm = f.get('branchMap', {})
        miss = []
        for k, node in bm.items():
            vals = b.get(k)
            arr = vals if isinstance(vals, list) else [vals]
            if any(x == 0 for x in arr):
                miss.append((node.get('line'), vals))
        miss.sort(key=lambda x: x[0])
        print('===', name, len(miss), 'missing ===')
        print(', '.join(str(ln) for ln, _ in miss))
