import unittest
from app_factory import create_app, db
from flask import Flask
from utils.decorators import role_required, accountant_only, can_create_visits, can_access_financial_reports, prevent_self_approval, log_action
from models.user import User
from models.visit import Visit
from models.patient import Patient
from models.audit_trail import AuditTrail


class UtilsDecoratorsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.client = self.app.test_client()
        db.create_all()
        self.manager = User(username='mgr_user2', email='mgr2@example.com', full_name='Manager', role='manager', is_admin=False)
        self.manager.set_password('p')
        self.doctor = User(username='doc_user2', email='doc2@example.com', full_name='Doctor', role='doctor', is_admin=False)
        self.doctor.set_password('p')
        self.accountant = User(username='acc_user2', email='acc2@example.com', full_name='Accountant', role='accountant', is_admin=False)
        self.accountant.set_password('p')
        self.reception = User(username='rec_user2', email='rec2@example.com', full_name='Reception', role='reception', is_admin=False)
        self.reception.set_password('p')
        db.session.add_all([self.manager, self.doctor, self.accountant, self.reception])
        db.session.commit()

        @self.app.route('/protected-manager')
        @role_required('manager')
        def protected_manager():
            return 'ok'

        @self.app.route('/protected-accountant')
        @accountant_only
        def protected_accountant():
            return 'ok'

        @self.app.route('/protected-create-visit')
        @can_create_visits
        def protected_create_visit():
            return 'ok'
        
        @self.app.route('/protected-financial-reports')
        @can_access_financial_reports
        def protected_financial_reports():
            return 'ok'
        
        @self.app.route('/approve-force', methods=['POST'])
        @prevent_self_approval
        def approve_force():
            return 'ok'
        
        @self.app.route('/log-action')
        @log_action('test_action')
        def log_action_route():
            return 'ok'

    def tearDown(self):
        db.session.rollback()
        # Use TRUNCATE TABLE instead of DROP SCHEMA to avoid enum type recreation issues
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        if tables:
            db.session.execute(db.text(f"TRUNCATE TABLE {', '.join(tables)} CASCADE"))
        db.session.commit()
        db.engine.dispose()
        db.session.remove()
        self.ctx.pop()

    def _login(self, username, password='p'):
        return self.client.post('/auth/login', data={'username': username, 'password': password}, follow_redirects=False)

    def test_role_required_manager(self):
        r = self._login(self.manager.username, 'p')
        self.assertEqual(r.status_code, 302)
        resp = self.client.get('/protected-manager')
        self.assertEqual(resp.status_code, 200)
        r2 = self._login(self.doctor.username, 'p')
        self.assertEqual(r2.status_code, 302)
        resp2 = self.client.get('/protected-manager')
        self.assertEqual(resp2.status_code, 403)

    def test_accountant_only(self):
        r = self._login(self.accountant.username, 'p')
        self.assertEqual(r.status_code, 302)
        resp = self.client.get('/protected-accountant')
        self.assertEqual(resp.status_code, 200)
        r2 = self._login(self.manager.username, 'p')
        self.assertEqual(r2.status_code, 302)
        resp2 = self.client.get('/protected-accountant')
        self.assertEqual(resp2.status_code, 200)
        r3 = self._login(self.doctor.username, 'p')
        self.assertEqual(r3.status_code, 302)
        resp3 = self.client.get('/protected-accountant')
        self.assertEqual(resp3.status_code, 403)

    def test_can_create_visits(self):
        r = self._login(self.reception.username, 'p')
        self.assertEqual(r.status_code, 302)
        resp = self.client.get('/protected-create-visit')
        self.assertEqual(resp.status_code, 200)
        r2 = self._login(self.accountant.username, 'p')
        self.assertEqual(r2.status_code, 302)
        resp2 = self.client.get('/protected-create-visit')
        self.assertEqual(resp2.status_code, 403)
    
    def test_can_access_financial_reports(self):
        r = self._login(self.accountant.username, 'p')
        self.assertEqual(r.status_code, 302)
        resp1 = self.client.get('/protected-financial-reports')
        self.assertEqual(resp1.status_code, 200)
        r2 = self._login(self.manager.username, 'p')
        self.assertEqual(r2.status_code, 302)
        resp2 = self.client.get('/protected-financial-reports')
        self.assertEqual(resp2.status_code, 200)
        r3 = self._login(self.doctor.username, 'p')
        self.assertEqual(r3.status_code, 302)
        resp3 = self.client.get('/protected-financial-reports')
        self.assertEqual(resp3.status_code, 403)
    
    def test_prevent_self_approval_blocks_creator(self):
        p = Patient(first_name='Self', last_name='Approve')
        db.session.add(p)
        db.session.commit()
        v = Visit(patient_id=p.id, department_id=None, doctor_id=None, status='OPEN', created_by=self.manager.id)
        db.session.add(v)
        db.session.commit()
        r = self._login(self.manager.username, 'p')
        self.assertEqual(r.status_code, 302)
        resp = self.client.post('/approve-force', data={'visit_id': v.id})
        self.assertEqual(resp.status_code, 403)
        r2 = self._login(self.accountant.username, 'p')
        self.assertEqual(r2.status_code, 302)
        resp2 = self.client.post('/approve-force', data={'visit_id': v.id})
        self.assertEqual(resp2.status_code, 200)
    
    def test_log_action_decorator_executes_without_errors(self):
        r = self._login(self.manager.username, 'p')
        self.assertEqual(r.status_code, 302)
        before = AuditTrail.query.count()
        resp = self.client.get('/log-action')
        self.assertEqual(resp.status_code, 200)
        after = AuditTrail.query.count()
        self.assertGreaterEqual(after, before)


if __name__ == '__main__':
    unittest.main()
