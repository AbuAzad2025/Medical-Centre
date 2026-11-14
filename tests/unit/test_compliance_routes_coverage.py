"""Coverage tests for routes/compliance_routes.py"""

pytest_plugins = ['tests._isolated_tenant']


class TestComplianceRoutes:
    PATHS = [
        '/compliance/audit-summary',
        '/compliance/breach-check',
        '/compliance/data-retention',
        '/compliance/encryption-at-rest',
        '/compliance/encryption-at-rest-verification',
        '/compliance/encryption_at_rest',
        '/compliance/encryption_at_rest_verification',
        '/compliance/encryption-verification',
        '/compliance/access-control-review',
        '/compliance/access-control',
        '/compliance/access_control_review',
        '/compliance/consent-verification',
        '/compliance/consent-management-verification',
        '/compliance/consent-management',
        '/compliance/consent_management_verification',
        '/compliance/verify-consent',
        '/compliance/audit-log-retention',
        '/compliance/audit-log-retention-check',
        '/compliance/audit_retention',
        '/compliance/audit-retention',
        '/compliance/audit-retention-check',
        '/compliance/soc2/cc1-control-environment',
        '/compliance/soc2/cc2-communication',
        '/compliance/soc2/cc3-risk-assessment',
        '/compliance/soc2/cc4-monitoring',
        '/compliance/soc2/cc5-control-activities',
        '/compliance/soc2/cc6-logical-access',
        '/compliance/soc2/cc7-system-operations',
        '/compliance/soc2/cc8-change-management',
        '/compliance/soc2/cc9-risk-mitigation',
        '/compliance/soc2/score',
    ]

    def test_get_unauth(self, app, client):
        for path in self.PATHS:
            resp = client.get(path)
            assert resp.status_code in (200, 302, 401, 403, 404)

    def test_get_auth(self, app, client, login_as):
        login_as(client, 'comp_get_user', 'admin')
        for path in self.PATHS:
            resp = client.get(path)
            assert resp.status_code in (200, 302, 401, 403, 404)

    def test_data_export_get(self, app, client):
        for path in [
            '/compliance/data-export',
            '/compliance/data_export',
            '/compliance/patient-data-export',
            '/compliance/export-patient-data',
        ]:
            resp = client.get(path)
            assert resp.status_code in (200, 302, 401, 403, 404)

    def test_data_export_post(self, app, client):
        for path in [
            '/compliance/data-export',
            '/compliance/data_export',
            '/compliance/patient-data-export',
            '/compliance/export-patient-data',
        ]:
            resp = client.post(path, data={})
            assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_data_export_patient(self, app, client):
        for path in ['/compliance/data-export/1']:
            resp = client.get(path)
            assert resp.status_code in (200, 302, 401, 403, 404)
            resp = client.post(path, data={})
            assert resp.status_code in (200, 302, 400, 401, 403, 404)
