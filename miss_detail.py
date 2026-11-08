import json, sys
d = json.load(open('coverage/coverage-final.json', 'r', encoding='utf-8'))
want = sys.argv[1:]
for path, f in d.items():
    low = path.replace('\\', '/')
    norm = low.replace('D:/recovers/data/medical/static/js/', '')
    if norm in want:
        b = f.get('b', {})
        bm = f.get('branchMap', {})
        miss = []
        for k, node in bm.items():
            vals = b.get(k)
            arr = vals if isinstance(vals, list) else [vals]
            if any(x == 0 for x in arr):
                miss.append((node.get('line'), node.get('type')))
        miss.sort(key=lambda x: (x[0] if isinstance(x[0], int) else 0))
        print('=== %s' % norm)
        for ln, t in miss:
            print('   line', ln, t)
