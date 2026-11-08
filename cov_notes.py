import json
d = json.load(open('coverage/coverage-final.json', 'r', encoding='utf-8'))
target = 'D:\\recovers\\data\\medical\\static\\js\\pages\\doctor\\notes.js'
f = d[target]
b = f.get('b', {})
bm = f.get('branchMap', {})
tot = sum(len(v if isinstance(v, list) else [v]) for v in b.values())
c = sum(sum(1 for x in (v if isinstance(v, list) else [v]) if x > 0) for v in b.values())
print('branch: %d/%d = %.1f%%' % (c, tot, 100 * c / tot))
for k, loc in bm.items():
    vals = b.get(k)
    arr = vals if isinstance(vals, list) else [vals]
    if any(x == 0 for x in arr):
        print('MISS line', loc.get('line'), 'vals', arr, 'type', loc.get('type'))
