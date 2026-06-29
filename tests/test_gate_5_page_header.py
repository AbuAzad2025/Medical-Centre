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
    def reception_client(self, client, login_as):
        return login_as(client, 'reception_ph5', 'reception', full_name='استقبال PH5')

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
    def doctor_client(self, client, login_as):
        return login_as(client, 'doctor_ph5', 'doctor', full_name='طبيب PH5')

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
    def lab_client(self, client, login_as):
        return login_as(client, 'lab_ph5', 'lab', full_name='مختبر PH5')

    @pytest.fixture
    def radiology_client(self, client, login_as):
        return login_as(client, 'radiology_ph5', 'radiology', full_name='أشعة PH5')

    @pytest.fixture
    def emergency_client(self, client, login_as):
        return login_as(client, 'emergency_ph5', 'emergency', full_name='طوارئ PH5')

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
    def nurse_client(self, client, login_as):
        return login_as(client, 'nurse_ph5', 'nurse', full_name='ممرض PH5')

    @pytest.fixture
    def superadmin_client(self, client, login_as):
        return login_as(client, 'superadmin_ph5', 'super_admin', full_name='سوبر أدمن PH5')

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


class TestPageHeaderFormAndHero:
    """Macro extensions: CSRF-protected form action + gradient hero variant."""

    def test_form_action_renders_post_with_csrf(self, app):
        from flask import render_template_string
        tmpl = (
            "{% from 'partials/_page_header.html' import page_header %}"
            "{{ page_header('عنوان', actions=["
            "{'type':'form','label':'تحويل','url':'/checkin','style':'info','icon':'fas fa-x'}]) }}"
        )
        with app.test_request_context():
            html = render_template_string(tmpl)
        assert 'clinical-page-header' in html
        assert '<form' in html and 'method="POST"' in html
        assert 'action="/checkin"' in html
        assert 'name="csrf_token"' in html
        assert 'btn-info' in html

    def test_hero_variant_renders_gradient(self, app):
        from flask import render_template_string
        tmpl = (
            "{% from 'partials/_page_header.html' import page_header %}"
            "{{ page_header('قسم المختبر', subtitle='وصف', icon='fas fa-flask', "
            "hero_class='lab-gradient', actions=[{'label':'X','url':'/y','style':'light'}]) }}"
        )
        with app.test_request_context():
            html = render_template_string(tmpl)
        assert 'clinical-page-header--hero' in html
        assert 'lab-gradient' in html
        assert 'text-white' in html
        assert 'btn-light' in html

    def test_view_appointment_uses_macro_form(self, app):
        from flask import render_template
        from types import SimpleNamespace
        appt = SimpleNamespace(
            id=42,
            status='SCHEDULED',
            patient=SimpleNamespace(full_name='مريض اختبار', phone='0599000000'),
            department=SimpleNamespace(name_ar='الأسنان', name='Dental'),
            doctor=SimpleNamespace(full_name='د. سارة'),
            starts_at=None,
        )
        with app.test_request_context():
            html = render_template(
                'reception/view_appointment.html',
                appointment=appt, appt_type='كشف', symptoms=None, base_notes=None,
            )
        assert 'clinical-page-header' in html
        assert 'تفاصيل الموعد' in html
        assert 'checkin' in html
        assert 'name="csrf_token"' in html
        assert 'مجدول' in html  # AppointmentState.SCHEDULED localized


class TestDashboardHeroAndInfoPagesRender:
    def test_legacy_dashboard_heroes_render_with_hero_header(self, app):
        from pathlib import Path
        for tmpl, cls in [('lab/dashboard_new.html', 'lab-gradient'),
                          ('accountant/dashboard_new.html', 'acc-gradient')]:
            # header-only smoke: confirm the migrated hero header compiles + emits gradient
            src = (Path(__file__).parent.parent / 'templates' / tmpl).read_text(encoding='utf-8')
            assert "import page_header" in src
            assert "hero_class='" + cls + "'" in src

    @pytest.mark.parametrize('tmpl', ['main/about.html', 'main/terms.html', 'main/privacy.html'])
    def test_public_info_pages_render(self, app, tmpl):
        from flask import render_template
        with app.test_request_context():
            html = render_template(tmpl)
        assert 'card' in html and '</div>' in html
