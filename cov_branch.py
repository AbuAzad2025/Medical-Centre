import json
d = json.load(open('coverage/coverage-final.json', 'r', encoding='utf-8'))
rows = []
for path, f in d.items():
    b = f.get('b', {})
    tot = sum(len(v if isinstance(v, list) else [v]) for v in b.values())
    if tot == 0:
        continue
    c = sum(sum(1 for x in (v if isinstance(v, list) else [v]) if x > 0) for v in b.values())
    rows.append((c, tot, 100 * c / tot, path.replace('D:/recovers/data/medical/', '').replace('\\', '/')))
rows.sort(key=lambda x: x[2])
for c, t, pct, p in rows:
    if pct < 90:
        print('%5.1f%%  %4d/%-4d  %s' % (pct, c, t, p))
