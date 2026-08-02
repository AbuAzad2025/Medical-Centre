"""Remove duplicate local 'from app.extensions import db' lines from files that already have it at top-level."""

import os

scan_dirs = ['routes', 'services', 'app', 'utils']
fixed = 0
for scan_dir in scan_dirs:
    for root, dirs, files in os.walk(scan_dir):
        for f in files:
            if not f.endswith('.py'):
                continue
            fp = os.path.join(root, f)
            with open(fp, encoding='utf-8') as fh:
                lines = fh.readlines()
            # Check if top-level import exists
            has_top_level = any(
                line.strip() == 'from app.extensions import db'
                and not line.startswith(' ')
                and not line.startswith('\t')
                for line in lines
            )
            if not has_top_level:
                continue
            # Remove local (indented) imports of the same
            new_lines = []
            removed = 0
            for line in lines:
                stripped = line.strip()
                if stripped == 'from app.extensions import db' and (
                    line.startswith('    ') or line.startswith('\t')
                ):
                    removed += 1
                    continue
                new_lines.append(line)
            if removed > 0:
                with open(fp, 'w', encoding='utf-8') as fh:
                    fh.writelines(new_lines)
                print(f'Removed {removed} local db imports from {fp}')
                fixed += 1
print(f'Total files fixed: {fixed}')
