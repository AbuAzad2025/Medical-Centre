import json

with open('route_permissions.json', encoding='utf-8') as f:
    perms = json.load(f)

# Categorize by blueprint prefix from the route
bp_counts = {}
bp_roles = {}

for route, roles in perms.items():
    # Determine blueprint from route
    bp = 'other'
    if route.startswith('/api/'):
        # Check if it's a specific API
        if route.startswith('/api/fhir/'):
            bp = 'fhir'
        elif route.startswith('/api/lab/'):
            bp = 'lab_api'
        elif route.startswith('/api/radiology/'):
            bp = 'radiology_api'
        elif route.startswith('/api/billing/'):
            bp = 'billing_api'
        elif route.startswith('/api/saas/'):
            bp = 'saas_api'
        elif route.startswith('/api/lab/') or route.startswith('/api/radiology/'):
            bp = 'clinical_api'
        else:
            bp = 'api'
    elif route.startswith('/reception/'):
        bp = 'reception'
    elif route.startswith('/doctor/'):
        bp = 'doctor'
    elif route.startswith('/emergency/'):
        bp = 'emergency'
    elif route.startswith('/lab/'):
        bp = 'lab'
    elif route.startswith('/radiology/'):
        bp = 'radiology'
    elif route.startswith('/medication/'):
        bp = 'medication'
    elif route.startswith('/nurse/'):
        bp = 'nurse'
    elif route.startswith('/manager/'):
        bp = 'manager'
    elif route.startswith('/owner/'):
        bp = 'owner'
    elif route.startswith('/super-admin/'):
        bp = 'super_admin'
    elif route.startswith('/accountant/'):
        bp = 'accountant'
    elif route.startswith('/finance/'):
        bp = 'finance'
    elif route.startswith('/portal/'):
        bp = 'portal'
    elif route.startswith('/payment/'):
        bp = 'payment'
    elif route.startswith('/bed/'):
        bp = 'bed'
    elif route.startswith('/booking/'):
        bp = 'booking'
    elif route.startswith('/auth/'):
        bp = 'auth'
    elif route.startswith('/backup/'):
        bp = 'backup'
    elif route.startswith('/dicom/'):
        bp = 'dicom'
    elif route.startswith('/hl7/'):
        bp = 'hl7'
    elif route.startswith('/ihe/'):
        bp = 'ihe'
    elif route.startswith('/telemedicine/'):
        bp = 'telemedicine'
    elif route.startswith('/booking/'):
        bp = 'booking'
    elif route.startswith('/cds/'):
        bp = 'cds'
    elif route.startswith('/specialty-'):
        bp = 'specialty_forms'
    elif route.startswith('/patient-'):
        bp = 'patient_education'
    elif route.startswith('/vaccination/'):
        bp = 'vaccination'
    elif route.startswith('/what-if/'):
        bp = 'what_if'
    elif route.startswith('/pathway/'):
        bp = 'pathway'
    elif route.startswith('/or/'):
        bp = 'or'
    elif route.startswith('/cds/'):
        bp = 'cds'
    elif route.startswith('/quality/'):
        bp = 'quality'
    elif route.startswith('/backup/'):
        bp = 'backup'
    elif route.startswith('/dicom/'):
        bp = 'dicom'
    elif route.startswith('/hl7/'):
        bp = 'hl7'
    elif route.startswith('/ihe/'):
        bp = 'ihe'
    elif route.startswith('/pwa/'):
        bp = 'pwa'
    elif route.startswith('/barcode/'):
        bp = 'barcode'
    elif route.startswith('/biometric/'):
        bp = 'biometric'
    elif route.startswith('/mfa/'):
        bp = 'mfa'
    elif route.startswith('/population-'):
        bp = 'population_health'
    elif route.startswith('/report-'):
        bp = 'report_builder'
    elif route.startswith('/saas/'):
        bp = 'saas'
    elif route.startswith('/sso/'):
        bp = 'sso'
    elif route.startswith('/security/'):
        bp = 'security'
    elif route.startswith('/settings'):
        bp = 'settings'
    elif route.startswith('/specialty-'):
        bp = 'specialty_forms'
    elif route.startswith('/procurement/'):
        bp = 'procurement'
    elif route.startswith('/referral/'):
        bp = 'referral'
    elif route.startswith('/vaccination/'):
        bp = 'vaccination'
    elif route.startswith('/what-if/'):
        bp = 'what_if'
    elif route.startswith('/handover/'):
        bp = 'handover'
    elif route.startswith('/data-warehouse/'):
        bp = 'data_warehouse'
    elif route.startswith('/kiosk/'):
        bp = 'kiosk'
    elif route.startswith('/monitoring/'):
        bp = 'monitoring'
    elif route.startswith('/procurement/'):
        bp = 'procurement'
    elif route.startswith('/referral/'):
        bp = 'referral'
    elif route.startswith('/telemedicine/'):
        bp = 'telemedicine'
    elif route.startswith('/vaccination/'):
        bp = 'vaccination'
    elif route.startswith('/what-if/'):
        bp = 'what_if'
    elif route.startswith('/handover/'):
        bp = 'handover'
    elif route.startswith('/metrics'):
        bp = 'metrics'
    elif route.startswith('/finance/'):
        bp = 'finance'
    elif route.startswith('/accountant/'):
        bp = 'accountant'
    elif route.startswith('/owner/'):
        bp = 'owner'
    elif route.startswith('/super-admin/'):
        bp = 'super_admin'
    elif route.startswith('/manager/'):
        bp = 'manager'
    elif route.startswith('/emergency/'):
        bp = 'emergency'
    elif route.startswith('/lab/'):
        bp = 'lab'
    elif route.startswith('/radiology/'):
        bp = 'radiology'
    elif route.startswith('/medication/'):
        bp = 'medication'
    elif route.startswith('/nurse/'):
        bp = 'nurse'
    elif route.startswith('/reception/'):
        bp = 'reception'
    elif route.startswith('/doctor/'):
        bp = 'doctor'
    elif route.startswith('/api/'):
        bp = 'api'
    elif route.startswith('/auth/'):
        bp = 'auth'
    elif route.startswith('/backup/'):
        bp = 'backup'
    elif route.startswith('/bed/'):
        bp = 'bed'
    elif route.startswith('/booking/'):
        bp = 'booking'
    elif route.startswith('/finance/'):
        bp = 'finance'
    elif route.startswith('/accountant/'):
        bp = 'accountant'
    elif route.startswith('/owner/'):
        bp = 'owner'
    elif route.startswith('/super-admin/'):
        bp = 'super_admin'
    elif route.startswith('/manager/'):
        bp = 'manager'
    elif route.startswith('/emergency/'):
        bp = 'emergency'
    elif route.startswith('/lab/'):
        bp = 'lab'
    elif route.startswith('/radiology/'):
        bp = 'radiology'
    elif route.startswith('/medication/'):
        bp = 'medication'
    elif route.startswith('/nurse/'):
        bp = 'nurse'
    elif route.startswith('/reception/'):
        bp = 'reception'
    elif route.startswith('/doctor/'):
        bp = 'doctor'
    else:
        bp = 'other'

    bp_counts[bp] = bp_counts.get(bp, 0) + 1

    # Track roles per blueprint
    if bp not in bp_roles:
        bp_roles[bp] = {}
    for role in roles:
        bp_roles[bp][role] = bp_roles[bp].get(role, 0) + 1

print('Blueprint route counts:')
for bp, count in sorted(bp_counts.items(), key=lambda x: -x[1]):
    print(f'{bp:30} {count}')

print('\nRoles per blueprint:')
for bp, roles in sorted(bp_roles.items()):
    print(f'\n{bp}:')
    for role, count in sorted(roles.items(), key=lambda x: -x[1]):
        print(f'  {role}: {count}')

# Also check for routes without explicit roles
with_role = sum(1 for r in perms.values() if r != ['authenticated'])
print(f'\nTotal routes: {len(perms)}')
print(f'Routes with specific roles: {with_role}')
print(f'Routes with only login: {len(perms) - with_role}')
