"""
Template Audit: Syntax, Structure, Fields, Completeness
"""
import os, sys, re
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ERRORS, WARNINGS, INFOS = [], [], []
def log_error(m): ERRORS.append(m); print(f"\033[91m[ERROR]\033[0m {m}")
def log_warn(m): WARNINGS.append(m); print(f"\033[93m[WARN]\033[0m  {m}")
def log_info(m): INFOS.append(m); print(f"\033[92m[INFO]\033[0m  {m}")


def check_templates():
    from app_factory import create_app
    app = create_app(os.getenv('FLASK_ENV', 'testing'))

    with app.app_context():
        env = app.jinja_env
        template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')

        syntax_errors = []
        no_base = []
        no_csrf = []
        missing_includes = []
        total = 0

        for root, _, files in os.walk(template_dir):
            for f in files:
                if not f.endswith('.html'):
                    continue
                total += 1
                filepath = os.path.join(root, f)
                rel = os.path.relpath(filepath, template_dir)

                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as fh:
                        source = fh.read()
                except Exception as e:
                    syntax_errors.append(f"{rel}: cannot read: {e}")
                    continue

                # 1. Syntax check
                try:
                    env.parse(source)
                except Exception as e:
                    syntax_errors.append(f"{rel}: {e}")
                    continue

                # 2. Check extends base.html (skip base, partials, standalone pages)
                STANDALONE_OK = {'dashboard_base.html', 'auth\\login.html',
                                 'errors\\403.html', 'errors\\404.html', 'errors\\500.html',
                                 'lab\\lab_requests_results_print_standalone.html',
                                 'print\\emergency_report.html', 'print\\invoice.html',
                                 'print\\prescription.html', 'print\\radiology_report.html',
                                 'print\\receipt.html', 'reception\\calls_display.html',
                                 'reception\\survey.html', 'reception\\waiting_display.html',
                                 'super_admin\\roles.html',
                                 'portal\\base.html', 'pwa\\offline.html'}
                if rel not in STANDALONE_OK and not rel.startswith('base') and not rel.startswith('macros') and not rel.startswith('includes') and not rel.startswith('components'):
                    if '{% extends' not in source and '<!DOCTYPE' not in source and '<html' not in source:
                        pass
                    elif '{% extends' not in source:
                        no_base.append(rel)

                # 3. Check for CSRF token in POST forms only
                for fm in re.finditer(r'<form\b[^>]*>', source, re.IGNORECASE):
                    form_tag = fm.group(0).lower()
                    has_method_post = 'method="post"' in form_tag or "method='post'" in form_tag
                    if not has_method_post:
                        continue
                    has_csrf = ('csrf_token' in source or
                                '{{ form.hidden_tag()' in source or
                                "{{ form.csrf_token" in source or
                                "{{ forms.csrf()" in source or
                                "{{ forms.hidden_tag()" in source or
                                'name="csrf_token"' in source)
                    if not has_csrf:
                        no_csrf.append(rel)
                        break

                # 4. Check for undefined macros/includes
                for line in source.split('\n'):
                    if '{% include' in line or '{% from' in line or '{% import' in line:
                        # Basic check — if file reference looks broken
                        if '""' in line or "''" in line:
                            missing_includes.append(f"{rel}: empty include: {line.strip()}")

        print("\n" + "="*70)
        print("[1/4] فحص Syntax — Templates Jinja2")
        print("="*70)
        if syntax_errors:
            for e in syntax_errors[:20]:
                log_error(e)
            if len(syntax_errors) > 20:
                log_error(f"... and {len(syntax_errors)-20} more syntax errors")
        else:
            log_info(f"All {total} templates have valid Jinja2 syntax")

        print("\n" + "="*70)
        print("[2/4] فحص Structure — Extends base.html")
        print("="*70)
        if no_base:
            for t in no_base[:15]:
                log_warn(f"{t} does not extend base layout")
            if len(no_base) > 15:
                log_warn(f"... and {len(no_base)-15} more")
        else:
            log_info("All content templates extend a base layout")

        print("\n" + "="*70)
        print("[3/4] فحص Security — CSRF Token in Forms")
        print("="*70)
        if no_csrf:
            for t in no_csrf[:15]:
                log_warn(f"{t}: <form> without csrf_token")
            if len(no_csrf) > 15:
                log_warn(f"... and {len(no_csrf)-15} more")
        else:
            log_info("All forms include CSRF protection")

        print("\n" + "="*70)
        print("[4/4] فحص Includes/Macros")
        print("="*70)
        if missing_includes:
            for i in missing_includes[:10]:
                log_warn(i)
        else:
            log_info("All includes/macros references look valid")

        print("\n" + "="*70)
        print("الملخص النهائي")
        print("="*70)
        print(f"  Total templates: {total}")
        print(f"  Syntax errors: {len(syntax_errors)}")
        print(f"  Missing base layout: {len(no_base)}")
        print(f"  Missing CSRF: {len(no_csrf)}")
        print(f"  Broken includes: {len(missing_includes)}")
        print(f"\n  {len(ERRORS)} خطأ")
        print(f"  {len(WARNINGS)} تحذير")
        print(f"  {len(INFOS)} معلومة")
        if not ERRORS and not WARNINGS:
            print("\n✅ كل القوالب نظيفة وكاملة")
        sys.exit(1 if ERRORS else 0)


if __name__ == '__main__':
    check_templates()
