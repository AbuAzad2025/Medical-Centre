import json
d = json.load(open('coverage/coverage-final.json', 'r', encoding='utf-8'))
total = cov = 0
rows = []
for path, f in d.items():
    s = f['s']
    t = len(s); c = sum(1 for v in s.values() if v > 0)
    total += t; cov += c
    if c < t:
        rows.append((t - c, c, t, path.replace('D:/recovers/data/medical/', '').replace('\\', '/')))
rows.sort(key=lambda x: -x[0])
print('TOTAL statements:', total)
print('Covered statements:', cov)
print('Overall coverage: %.2f%%' % (100 * cov / total))
print()
print('Files still below 90% statement coverage (miss, pct):')
below = [r for r in rows if 100 * r[1] / r[2] < 90]
for miss, c, t, p in below:
    print('%5.1f%%  %4d missed  %s' % (100 * c / t, miss, p))
print()
print('Files above or at 90%:', len(d) - len(below), '/', len(d))
