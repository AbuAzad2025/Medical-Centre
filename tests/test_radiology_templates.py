"""Tests for routes.radiology.templates module.

Covers radiology report template CRUD operations.
"""

import pytest
from unittest.mock import MagicMock, patch

from routes.radiology import radiology_bp


@pytest.fixture
def template_data():
    return [
        {'id': '1', 'name': 'Template 1', 'modality': 'XRAY', 'findings': 'F', 'impression': 'I',
         'recommendations': 'R', 'is_active': True},
        {'id': '2', 'name': 'Template 2', 'modality': 'CT', 'findings': 'F', 'impression': 'I',
         'recommendations': 'R', 'is_active': False},
        {'id': '3', 'name': 'Template 3', 'modality': 'MRI', 'findings': 'F', 'impression': 'I',
         'recommendations': 'R', 'is_active': True},
    ]


class TestApiReportTemplates:
    """Tests for api_report_templates endpoint."""

    @patch('routes.radiology.templates._get_radiology_report_templates')
    def test_get_templates_default(self, mock_get, manager_auth_client, template_data):
        """Test GET templates with defaults."""
        mock_get.return_value = template_data.copy()
        response = manager_auth_client.get('/radiology/api/report-templates')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    @patch('routes.radiology.templates._get_radiology_report_templates')
    def test_get_templates_inactive_included(self, mock_get, manager_auth_client, template_data):
        """Test GET templates includes inactive when active_only=false."""
        mock_get.return_value = template_data.copy()
        response = manager_auth_client.get('/radiology/api/report-templates?active_only=false')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    @patch('routes.radiology.templates._get_radiology_report_templates')
    def test_get_templates_with_modality_filter(self, mock_get, manager_auth_client, template_data):
        """Test GET templates with modality filter."""
        mock_get.return_value = template_data.copy()
        response = manager_auth_client.get('/radiology/api/report-templates?modality=xray')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    @patch('routes.radiology.templates._get_radiology_report_templates')
    def test_get_templates_empty_list(self, mock_get, manager_auth_client):
        """Test GET templates with no templates."""
        mock_get.return_value = []
        response = manager_auth_client.get('/radiology/api/report-templates')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['templates'] == []

    @patch('routes.radiology.templates._get_radiology_report_templates')
    def test_get_templates_skips_non_dicts(self, mock_get, manager_auth_client, template_data):
        """Test GET templates skips non-dict entries."""
        mock_get.return_value = [None, 'string', {'id': '1', 'modality': 'XRAY', 'is_active': True}]
        response = manager_auth_client.get('/radiology/api/report-templates?active_only=false')
        assert response.status_code == 200
        data = response.get_json()
        assert len(data['templates']) == 1

    @patch('routes.radiology.templates._get_radiology_report_templates')
    def test_get_templates_active_false_string(self, mock_get, manager_auth_client, template_data):
        """Test GET templates with active_only=false as '0'."""
        mock_get.return_value = template_data.copy()
        response = manager_auth_client.get('/radiology/api/report-templates?active_only=0')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    @patch('routes.radiology.templates._get_radiology_report_templates')
    def test_get_templates_no_modality_match(self, mock_get, manager_auth_client):
        """Test GET templates with modality that doesn't match."""
        mock_get.return_value = [{'id': '1', 'modality': 'XRAY', 'is_active': True}]
        response = manager_auth_client.get('/radiology/api/report-templates?modality=ct')
        assert response.status_code == 200
        data = response.get_json()
        assert len(data['templates']) == 0


class TestUpsertReportTemplate:
    """Tests for upsert_report_template endpoint."""

    @patch('routes.radiology.templates._get_radiology_report_templates')
    @patch('routes.radiology.templates._save_radiology_report_templates')
    def test_create_new_template(self, mock_save, mock_get, manager_auth_client):
        """Test creating a new template."""
        mock_get.return_value = []
        response = manager_auth_client.post('/radiology/api/report-templates', json={
            'name': 'New Template',
            'modality': 'XRAY',
            'findings': 'Findings',
            'impression': 'Impression',
        })
        assert response.status_code == 201
        data = response.get_json()
        assert data['success'] is True
        assert data['id'] is not None

    @patch('routes.radiology.templates._get_radiology_report_templates')
    @patch('routes.radiology.templates._save_radiology_report_templates')
    def test_update_existing_template(self, mock_save, mock_get, manager_auth_client):
        """Test updating an existing template."""
        mock_get.return_value = [
            {'id': '1', 'name': 'Old', 'modality': 'XRAY', 'findings': '', 'impression': '',
             'recommendations': '', 'is_active': True},
        ]
        response = manager_auth_client.post('/radiology/api/report-templates', json={
            'id': '1',
            'name': 'Updated Template',
            'modality': 'CT',
            'findings': 'New findings',
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['id'] == '1'

    @patch('routes.radiology.templates._get_radiology_report_templates')
    @patch('routes.radiology.templates._save_radiology_report_templates')
    def test_update_nonexistent_template(self, mock_save, mock_get, manager_auth_client):
        """Test updating a non-existent template."""
        mock_get.return_value = [
            {'id': '1', 'name': 'Old', 'modality': 'XRAY', 'findings': '', 'impression': '',
             'recommendations': '', 'is_active': True},
        ]
        response = manager_auth_client.post('/radiology/api/report-templates', json={
            'id': '999',
            'name': 'Test',
            'modality': 'XRAY',
        })
        assert response.status_code == 404

    @patch('routes.radiology.templates._get_radiology_report_templates')
    def test_create_template_missing_name(self, mock_get, manager_auth_client):
        """Test creating template without name."""
        mock_get.return_value = []
        response = manager_auth_client.post('/radiology/api/report-templates', json={
            'modality': 'XRAY',
        })
        assert response.status_code == 400

    @patch('routes.radiology.templates._get_radiology_report_templates')
    def test_create_template_invalid_modality(self, mock_get, manager_auth_client):
        """Test creating template with invalid modality."""
        mock_get.return_value = []
        response = manager_auth_client.post('/radiology/api/report-templates', json={
            'name': 'Test',
            'modality': 'INVALID',
        })
        assert response.status_code == 400

    @patch('routes.radiology.templates._get_radiology_report_templates')
    @patch('routes.radiology.templates._save_radiology_report_templates')
    def test_create_template_active_from_string(self, mock_save, mock_get, manager_auth_client):
        """Test creating template with is_active as string."""
        mock_get.return_value = []
        response = manager_auth_client.post('/radiology/api/report-templates', json={
            'name': 'Test',
            'modality': 'CT',
            'is_active': 'true',
        })
        assert response.status_code == 201

    @patch('routes.radiology.templates._get_radiology_report_templates')
    @patch('routes.radiology.templates._save_radiology_report_templates')
    def test_create_template_active_false_string(self, mock_save, mock_get, manager_auth_client):
        """Test creating template with is_active=false string."""
        mock_get.return_value = []
        response = manager_auth_client.post('/radiology/api/report-templates', json={
            'name': 'Test',
            'modality': 'CT',
            'is_active': 'false',
        })
        assert response.status_code == 201

    @patch('routes.radiology.templates._get_radiology_report_templates')
    @patch('routes.radiology.templates._save_radiology_report_templates')
    def test_create_template_from_form(self, mock_save, mock_get, manager_auth_client):
        """Test creating template from form data instead of JSON."""
        mock_get.return_value = []
        response = manager_auth_client.post('/radiology/api/report-templates', data={
            'name': 'Form Template',
            'modality': 'MRI',
        })
        assert response.status_code == 201

    @patch('routes.radiology.templates._get_radiology_report_templates')
    @patch('routes.radiology.templates._save_radiology_report_templates')
    def test_create_template_is_active_default_true(self, mock_save, mock_get, manager_auth_client):
        """Test creating template with is_active=None defaults to True."""
        mock_get.return_value = []
        response = manager_auth_client.post('/radiology/api/report-templates', json={
            'name': 'Test',
            'modality': 'CT',
            'is_active': None,
        })
        assert response.status_code == 201

    @patch('routes.radiology.templates._get_radiology_report_templates')
    @patch('routes.radiology.templates._save_radiology_report_templates')
    def test_update_template_with_id_not_found(self, mock_save, mock_get, manager_auth_client):
        """Test updating template where id doesn't match."""
        mock_get.return_value = [
            {'id': '999', 'name': 'Other', 'modality': 'XRAY', 'findings': '', 'impression': '',
             'recommendations': '', 'is_active': True},
        ]
        response = manager_auth_client.post('/radiology/api/report-templates', json={
            'id': '1',
            'name': 'Test',
            'modality': 'XRAY',
        })
        assert response.status_code == 404


class TestDeleteReportTemplate:
    """Tests for delete_report_template endpoint."""

    @patch('routes.radiology.templates._get_radiology_report_templates')
    @patch('routes.radiology.templates._save_radiology_report_templates')
    def test_delete_existing_template(self, mock_save, mock_get, manager_auth_client):
        """Test deleting an existing template."""
        mock_get.return_value = [
            {'id': '1', 'name': 'T1', 'modality': 'XRAY', 'findings': '', 'impression': '',
             'recommendations': '', 'is_active': True},
            {'id': '2', 'name': 'T2', 'modality': 'CT', 'findings': '', 'impression': '',
             'recommendations': '', 'is_active': True},
        ]
        response = manager_auth_client.post('/radiology/api/report-templates/1/delete')
        assert response.status_code == 200

    @patch('routes.radiology.templates._get_radiology_report_templates')
    @patch('routes.radiology.templates._save_radiology_report_templates')
    def test_delete_nonexistent_template(self, mock_save, mock_get, manager_auth_client):
        """Test deleting a non-existent template."""
        mock_get.return_value = [
            {'id': '1', 'name': 'T1', 'modality': 'XRAY', 'is_active': True},
        ]
        response = manager_auth_client.post('/radiology/api/report-templates/999/delete')
        assert response.status_code == 404


class TestApiReportMacros:
    """Tests for api_report_macros endpoint."""

    @patch('routes.radiology.templates._get_radiology_report_macros')
    def test_get_macros_default(self, mock_get, manager_auth_client):
        """Test GET macros with defaults."""
        mock_get.return_value = [
            {'id': '1', 'name': 'Normal', 'text': 'No findings', 'is_active': True},
            {'id': '2', 'name': 'Abnormal', 'text': 'Abnormal', 'is_active': False},
        ]
        response = manager_auth_client.get('/radiology/api/report-macros')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    @patch('routes.radiology.templates._get_radiology_report_macros')
    def test_get_macros_inactive_included(self, mock_get, manager_auth_client):
        """Test GET macros includes inactive when active_only=false."""
        mock_get.return_value = [
            {'id': '1', 'name': 'Normal', 'text': 'No findings', 'is_active': True},
            {'id': '2', 'name': 'Abnormal', 'text': 'Abnormal', 'is_active': False},
        ]
        response = manager_auth_client.get('/radiology/api/report-macros?active_only=false')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    @patch('routes.radiology.templates._get_radiology_report_macros')
    def test_get_macros_empty_list(self, mock_get, manager_auth_client):
        """Test GET macros with no macros."""
        mock_get.return_value = []
        response = manager_auth_client.get('/radiology/api/report-macros')
        assert response.status_code == 200
        data = response.get_json()
        assert data['macros'] == []

    @patch('routes.radiology.templates._get_radiology_report_macros')
    def test_get_macros_skips_non_dicts(self, mock_get, manager_auth_client):
        """Test GET macros skips non-dict entries."""
        mock_get.return_value = [None, 'string', {'id': '1', 'name': 'M1', 'text': 'T', 'is_active': True}]
        response = manager_auth_client.get('/radiology/api/report-macros?active_only=false')
        assert response.status_code == 200
        data = response.get_json()
        assert len(data['macros']) == 1


class TestUpsertReportMacro:
    """Tests for upsert_report_macro endpoint."""

    @patch('routes.radiology.templates._get_radiology_report_macros')
    @patch('routes.radiology.templates._save_radiology_report_macros')
    def test_create_new_macro(self, mock_save, mock_get, manager_auth_client):
        """Test creating a new macro."""
        mock_get.return_value = []
        response = manager_auth_client.post('/radiology/api/report-macros', json={
            'name': 'New Macro',
            'text': 'Some text',
        })
        assert response.status_code == 201

    @patch('routes.radiology.templates._get_radiology_report_macros')
    @patch('routes.radiology.templates._save_radiology_report_macros')
    def test_update_existing_macro(self, mock_save, mock_get, manager_auth_client):
        """Test updating an existing macro."""
        mock_get.return_value = [
            {'id': '1', 'name': 'Old', 'text': 'Old text', 'is_active': True},
        ]
        response = manager_auth_client.post('/radiology/api/report-macros', json={
            'id': '1',
            'name': 'Updated',
            'text': 'Updated text',
        })
        assert response.status_code == 200

    @patch('routes.radiology.templates._get_radiology_report_macros')
    @patch('routes.radiology.templates._save_radiology_report_macros')
    def test_update_nonexistent_macro(self, mock_save, mock_get, manager_auth_client):
        """Test updating a non-existent macro."""
        mock_get.return_value = [
            {'id': '1', 'name': 'Old', 'text': 'Old', 'is_active': True},
        ]
        response = manager_auth_client.post('/radiology/api/report-macros', json={
            'id': '999',
            'name': 'Test',
            'text': 'Text',
        })
        assert response.status_code == 404

    @patch('routes.radiology.templates._get_radiology_report_macros')
    def test_create_macro_missing_name(self, mock_get, manager_auth_client):
        """Test creating macro without name."""
        mock_get.return_value = []
        response = manager_auth_client.post('/radiology/api/report-macros', json={
            'text': 'Some text',
        })
        assert response.status_code == 400

    @patch('routes.radiology.templates._get_radiology_report_macros')
    @patch('routes.radiology.templates._save_radiology_report_macros')
    def test_create_macro_active_from_string(self, mock_save, mock_get, manager_auth_client):
        """Test creating macro with is_active as string."""
        mock_get.return_value = []
        response = manager_auth_client.post('/radiology/api/report-macros', json={
            'name': 'Test',
            'text': 'Text',
            'is_active': 'true',
        })
        assert response.status_code == 201

    @patch('routes.radiology.templates._get_radiology_report_macros')
    @patch('routes.radiology.templates._save_radiology_report_macros')
    def test_create_macro_active_none_default(self, mock_save, mock_get, manager_auth_client):
        """Test creating macro with is_active=None defaults to True."""
        mock_get.return_value = []
        response = manager_auth_client.post('/radiology/api/report-macros', json={
            'name': 'Test',
            'text': 'Text',
            'is_active': None,
        })
        assert response.status_code == 201


class TestDeleteReportMacro:
    """Tests for delete_report_macro endpoint."""

    @patch('routes.radiology.templates._get_radiology_report_macros')
    @patch('routes.radiology.templates._save_radiology_report_macros')
    def test_delete_existing_macro(self, mock_save, mock_get, manager_auth_client):
        """Test deleting an existing macro."""
        mock_get.return_value = [
            {'id': '1', 'name': 'M1', 'text': 'T1', 'is_active': True},
            {'id': '2', 'name': 'M2', 'text': 'T2', 'is_active': True},
        ]
        response = manager_auth_client.post('/radiology/api/report-macros/1/delete')
        assert response.status_code == 200

    @patch('routes.radiology.templates._get_radiology_report_macros')
    @patch('routes.radiology.templates._save_radiology_report_macros')
    def test_delete_nonexistent_macro(self, mock_save, mock_get, manager_auth_client):
        """Test deleting a non-existent macro."""
        mock_get.return_value = [
            {'id': '1', 'name': 'M1', 'text': 'T1', 'is_active': True},
        ]
        response = manager_auth_client.post('/radiology/api/report-macros/999/delete')
        assert response.status_code == 404

    @patch('routes.radiology.templates._get_radiology_report_macros')
    @patch('routes.radiology.templates._save_radiology_report_macros')
    def test_delete_macro_skips_non_dicts(self, mock_save, mock_get, manager_auth_client):
        """Test deleting macro skips non-dict entries."""
        mock_get.return_value = [None, 'string', {'id': '1', 'name': 'M1', 'text': 'T', 'is_active': True}]
        response = manager_auth_client.post('/radiology/api/report-macros/999/delete')
        assert response.status_code == 404


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
