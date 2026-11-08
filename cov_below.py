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
print('Overall: %.2f%%' % (100 * cov / total))
print('Covered statements:', cov, '/', total)
print('Files still below 90%:')
nb = 0
for miss, c, t, p in rows:
    pct = 100 * c / t
    if pct < 90:
        nb += 1
        print('%5.1f%%  %4d missed  %s' % (pct, miss, p))
print('Files below 90%:', nb)
