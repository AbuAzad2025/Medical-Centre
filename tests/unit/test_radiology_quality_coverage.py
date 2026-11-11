"""Coverage tests for routes.radiology.quality.py"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

pytest_plugins = ['tests._isolated_tenant']


class TestRadiologyQuality:
    def test_quality_page(self, app, client, login_as):
        login_as(client, 'rad_qual_user', 'radiology')
        resp = client.get('/radiology/quality')
        assert resp.status_code in (200, 302)

    def test_quality_page_with_dates(self, app, client, login_as):
        login_as(client, 'rad_qual_date_user', 'radiology')
        resp = client.get('/radiology/quality?start_date=2026-01-01&end_date=2026-12-31')
        assert resp.status_code in (200, 302)

    def test_quality_page_manager(self, app, client, login_as):
        login_as(client, 'rad_qual_mgr', 'manager')
        resp = client.get('/radiology/quality')
        assert resp.status_code in (200, 302)

    def test_api_ai_assist_ct_brain(self, app, client, login_as):
        login_as(client, 'rad_ai_user', 'radiology')
        resp = client.post(
            '/radiology/api/ai-assist',
            json={
                'modality': 'CT',
                'body_part': 'brain',
                'impression': 'headache',
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert 'suggestions' in data['data']

    def test_api_ai_assist_chest_xray(self, app, client, login_as):
        login_as(client, 'rad_ai_chest_user', 'radiology')
        resp = client.post(
            '/radiology/api/ai-assist',
            json={
                'modality': 'XRAY',
                'body_part': 'chest',
                'impression': 'cough',
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_api_ai_assist_us_abdomen(self, app, client, login_as):
        login_as(client, 'rad_ai_us_user', 'radiology')
        resp = client.post(
            '/radiology/api/ai-assist',
            json={
                'modality': 'US',
                'body_part': 'abdomen',
                'impression': 'pain',
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_api_ai_assist_bleed(self, app, client, login_as):
        login_as(client, 'rad_ai_bleed_user', 'radiology')
        resp = client.post(
            '/radiology/api/ai-assist',
            json={
                'modality': 'CT',
                'body_part': 'head',
                'impression': '뇌출혈',
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_api_ai_assist_no_suggestions(self, app, client, login_as):
        login_as(client, 'rad_ai_none_user', 'radiology')
        resp = client.post(
            '/radiology/api/ai-assist',
            json={
                'modality': 'MRI',
                'body_part': 'knee',
                'impression': 'sprain',
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert len(data['data']['suggestions']) >= 1

    def test_second_review_not_found(self, app, client, login_as):
        login_as(client, 'rad_review_user', 'radiology')
        resp = client.post('/radiology/results/99999/second-review')
        assert resp.status_code == 404
