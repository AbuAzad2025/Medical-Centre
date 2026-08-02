import glob
import re

console_pattern = re.compile(r'console\.(log|warn|error|debug)\s*\([^;]*\);?', re.DOTALL)


def repl(m):
    call = m.group(0)
    # Extract first string literal if any
    msg = re.search(r"['\"]([^'\"]+)['\"]", call)
    if msg:
        text = msg.group(1)
        # Simple translation heuristics
        text = text.replace('Error:', 'خطأ:')
        text = text.replace('error', 'خطأ')
        text = text.replace('Failed to', 'فشل')
        text = text.replace('loading', 'تحميل')
        return '/* ' + text + ' */'
    return '/* تم التقاط خطأ */'


for path in glob.glob('static/js/**/*.js', recursive=True):
    with open(path, encoding='utf-8') as f:
        content = f.read()
    new_content = console_pattern.sub(repl, content)
    if new_content != content:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print('Cleaned', path)
