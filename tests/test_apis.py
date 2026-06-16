import unittest
import uuid
from app_factory import create_app, db
from models.user import User


class ApiEndpointsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.client = self.app.test_client()
        db.create_all()
        self.suf = uuid.uuid4().hex[:8]
        self.reception = self._create_user(f'api_reception_test_{self.suf}', 'reception')
        self.other = self._create_user(f'api_other_test_{self.suf}', 'nurse')

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

    def _create_user(self, username, role, password='p'):
        u = User(username=username, email=f'{username}_{self.suf}@example.com', full_name=username, role=role, is_admin=False)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        return u

    def _login(self, username, password):
        page = self.client.get('/auth/login')
        html = page.data.decode('utf-8')
        import re
        m = re.search(r'name="csrf_token" value="([^"]+)"', html)
        token = m.group(1) if m else ''
        return self.client.post('/auth/login', data={'username': username, 'password': password, 'csrf_token': token}, follow_redirects=False)

    def test_booking_available_doctors_public(self):
        r = self.client.get('/booking/api/available-doctors')
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn('success', data)

    def test_available_times_respects_schedule(self):
        from models.user import User, StaffWorkSchedule, StaffAbsence
        import datetime as _dt
        d = User(username=f'doc_{self.suf}', email=f'doc_{self.suf}@example.com', full_name='Doctor Test', role='doctor', is_admin=False)
        d.set_password('p')
        db.session.add(d)
        db.session.commit()
        dow = _dt.date.today().weekday()
        s = StaffWorkSchedule.query.filter_by(user_id=d.id, day_of_week=dow).first()
        if s:
            s.start_time = _dt.time(10,0)
            s.end_time = _dt.time(12,0)
        else:
            s = StaffWorkSchedule(user_id=d.id, day_of_week=dow, start_time=_dt.time(10,0), end_time=_dt.time(12,0), is_active=True)
            db.session.add(s)
        db.session.commit()
        today = _dt.date.today().strftime('%Y-%m-%d')
        r = self.client.get(f'/booking/api/available-times?doctor_id={d.id}&date={today}')
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertTrue(data['success'])
        self.assertIn('10:00', data['available_times'])
        self.assertIn('11:00', data['available_times'])

    def test_available_times_respects_absence(self):
        from models.user import User, StaffWorkSchedule, StaffAbsence
        import datetime as _dt
        d = User(username=f'doc2_{self.suf}', email=f'doc2_{self.suf}@example.com', full_name='Doctor Test 2', role='doctor', is_admin=False)
        d.set_password('p')
        db.session.add(d)
        db.session.commit()
        today_date = _dt.date.today()
        a = StaffAbsence(user_id=d.id, start_date=today_date, end_date=today_date, reason='Leave')
        db.session.add_all([a])
        db.session.commit()
        today = today_date.strftime('%Y-%m-%d')
        r = self.client.get(f'/booking/api/available-times?doctor_id={d.id}&date={today}')
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['available_times'], [])

    def test_reception_api_doctors_forbidden_without_role(self):
        self._login(f'api_other_test_{self.suf}', 'p')
        r = self.client.get('/reception/api/doctors')
        self.assertEqual(r.status_code, 403)

    def test_reception_api_doctors_allowed_for_reception(self):
        self._login(f'api_reception_test_{self.suf}', 'p')
        r = self.client.get('/reception/api/doctors')
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertTrue('success' in data)


if __name__ == '__main__':
    unittest.main()
