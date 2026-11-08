import json
d = json.load(open('coverage/coverage-final.json', 'r', encoding='utf-8'))
for path, f in d.items():
    if path.endswith('static/js/app.js') or path.endswith('static\\js\\app.js'):
        lines = sorted({f['statementMap'][k]['start']['line'] for k, v in f['s'].items() if v == 0})
        print('uncovered:', lines)
