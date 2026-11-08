with open('static/js/pages/doctor/notes.js', encoding='utf-8') as f:
    lines = f.read().splitlines()
with open('notes_b.txt', 'w', encoding='utf-8') as out2:
    for i in range(33, 127):
        out2.write(str(i+1) + ': ' + lines[i][:230] + '\n')
print('B written')
