#!/usr/bin/env python3
"""
Frontend Asset & Inheritance Audit — standalone, no DB.
Generates workspace discovery, inheritance matrix, orphan list, contrast report.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = ROOT / "templates"
STATIC_DIR = ROOT / "static"

RE_URL_FOR_STATIC = re.compile(r"url_for\(\s*['\"]static['\"]\s*,\s*filename\s*=\s*['\"]([^'\"]+)['\"]\s*\)")
RE_EXTENDS = re.compile(r"{%\s*extends\s+['\"]([^'\"]+)['\"]")
RE_INCLUDE = re.compile(r"{%\s*include\s+['\"]([^'\"]+)['\"]")
RE_IMPORT = re.compile(r"{%\s*(?:import|from)\s+['\"]([^'\"]+)['\"]")
RE_BLOCK = re.compile(r"{%\s*block\s+(\w+)\s*%}")

def scan():
    templates = sorted(TEMPLATES_DIR.rglob("*.html"))
    static_css = sorted((STATIC_DIR / "css").glob("*.css")) if (STATIC_DIR / "css").exists() else []
    static_js = list((STATIC_DIR / "js").rglob("*.js"))
    print(f"Templates: {len(templates)}")
    print(f"CSS files: {len(static_css)} -> {[p.name for p in static_css]}")
    print(f"JS files: {len(static_js)}")
    # Check existence
    missing = []
    referenced = set()
    for tmpl in templates:
        t = tmpl.read_text(encoding="utf-8", errors="ignore")
        for ref in RE_URL_FOR_STATIC.findall(t):
            referenced.add(ref)
            if not (STATIC_DIR / ref.split("?")[0]).exists():
                missing.append(f"{tmpl.relative_to(ROOT)} -> {ref}")
    print(f"Referenced static assets: {len(referenced)}")
    if missing:
        print("Missing:")
        for m in missing[:20]:
            print(" ", m)
    else:
        print("All url_for static refs exist: OK")
    # Duplicate check along chains
    tmpl_texts = {p.relative_to(TEMPLATES_DIR).as_posix(): p.read_text(encoding="utf-8", errors="ignore") for p in templates}
    dups = 0
    for rel, txt in tmpl_texts.items():
        parent = RE_EXTENDS.search(txt)
        if parent:
            par = parent.group(1)
            # check duplicate css between child and parent
            child_css = {x for x in RE_URL_FOR_STATIC.findall(txt) if x.endswith(".css")}
            if par in tmpl_texts:
                par_css = {x for x in RE_URL_FOR_STATIC.findall(tmpl_texts[par]) if x.endswith(".css")}
                overlap = child_css & par_css
                if overlap:
                    print(f"DUP CSS {rel} -> {par}: {overlap}")
                    dups += 1
    if dups == 0:
        print("No duplicate CSS along inheritance: OK")
    # Orphans
    all_static = {p.relative_to(STATIC_DIR).as_posix() for p in STATIC_DIR.rglob("*") if p.is_file() and not p.name.startswith(".")}
    orphans = [f for f in all_static if f.startswith("css/") or f.startswith("js/")]
    # filter referenced
    orphans = [f for f in orphans if f not in referenced and not any(f.startswith(x) for x in ["vendor/", "img/"])]
    print(f"Potential orphan css/js: {len(orphans)}")
    for o in orphans[:20]:
        print(" ", o)
    # Blocks
    for rel, txt in list(tmpl_texts.items())[:5]:
        blocks = RE_BLOCK.findall(txt)
        if blocks:
            print(f"{rel} blocks: {blocks} extends={RE_EXTENDS.search(txt).group(1) if RE_EXTENDS.search(txt) else '-'} includes={len(RE_INCLUDE.findall(txt))}")

    # Matrix sample
    print("\n| Template Path | Parent | Blocks | CSS Loaded | JS Loaded | Risk |")
    print("|---|---|---|---|---|---|")
    samples = ["base.html", "reception/patients.html", "reception/create_visit.html", "doctor/patient_queue.html", "lab/process.html", "super_admin/users.html", "emergency/dashboard_new.html"]
    for s in samples:
        p = TEMPLATES_DIR / s
        if not p.exists():
            continue
        t = p.read_text(encoding="utf-8", errors="ignore")
        parent = RE_EXTENDS.search(t).group(1) if RE_EXTENDS.search(t) else "-"
        blocks = ",".join(RE_BLOCK.findall(t)[:3])
        css = ",".join([x.split("/")[-1] for x in RE_URL_FOR_STATIC.findall(t) if x.endswith(".css")][:2])
        js = ",".join([x.split("/")[-1] for x in RE_URL_FOR_STATIC.findall(t) if x.endswith(".js")][:2])
        print(f"| {s} | {parent} | {blocks or '-'} | {css or '-'} | {js or '-'} | - |")

if __name__ == "__main__":
    scan()
