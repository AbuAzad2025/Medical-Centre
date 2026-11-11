"""Coverage tests for routes.patient_education_routes.py"""

from __future__ import annotations

import pytest

pytest_plugins = ['tests._isolated_tenant']


class TestAllowedFile:
    def test_allowed_extensions(self):
        from routes.patient_education_routes import allowed_file

        assert allowed_file('document.pdf') is True
        assert allowed_file('image.png') is True
        assert allowed_file('image.jpg') is True
        assert allowed_file('image.jpeg') is True
        assert allowed_file('image.gif') is True
        assert allowed_file('video.mp4') is True
        assert allowed_file('video.webm') is True

    def test_disallowed_extensions(self):
        from routes.patient_education_routes import allowed_file

        assert allowed_file('script.exe') is False
        assert allowed_file('document.txt') is False
        assert allowed_file('noextension') is False
        assert allowed_file('') is False

    def test_case_insensitive(self):
        from routes.patient_education_routes import allowed_file

        assert allowed_file('document.PDF') is True
        assert allowed_file('image.PNG') is True


class TestPatientEducationRoutes:
    def test_index(self, app, client, login_as):
        login_as(client, 'ed_user', 'doctor')
        resp = client.get('/patient-education/')
        assert resp.status_code in (200, 302, 403)

    def test_view_material_not_found(self, app, client, login_as):
        login_as(client, 'ed_view_user', 'doctor')
        resp = client.get('/patient-education/material/99999')
        assert resp.status_code in (200, 302, 404)
