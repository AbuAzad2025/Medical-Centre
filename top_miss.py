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
                miss.append(node.get('line'))
        miss.sort(key=lambda x: (x if isinstance(x, int) else 0))
        tot = sum(len(v if isinstance(v, list) else [v]) for v in b.values())
        c = sum(sum(1 for x in (v if isinstance(v, list) else [v]) if x > 0) for v in b.values())
        print('=== %s  %d/%d = %.1f%%' % (norm, c, tot, 100 * c / tot))
        print('miss:', miss)
