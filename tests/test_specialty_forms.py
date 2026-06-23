"""Tests for UX1-005: Dynamic specialty forms."""

import uuid

import pytest

from app_factory import db as _db
from models.patient import Patient
from models.specialty_form import (
    SpecialtyForm,
    SpecialtyFormField,
    SpecialtyFormSubmission,
    SpecialtyFormVersion,
)


@pytest.fixture(scope='function')
def specialty_patient(app, test_tenant):
    suffix = uuid.uuid4().hex[:8]
    p = Patient(
        tenant_id=test_tenant.id,
        first_name=f'SpecForm{suffix}',
        last_name='Patient',
        phone='0599999999',
    )
    _db.session.add(p)
    _db.session.commit()
    return p


@pytest.fixture(scope='function')
def draft_specialty_form(app, test_tenant, manager_user):
    suffix = uuid.uuid4().hex[:6]
    form = SpecialtyForm(
        tenant_id=test_tenant.id,
        name=f'نموذج اختبار {suffix}',
        slug=f'test-form-{suffix}',
        specialty='اختبار',
        is_active=True,
        created_by=manager_user.id,
    )
    _db.session.add(form)
    _db.session.flush()
    version = SpecialtyFormVersion(
        tenant_id=test_tenant.id,
        form_id=form.id,
        version_number=1,
        status='draft',
    )
    _db.session.add(version)
    _db.session.flush()
    _db.session.add(SpecialtyFormField(
        tenant_id=test_tenant.id,
        version_id=version.id,
        name='chief_complaint',
        label='الشكوى الرئيسية',
        field_type='textarea',
        required=True,
        sort_order=0,
    ))
    _db.session.commit()
    return form, version


class TestSpecialtyFormsAccess:
    def test_list_requires_login(self, client):
        resp = client.get('/specialty-forms')
        assert resp.status_code == 302

    def test_list_loads_for_manager(self, manager_auth_client):
        resp = manager_auth_client.get('/specialty-forms')
        assert resp.status_code == 200
        assert 'النماذج التخصصية'.encode('utf-8') in resp.data

    def test_new_form_forbidden_for_pharmacist(self, auth_client):
        resp = auth_client.get('/specialty-forms/new')
        assert resp.status_code == 403


class TestSpecialtyFormsLifecycle:
    def test_create_draft_form(self, manager_auth_client, test_tenant):
        suffix = uuid.uuid4().hex[:6]
        slug = f'intake-{suffix}'
        resp = manager_auth_client.post('/specialty-forms/new', data={
            'name': f'نموذج قبول {suffix}',
            'slug': slug,
            'specialty': 'قلب',
            'description': 'وصف اختبار',
            'field_label[]': ['ضغط الدم'],
            'field_name[]': ['bp'],
            'field_type[]': ['text'],
            'field_required[]': ['1'],
            'field_options[]': [''],
            'field_default[]': [''],
            'field_order[]': ['0'],
        }, follow_redirects=False)
        assert resp.status_code == 302
        form = SpecialtyForm.query.filter_by(slug=slug).first()
        assert form is not None
        assert form.tenant_id == test_tenant.id or form.tenant_id is None
        assert len(form.versions) == 1
        assert form.versions[0].status == 'draft'
        assert len(form.versions[0].fields) == 1

    def test_publish_and_fill(self, manager_auth_client, draft_specialty_form, specialty_patient, test_tenant):
        form, version = draft_specialty_form
        pub = manager_auth_client.post(
            f'/specialty-forms/{form.id}/versions/{version.id}/publish',
            follow_redirects=True,
        )
        assert pub.status_code == 200
        _db.session.refresh(form)
        assert form.latest_published_version_id == version.id

        fill = manager_auth_client.post(f'/specialty-forms/{form.id}/fill', data={
            'patient_id': specialty_patient.id,
            'field_chief_complaint': 'ألم صدر',
        }, follow_redirects=True)
        assert fill.status_code == 200
        submission = SpecialtyFormSubmission.query.filter_by(patient_id=specialty_patient.id).first()
        assert submission is not None
        assert submission.answers['chief_complaint'] == 'ألم صدر'

    def test_view_submission(self, manager_auth_client, draft_specialty_form, specialty_patient):
        form, version = draft_specialty_form
        version.status = 'published'
        form.latest_published_version_id = version.id
        submission = SpecialtyFormSubmission(
            tenant_id=form.tenant_id,
            version_id=version.id,
            patient_id=specialty_patient.id,
            answers={'chief_complaint': 'سعال'},
            submitted_by=None,
        )
        _db.session.add(submission)
        _db.session.commit()

        resp = manager_auth_client.get(f'/specialty-forms/submissions/{submission.id}')
        assert resp.status_code == 200
        assert 'سعال'.encode('utf-8') in resp.data

    def test_cannot_edit_published_version(self, manager_auth_client, draft_specialty_form):
        form, version = draft_specialty_form
        version.status = 'published'
        form.latest_published_version_id = version.id
        _db.session.commit()

        resp = manager_auth_client.get(
            f'/specialty-forms/{form.id}/versions/{version.id}/edit',
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert f'/specialty-forms/{form.id}' in (resp.location or '')

    def test_publish_without_fields_rejected(self, manager_auth_client, test_tenant, manager_user):
        suffix = uuid.uuid4().hex[:6]
        form = SpecialtyForm(
            tenant_id=test_tenant.id,
            name='فارغ',
            slug=f'empty-{suffix}',
            is_active=True,
            created_by=manager_user.id,
        )
        _db.session.add(form)
        _db.session.flush()
        version = SpecialtyFormVersion(
            tenant_id=test_tenant.id,
            form_id=form.id,
            version_number=1,
            status='draft',
        )
        _db.session.add(version)
        _db.session.commit()

        resp = manager_auth_client.post(
            f'/specialty-forms/{form.id}/versions/{version.id}/publish',
            follow_redirects=False,
        )
        assert resp.status_code == 302
        _db.session.refresh(version)
        assert version.status == 'draft'
