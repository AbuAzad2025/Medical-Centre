import os, re, json

def main(ctx):
    routes_dir = "D:/Data/MED-2-7-2025/medical_system/routes"
    templates_dir = "D:/Data/MED-2-7-2025/medical_system/templates"

    # 1. Get all owner templates
    owner_templates = set()
    owner_dir = os.path.join(templates_dir, "owner")
    if os.path.isdir(owner_dir):
        for f in os.listdir(owner_dir):
            if f.endswith('.html'):
                owner_templates.add(f)

    # 2. Scan all route files for render_template calls
    used_owner_templates = {}  # template -> [(file, line)]
    missing_templates = {}  # template -> [(file, line)]
    all_rendered_templates = {}  # template -> [(file, line)]

    render_re = re.compile(r"render_template\s*\(\s*['\"]([^'\"]+)['\"]", re.MULTILINE | re.DOTALL)

    for root, dirs, files in os.walk(routes_dir):
        for fname in files:
            if not fname.endswith('.py'):
                continue
            fpath = os.path.join(root, fname)
            rel = os.path.relpath(fpath, routes_dir).replace(os.sep, '/')
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            for match in render_re.finditer(content):
                tmpl = match.group(1)
                line_num = content[:match.start()].count('\n') + 1
                all_rendered_templates.setdefault(tmpl, []).append((rel, line_num))
                if tmpl.startswith('owner/'):
                    tname = tmpl.split('owner/')[1]
                    used_owner_templates.setdefault(tname, []).append((rel, line_num))
                # Check if template exists - normalize path separators
                tmpl_path = os.path.normpath(os.path.join(templates_dir, tmpl))
                if not os.path.exists(tmpl_path):
                    missing_templates.setdefault(tmpl, []).append((rel, line_num))

    # Collect saas templates
    saas_templates = {}
    for t, refs in all_rendered_templates.items():
        saas_refs = [r for r in refs if r[0] == 'saas_routes.py']
        if saas_refs:
            saas_templates[t] = saas_refs

    # Collect super_admin templates
    super_admin_templates = {}
    for t, refs in all_rendered_templates.items():
        sa_refs = [r for r in refs if r[0].startswith('super_admin/')]
        if sa_refs:
            super_admin_templates[t] = sa_refs

    # Collect all rendered templates with existence info
    all_templates = {}
    for t, refs in all_rendered_templates.items():
        exists = os.path.exists(os.path.normpath(os.path.join(templates_dir, t)))
        all_templates[t] = {
            "exists": exists,
            "refs": refs
        }

    return {
        "owner_templates": sorted(owner_templates),
        "used_owner": {k: v for k, v in used_owner_templates.items()},
        "unused_owner": sorted(owner_templates - set(used_owner_templates.keys())),
        "missing_templates": {k: v for k, v in missing_templates.items()},
        "saas_templates": saas_templates,
        "super_admin_templates": super_admin_templates,
        "all_templates_count": len(all_templates),
    }
