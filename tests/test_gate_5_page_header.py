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


class TestMedicalHeaderDebt:
    """Phase 5 — migrated templates must not keep legacy medical-header blocks."""

    MIGRATED = (
        'medication/list.html',
        'medication/add.html',
        'radiology/radiology_requests.html',
        'doctor/notes.html',
        'lab/process.html',
        'emergency/emergency_visits.html',
    )

    def test_migrated_templates_drop_medical_header(self):
        from pathlib import Path
        root = Path(__file__).parent.parent / 'templates'
        for rel in self.MIGRATED:
            text = (root / rel).read_text(encoding='utf-8')
            assert 'medical-header' not in text, rel
            assert 'content-header' not in text, rel
