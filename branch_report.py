import json, sys
d = json.load(open('coverage/coverage-final.json', 'r', encoding='utf-8'))
rows = []
for path, f in d.items():
    low = path.replace('\\', '/')
    norm = low.replace('D:/recovers/data/medical/static/js/', '')
    b = f.get('b', {})
    bm = f.get('branchMap', {})
    tot = sum(len(v if isinstance(v, list) else [v]) for v in b.values())
    if tot == 0:
        continue
    c = sum(sum(1 for x in (v if isinstance(v, list) else [v]) if x > 0) for v in b.values())
    miss = []
    for k, node in bm.items():
        vals = b.get(k)
        arr = vals if isinstance(vals, list) else [vals]
        if any(x == 0 for x in arr):
            miss.append(node.get('line'))
    miss.sort(key=lambda x: (x if isinstance(x, int) else 0))
    rows.append((c, tot, 100 * c / tot, norm, miss))
rows.sort(key=lambda x: x[2])
limit = float(sys.argv[1]) if len(sys.argv) > 1 else 90.0
for c, t, pct, p, miss in rows:
    if pct < limit:
        print('%5.1f%%  %4d/%-4d  %s' % (pct, c, t, p))
