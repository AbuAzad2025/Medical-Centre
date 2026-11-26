"""Move per-row modals out of <tbody> (invalid HTML that distorted the table)."""

PATH = 'templates/owner/subscriptions.html'
with open(PATH, encoding='utf-8') as fh:
    text = fh.read()

start = text.index('                {# --- MODALS --- #}')
end = text.index('                {% endfor %}\n            </tbody>', start)
modals = text[start:end]
text = (
    text[:start]
    + '                {% endfor %}\n            </tbody>'
    + text[end + len('                {% endfor %}\n            </tbody>') :]
)

anchor = '        </table>\n    </div>\n</div>'
assert anchor in text
text = text.replace(
    anchor,
    '        </table>\n    </div>\n\n'
    + '    {# Row modals live outside the table body. #}\n'
    + '    {% for t in tenants %}\n'
    + modals.rstrip()
    + '\n    {% endfor %}\n</div>',
)

with open(PATH, 'w', encoding='utf-8', newline='') as fh:
    fh.write(text)
print('moved modals outside tbody')
