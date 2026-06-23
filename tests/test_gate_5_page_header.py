"""Phase 5: clinical-page-header macro on priority routes."""

from __future__ import annotations

import pytest


class TestPageHeaderMacro:
    def test_renders_title_subtitle_and_actions(self, app):
        with app.app_context():
            from flask import render_template_string
            html = render_template_string(
                "{% from 'partials/_page_header.html' import page_header %}"
                "{{ page_header("
                "title='عنوان', subtitle='وصف', icon='fas fa-star',"
                "breadcrumbs=[{'label': 'الرئيسية', 'url': '/'}, {'label': 'الحالي'}],"
                "actions=["
                "  {'url': '/new', 'label': 'جديد', 'icon': 'fas fa-plus'},"
                "  {'type': 'button', 'label': 'تصدير', 'data_action': 'export-visits', 'style': 'success'}"
                "]) }}"
            )
        assert 'clinical-page-header' in html
        assert 'عنوان' in html
        assert 'وصف' in html
        assert 'data-action="export-visits"' in html
        assert 'href="/new"' in html
        assert 'clinical-breadcrumb' in html


class TestReceptionPagesUsePageHeader:
    @pytest.fixture
    def reception_client(self, app, client, test_tenant):
        from app.core.rate_limiter import _shared_store
        from app_factory import db as _db
        from models.user import User

        _shared_store.clear()
        u = User.query.filter_by(username='reception_ph5').first()
        if not u:
            u = User(
                username='reception_ph5',
                email='reception_ph5@test.local',
                full_name='استقبال PH5',
                role='reception',
                is_active=True,
                tenant_id=test_tenant.id,
            )
            u.set_password('test123')
            _db.session.add(u)
            _db.session.commit()

        client.post('/auth/login', data={
            'username': 'reception_ph5',
            'password': 'test123',
            'tenant_slug': test_tenant.slug,
        })
        return client

    def test_visits_page_has_clinical_page_header(self, reception_client):
        resp = reception_client.get('/reception/visits')
        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        assert 'clinical-page-header' in text
        assert 'قائمة الزيارات' in text
        assert 'data-action="export-visits"' in text

    def test_queue_page_has_clinical_page_header(self, reception_client):
        resp = reception_client.get('/reception/queue')
        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        assert 'clinical-page-header' in text
        assert 'إدارة الطابور الموحد' in text

    def test_appointments_page_has_clinical_page_header(self, reception_client):
        resp = reception_client.get('/reception/appointments')
        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        assert 'clinical-page-header' in text
        assert 'قائمة المواعيد' in text
        assert 'data-action="export-appointments"' in text

    def test_follow_ups_page_has_clinical_page_header(self, reception_client):
        resp = reception_client.get('/reception/follow-ups')
        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        assert 'clinical-page-header' in text
        assert 'المتابعات' in text


class TestDoctorQueuePageHeader:
    @pytest.fixture
    def doctor_client(self, app, client, test_tenant):
        from app.core.rate_limiter import _shared_store
        from app_factory import db as _db
        from models.user import User

        _shared_store.clear()
        u = User.query.filter_by(username='doctor_ph5').first()
        if not u:
            u = User(
                username='doctor_ph5',
                email='doctor_ph5@test.local',
                full_name='طبيب PH5',
                role='doctor',
                is_active=True,
                tenant_id=test_tenant.id,
            )
            u.set_password('test123')
            _db.session.add(u)
            _db.session.commit()

        client.post('/auth/login', data={
            'username': 'doctor_ph5',
            'password': 'test123',
            'tenant_slug': test_tenant.slug,
        })
        return client

    def test_patient_queue_header(self, doctor_client):
        resp = doctor_client.get('/doctor/patient-queue')
        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        assert 'clinical-page-header' in text
        assert 'data-action="refreshQueue"' in text


class TestPharmacyPosPageHeader:
    def test_pos_page_header(self, auth_client):
        resp = auth_client.get('/medication/pos')
        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        assert 'clinical-page-header' in text
        assert 'نقطة البيع' in text

    def test_medication_list_header(self, auth_client):
        resp = auth_client.get('/medication/list')
        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        assert 'clinical-page-header' in text
        assert 'قائمة الأدوية' in text

    def test_medication_add_header(self, auth_client):
        resp = auth_client.get('/medication/add')
        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        assert 'clinical-page-header' in text
        assert 'إضافة دواء جديد' in text


class TestLabRadiologyEmergencyPageHeader:
    @pytest.fixture
    def lab_client(self, app, client, test_tenant):
        from app.core.rate_limiter import _shared_store
        from app_factory import db as _db
        from models.user import User

        _shared_store.clear()
        u = User.query.filter_by(username='lab_ph5').first()
        if not u:
            u = User(
                username='lab_ph5',
                email='lab_ph5@test.local',
                full_name='مختبر PH5',
                role='lab',
                is_active=True,
                tenant_id=test_tenant.id,
            )
            u.set_password('test123')
            _db.session.add(u)
            _db.session.commit()

        client.post('/auth/login', data={
            'username': 'lab_ph5',
            'password': 'test123',
            'tenant_slug': test_tenant.slug,
        })
        return client

    @pytest.fixture
    def radiology_client(self, app, client, test_tenant):
        from app.core.rate_limiter import _shared_store
        from app_factory import db as _db
        from models.user import User

        _shared_store.clear()
        u = User.query.filter_by(username='radiology_ph5').first()
        if not u:
            u = User(
                username='radiology_ph5',
                email='radiology_ph5@test.local',
                full_name='أشعة PH5',
                role='radiology',
                is_active=True,
                tenant_id=test_tenant.id,
            )
            u.set_password('test123')
            _db.session.add(u)
            _db.session.commit()

        client.post('/auth/login', data={
            'username': 'radiology_ph5',
            'password': 'test123',
            'tenant_slug': test_tenant.slug,
        })
        return client

    @pytest.fixture
    def emergency_client(self, app, client, test_tenant):
        from app.core.rate_limiter import _shared_store
        from app_factory import db as _db
        from models.user import User

        _shared_store.clear()
        u = User.query.filter_by(username='emergency_ph5').first()
        if not u:
            u = User(
                username='emergency_ph5',
                email='emergency_ph5@test.local',
                full_name='طوارئ PH5',
                role='emergency',
                is_active=True,
                tenant_id=test_tenant.id,
            )
            u.set_password('test123')
            _db.session.add(u)
            _db.session.commit()

        client.post('/auth/login', data={
            'username': 'emergency_ph5',
            'password': 'test123',
            'tenant_slug': test_tenant.slug,
        })
        return client

    def test_lab_worklist_header(self, lab_client):
        resp = lab_client.get('/lab/worklist')
        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        assert 'clinical-page-header' in text
        assert 'قائمة عمل المختبر' in text

    def test_radiology_requests_header(self, radiology_client):
        resp = radiology_client.get('/radiology/requests')
        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        assert 'clinical-page-header' in text
        assert 'طلبات فحوصات الأشعة' in text

    def test_emergency_visits_header(self, emergency_client):
        resp = emergency_client.get('/emergency/emergency-visits')
        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        assert 'clinical-page-header' in text
        assert 'زيارات الطوارئ' in text
        assert 'clinical-breadcrumb' in text

    def test_lab_quality_header(self, lab_client):
        resp = lab_client.get('/lab/quality')
        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        assert 'clinical-page-header' in text
        assert 'جودة المختبر' in text

    def test_radiology_quality_header(self, radiology_client):
        resp = radiology_client.get('/radiology/quality')
        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        assert 'clinical-page-header' in text
        assert 'جودة الأشعة' in text


class TestNurseSuperAdminPageHeader:
    @pytest.fixture
    def nurse_client(self, app, client, test_tenant):
        from app.core.rate_limiter import _shared_store
        from app_factory import db as _db
        from models.user import User

        _shared_store.clear()
        u = User.query.filter_by(username='nurse_ph5').first()
        if not u:
            u = User(
                username='nurse_ph5',
                email='nurse_ph5@test.local',
                full_name='ممرض PH5',
                role='nurse',
                is_active=True,
                tenant_id=test_tenant.id,
            )
            u.set_password('test123')
            _db.session.add(u)
            _db.session.commit()

        client.post('/auth/login', data={
            'username': 'nurse_ph5',
            'password': 'test123',
            'tenant_slug': test_tenant.slug,
        })
        return client

    @pytest.fixture
    def superadmin_client(self, app, client, test_tenant):
        from app.core.rate_limiter import _shared_store
        from app_factory import db as _db
        from models.user import User

        _shared_store.clear()
        u = User.query.filter_by(username='superadmin_ph5').first()
        if not u:
            u = User(
                username='superadmin_ph5',
                email='superadmin_ph5@test.local',
                full_name='سوبر أدمن PH5',
                role='super_admin',
                is_active=True,
                tenant_id=test_tenant.id,
            )
            u.set_password('test123')
            _db.session.add(u)
            _db.session.commit()

        client.post('/auth/login', data={
            'username': 'superadmin_ph5',
            'password': 'test123',
            'tenant_slug': test_tenant.slug,
        })
        return client

    def test_nurse_reports_header(self, nurse_client):
        resp = nurse_client.get('/nurse/reports')
        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        assert 'clinical-page-header' in text
        assert 'تقرير التمريض' in text

    def test_superadmin_permissions_header(self, superadmin_client):
        resp = superadmin_client.get('/super-admin/permissions')
        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        assert 'clinical-page-header' in text
        assert 'إدارة الصلاحيات' in text

    def test_superadmin_performance_header(self, superadmin_client):
        resp = superadmin_client.get('/super-admin/performance')
        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        assert 'clinical-page-header' in text
        assert 'مراقبة الأداء' in text

    def test_superadmin_maintenance_header(self, superadmin_client):
        resp = superadmin_client.get('/super-admin/system/maintenance')
        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        assert 'clinical-page-header' in text
        assert 'صيانة النظام' in text


class TestMedicalHeaderDebt:
    """Phase 5 — migrated templates must not keep legacy medical-header blocks."""

    MIGRATED = (
        'medication/list.html',
        'medication/add.html',
        'radiology/radiology_requests.html',
        'doctor/notes.html',
        'lab/process.html',
        'emergency/emergency_visits.html',
        'nurse/reports.html',
        'lab/quality.html',
        'radiology/quality.html',
        'super_admin/permissions.html',
        'super_admin/performance.html',
        'super_admin/system_maintenance.html',
    )

    def test_migrated_templates_drop_medical_header(self):
        from pathlib import Path
        root = Path(__file__).parent.parent / 'templates'
        for rel in self.MIGRATED:
            text = (root / rel).read_text(encoding='utf-8')
            assert 'medical-header' not in text, rel
            assert 'content-header' not in text, rel
            assert 'class="page-title"' not in text, rel

    def test_all_macro_importers_use_macro_and_drop_legacy(self):
        """Self-maintaining: every template importing page_header must call it
        and must not retain legacy header markers."""
        from pathlib import Path
        root = Path(__file__).parent.parent / 'templates'
        for path in root.rglob('*.html'):
            text = path.read_text(encoding='utf-8')
            if 'import page_header' not in text:
                continue
            rel = path.relative_to(root).as_posix()
            assert 'page_header(' in text, rel
            assert 'medical-header' not in text, rel
            assert 'content-header' not in text, rel
            assert 'class="page-title"' not in text, rel

    def test_all_macro_importers_compile(self, app):
        """Every template using the macro must compile (Jinja syntax check)."""
        from pathlib import Path
        root = Path(__file__).parent.parent / 'templates'
        errors = []
        with app.app_context():
            for path in root.rglob('*.html'):
                text = path.read_text(encoding='utf-8')
                if 'import page_header' not in text:
                    continue
                rel = path.relative_to(root).as_posix()
                try:
                    app.jinja_env.get_template(rel)
                except Exception as e:
                    errors.append((rel, type(e).__name__, str(e)[:160]))
        assert not errors, errors

    def test_macro_templates_url_for_endpoints_exist(self, app):
        """Catch url_for BuildErrors: every endpoint referenced in a migrated
        template must be registered in the URL map."""
        import re
        from pathlib import Path
        root = Path(__file__).parent.parent / 'templates'
        known = set(app.url_map._rules_by_endpoint.keys())
        pattern = re.compile(r"url_for\(\s*['\"]([a-zA-Z0-9_.]+)['\"]")
        missing = []
        for path in root.rglob('*.html'):
            text = path.read_text(encoding='utf-8')
            if 'import page_header' not in text:
                continue
            rel = path.relative_to(root).as_posix()
            for ep in pattern.findall(text):
                if ep not in known:
                    missing.append((rel, ep))
        assert not missing, missing
