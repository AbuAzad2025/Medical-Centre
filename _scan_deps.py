"""Scan all cross-module url_for references in templates."""
import os, re

os.chdir(r'D:\Data\MED-2-7-2025\medical_system')

# Manually define module->blueprints based on module_route_map
module_bps = {
    'reception': ['reception'],
    'doctor': ['doctor', 'vaccination', 'referral', 'pathway', 'cds', 'patient_education', 'telemedicine', 'clinical_coding'],
    'lab': ['lab'],
    'radiology': ['radiology', 'dicom'],
    'pharmacy': ['medication'],
    'emergency': ['emergency'],
    'nursing': ['nurse', 'emar', 'bed', 'or', 'nursing_assessment'],
    'billing': ['finance', 'accountant', 'payment'],
    'inventory': ['barcode'],
    'appointments': ['booking'],
    'reporting': ['manager', 'report_builder', 'data_warehouse', 'pop_health', 'quality', 'what_if'],
    'owner': ['owner', 'super_admin'],
    'portal': ['portal'],
    'ai_imaging': ['ai_imaging'],
    'integration': ['fhir', 'sso'],
}
core_bps = ['main', 'auth', 'security', 'mfa', 'backup', 'backup_restore', 'biometric']

# Reverse: blueprint -> module
bp_to_module = {}
for mod, bps in module_bps.items():
    for bp in bps:
        bp_to_module[bp] = mod

total = 0
unguarded = []
owner_paths = ('owner', 'super_admin', 'auth', 'security')

for root, dirs, files in os.walk('templates'):
    for f in files:
        if not f.endswith('.html'):
            continue
        path = os.path.join(root, f)
        rel = os.path.relpath(path, 'templates').replace('\\', '/')
        parts = rel.split('/')
        owner_mod = parts[0]
        if owner_mod in ('partials',):
            continue
        if owner_mod in owner_paths or owner_mod in core_bps:
            continue
        
        # Resolve template's OWNER module from its directory name
        # e.g., "booking" → appointments, "nurse" → nursing, "accountant" → billing
        template_mod = bp_to_module.get(owner_mod, owner_mod)
        if template_mod in core_bps or template_mod == 'owner':
            continue
        
        with open(path, encoding='utf-8') as fh:
            lines = fh.readlines()
        
        for i, line in enumerate(lines, 1):
            for m in re.finditer(r"url_for\s*\(\s*['\"]([\w.]+)['\"]", line):
                endpoint = m.group(1)
                if '.' not in endpoint:
                    continue
                bp_name = endpoint.split('.')[0]
                target_mod = bp_to_module.get(bp_name)
                if target_mod is None:
                    continue
                # Skip same-module and core references
                if target_mod == template_mod:
                    continue
                if bp_name in core_bps:
                    continue
                
                # Check if line itself has module_active guard
                if 'module_active' in line:
                    continue
                # Check nearby lines for module_active
                nearby = ''.join(lines[max(0,i-3):i])
                if 'module_active' in nearby:
                    continue
                
                unguarded.append((rel, i, line.strip()[:100], bp_name, owner_mod, target_mod))

print(f'=== ALL UNGUARDED CROSS-MODULE TEMPLATE REFERENCES ===')
unguarded.sort(key=lambda x: (x[5], x[3]))
for rel, lineno, text, bp, owner, target in unguarded:
    print(f'  {rel}:{lineno}  [{owner}] -> {bp}. ({target})  "{text}"')

print(f'\nTotal: {len(unguarded)}')
