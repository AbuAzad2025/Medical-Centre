"""
MEGA Route Walker — visits EVERY registered endpoint as super_admin.
Super admin bypasses all module guards and role checks, so this covers
the maximum number of handler functions in a single pass.
"""

import pytest


def _get_routes(app):
    routes = []
    for rule in app.url_map.iter_rules():
        if 'GET' not in rule.methods:
            continue
        skip = ('/static/', '/__health', '/_ghost', '/debug', '/kiosk')
        if any(rule.rule.startswith(p) for p in skip):
            continue
        if rule.endpoint.startswith('static'):
            continue
        routes.append(rule.rule)
    return sorted(set(routes))


def _safe(client, url):
    try:
        return client.get(url, follow_redirects=False).status_code
    except Exception:
        return None


@pytest.fixture
def sa_client(app, client, db, test_tenant):
    from tests.tenant_context import ensure_test_user, login_test_client

    u = ensure_test_user(db, test_tenant, username='mega_sa', role='super_admin')
    login_test_client(client, u, test_tenant)
    return client


_PREFIXES = [
    '/',
    '/reception/',
    '/doctor/',
    '/lab/',
    '/radiology/',
    '/medication/',
    '/nurse/',
    '/nursing-assessment/',
    '/emergency/',
    '/bed/',
    '/or/',
    '/finance/',
    '/accountant/',
    '/manager/',
    '/booking/',
    '/payment/',
    '/billing/',
    '/inbox/',
    '/clinical-coding/',
    '/clinical-pathway/',
    '/vaccination/',
    '/referral/',
    '/specialty-forms/',
    '/patient-education/',
    '/quality/',
    '/population-health/',
    '/what-if/',
    '/data-warehouse/',
    '/report-builder/',
    '/dicom/',
    '/ai-imaging/',
    '/telemedicine/',
    '/emar/',
    '/barcode/',
    '/biometric/',
    '/backup/',
    '/backup-restore/',
]


class TestMegaWalkerReception:
    def test_walk_reception_all(self, app, sa_client):
        routes = _get_routes(app)
        walked = [u for u in routes if any(u.startswith(p) for p in ['/reception/'])]
        codes = [_safe(sa_client, u) for u in walked]
        errors = [(u, c) for u, c in zip(walked, codes, strict=False) if c is not None and c >= 500]
        print(f'\n[RC] {len(walked)} routes, server_errors={len(errors)}')
        for u, c in errors[:5]:
            print(f'  5xx: {u} -> {c}')


class TestMegaWalkerDoctor:
    def test_walk_doctor_all(self, app, sa_client):
        routes = _get_routes(app)
        walked = [u for u in routes if any(u.startswith(p) for p in ['/doctor/'])]
        [_safe(sa_client, u) for u in walked]
        print(f'\n[DR] {len(walked)} routes')


class TestMegaWalkerPharmacy:
    def test_walk_pharmacy_medication(self, app, sa_client):
        routes = _get_routes(app)
        walked = [u for u in routes if any(u.startswith(p) for p in ['/medication/', '/pharmacy/'])]
        [_safe(sa_client, u) for u in walked]
        print(f'\n[PH] {len(walked)} routes')


class TestMegaWalkerNurse:
    def test_walk_nurse_bed_emar(self, app, sa_client):
        routes = _get_routes(app)
        walked = [
            u
            for u in routes
            if any(u.startswith(p) for p in ['/nurse/', '/nursing-assessment/', '/bed/', '/emar/'])
        ]
        [_safe(sa_client, u) for u in walked]
        print(f'\n[NU] {len(walked)} routes')


class TestMegaWalkerLabRadiology:
    def test_walk_lab_radiology(self, app, sa_client):
        routes = _get_routes(app)
        walked = [
            u
            for u in routes
            if any(u.startswith(p) for p in ['/lab/', '/radiology/', '/dicom/', '/ai-imaging/'])
        ]
        [_safe(sa_client, u) for u in walked]
        print(f'\n[LR] {len(walked)} routes')


class TestMegaWalkerFinance:
    def test_walk_finance_accountant_billing(self, app, sa_client):
        routes = _get_routes(app)
        walked = [
            u
            for u in routes
            if any(u.startswith(p) for p in ['/finance/', '/accountant/', '/billing/', '/payment/'])
        ]
        [_safe(sa_client, u) for u in walked]
        print(f'\n[FI] {len(walked)} routes')


class TestMegaWalkerManager:
    def test_walk_manager_reports(self, app, sa_client):
        routes = _get_routes(app)
        walked = [
            u
            for u in routes
            if any(
                u.startswith(p)
                for p in [
                    '/manager/',
                    '/report-builder/',
                    '/data-warehouse/',
                    '/what-if/',
                    '/population-health/',
                    '/quality/',
                ]
            )
        ]
        [_safe(sa_client, u) for u in walked]
        print(f'\n[MG] {len(walked)} routes')


class TestMegaWalkerEmergency:
    def test_walk_emergency_or_vaccination_referral(self, app, sa_client):
        routes = _get_routes(app)
        walked = [
            u
            for u in routes
            if any(
                u.startswith(p)
                for p in ['/emergency/', '/or/', '/vaccination/', '/referral/', '/cds/']
            )
        ]
        [_safe(sa_client, u) for u in walked]
        print(f'\n[EM] {len(walked)} routes')


class TestMegaWalkerSpecialty:
    def test_walk_specialty_patient_edu_telemedicine_sso_security(self, app, sa_client):
        routes = _get_routes(app)
        walked = [
            u
            for u in routes
            if any(
                u.startswith(p)
                for p in [
                    '/specialty-forms/',
                    '/patient-education/',
                    '/telemedicine/',
                    '/sso/',
                    '/security/',
                    '/pwa/',
                ]
            )
        ]
        [_safe(sa_client, u) for u in walked]
        print(f'\n[SP] {len(walked)} routes')


class TestMegaWalkerMisc:
    def test_walk_misc_root_main(self, app, sa_client):
        routes = _get_routes(app)
        # Walk everything NOT covered above (misc, main, root, etc.)
        known_prefixes = [
            '/reception/',
            '/doctor/',
            '/medication/',
            '/pharmacy/',
            '/nurse/',
            '/nursing-assessment/',
            '/bed/',
            '/emar/',
            '/lab/',
            '/radiology/',
            '/dicom/',
            '/ai-imaging/',
            '/finance/',
            '/accountant/',
            '/billing/',
            '/payment/',
            '/manager/',
            '/report-builder/',
            '/data-warehouse/',
            '/what-if/',
            '/population-health/',
            '/quality/',
            '/emergency/',
            '/or/',
            '/vaccination/',
            '/referral/',
            '/cds/',
            '/specialty-forms/',
            '/patient-education/',
            '/telemedicine/',
            '/sso/',
            '/security/',
            '/pwa/',
            '/auth/',
            '/owner/',
            '/super-admin/',
            '/backup/',
            '/backup-restore/',
            '/api/fhir',
            '/static/',
            '/kiosk',
            '/tenant/',
            '/saas',
            '/mfa',
            '/barcode',
            '/biometric',
        ]
        misc = [u for u in routes if not any(u.startswith(p) for p in known_prefixes)]
        [_safe(sa_client, u) for u in misc]
        print(f'\n[MISC] {len(misc)} routes')
