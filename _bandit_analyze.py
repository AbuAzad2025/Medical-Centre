import json
from collections import Counter

d = json.load(open('bandit-all.json'))
m = d.get('metrics', {}).get('_totals', {})
print('FULL POPULATION (_totals):')
print({k: v for k, v in m.items() if k.startswith(('SEVERITY.', 'CONFIDENCE'))})

ids = {}
for i in d.get('results', []):
    rec = ids.setdefault(i['test_id'], [0, Counter()])
    rec[0] += 1
    rec[1][i['issue_severity']] += 1

print()
print('results count:', len(d.get('results', [])))
print('By test_id: (count, severity-breakdown)')
for tid, rec in sorted(ids.items(), key=lambda x: -x[1][0]):
    print('  %s: %d  %s' % (tid, rec[0], dict(rec[1])))

# severity of reported issues (no filter)
sev = Counter(i['issue_severity'] for i in d.get('results', []))
print()
print('Reported issue severities:', dict(sev))
print('HIGH-severity reported issues:', sev.get('HIGH', 0))
