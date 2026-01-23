import unittest
import uuid
from app_factory import create_app, db
from models.user import User
from models.service import ServiceMaster


class SuperAdminPricingPageTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.client = self.app.test_client()
        db.create_all()
        suf = uuid.uuid4().hex[:8]

        # super admin
        self.admin_username = f'pricing_admin_test_{suf}'
        self.admin = User(username=self.admin_username, email=f'pricing_admin_test_{suf}@example.com', full_name='Pricing Admin', role='super_admin', is_admin=True)
        self.admin.set_password('p')
        db.session.add(self.admin)
        db.session.commit()

        # create service
        self.service = ServiceMaster(code=f'CONS01_{suf}', name='Consultation', description='Basic consultation', base_price=50, is_active=True)
        db.session.add(self.service)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def _login(self, username, password):
        page = self.client.get('/auth/login')
        html = page.data.decode('utf-8')
        import re
        m = re.search(r'name="csrf_token" value="([^"]+)"', html)
        token = m.group(1) if m else ''
        return self.client.post('/auth/login', data={'username': username, 'password': password, 'csrf_token': token}, follow_redirects=True)

    def test_pricing_page_loads(self):
        self._login(self.admin_username, 'p')
        r = self.client.get(f'/super-admin/service-pricing/{self.service.id}')
        self.assertEqual(r.status_code, 200)
        self.assertIn('Consultation', r.data.decode('utf-8'))


if __name__ == '__main__':
    unittest.main()
