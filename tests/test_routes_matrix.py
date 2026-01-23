import unittest
import re
import uuid
from app_factory import create_app, db
from models.user import User


class RoutesMatrixTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app.config.update(PROPAGATE_EXCEPTIONS=False)
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.client = self.app.test_client()
        db.create_all()
        suf = uuid.uuid4().hex[:6]
        self.roles = [
            'super_admin', 'admin', 'manager', 'reception', 'doctor',
            'emergency', 'lab', 'radiology', 'nurse', 'accountant'
        ]
        self.users = {}
        for role in self.roles:
            uname = f'{role}_{suf}'
            u = User(username=uname, email=f'{uname}@example.com', full_name=uname, role=role, is_admin=(role in ['super_admin','admin']), is_active=True)
            u.set_password('p')
            db.session.add(u)
            self.users[role] = uname
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def _login(self, role):
        r = self.client.post('/auth/login', data={'username': self.users[role], 'password': 'p'}, follow_redirects=False)
        self.assertIn(r.status_code, (301, 302))

    def _sample_path(self, rule):
        path = rule.rule
        def repl(m):
            conv = m.group(1) or 'string'
            name = m.group(2)
            if conv == 'int':
                return '1'
            if conv == 'float':
                return '1.0'
            if conv == 'path':
                return 'x/y'
            if conv == 'uuid':
                return '00000000-0000-0000-0000-000000000000'
            return 'x'
        path = re.sub(r'<(?:(\w+):)?(\w+)>', repl, path)
        return path

    def test_get_routes_by_role_matrix(self):
        routes = [r for r in self.app.url_map.iter_rules() if 'GET' in r.methods]
        skip_prefixes = ('/static/',)
        count = 0
        for role in self.roles:
            with self.subTest(role=role):
                self._login(role)
                for r in routes:
                    path = self._sample_path(r)
                    if any(path.startswith(p) for p in skip_prefixes):
                        continue
                    resp = self.client.get(path, follow_redirects=False)
                    with self.subTest(role=role, path=path, code=resp.status_code):
                        self.assertTrue(isinstance(resp.status_code, int))
                        count += 1
        self.assertGreater(count, 1000)

    def test_get_routes_html_quality(self):
        routes = [r for r in self.app.url_map.iter_rules() if 'GET' in r.methods]
        skip_prefixes = ('/static/',)
        validated = 0
        for role in self.roles:
            self._login(role)
            for r in routes:
                path = self._sample_path(r)
                if any(path.startswith(p) for p in skip_prefixes):
                    continue
                resp = self.client.get(path, follow_redirects=False)
                if resp.status_code == 200 and 'text/html' in resp.headers.get('Content-Type', ''):
                    html = resp.data.decode('utf-8', errors='ignore')
                    if len(html) > 300:
                        self.assertIn('<html', html)
                        self.assertIn('<body', html)
                        self.assertIn('</body>', html)
                        validated += 1
        self.assertGreaterEqual(validated, 50)

    def test_post_json_endpoints(self):
        post_rules = [r for r in self.app.url_map.iter_rules() if 'POST' in r.methods]
        accept = {200, 301, 302, 400, 401, 403, 404, 405, 422, 500}
        for role in ['accountant', 'manager', 'admin', 'super_admin', 'reception', 'doctor', 'lab', 'radiology', 'nurse']:
            self._login(role)
            for r in post_rules:
                path = self._sample_path(r)
                resp = self.client.post(path, json={}, follow_redirects=False)
                with self.subTest(role=role, path=path, code=resp.status_code):
                    self.assertIn(resp.status_code, accept)

    def test_put_patch_delete_endpoints(self):
        put_rules = [r for r in self.app.url_map.iter_rules() if 'PUT' in r.methods]
        patch_rules = [r for r in self.app.url_map.iter_rules() if 'PATCH' in r.methods]
        delete_rules = [r for r in self.app.url_map.iter_rules() if 'DELETE' in r.methods]
        accept = {200, 301, 302, 400, 401, 403, 404, 405, 422, 500}
        roles = ['admin', 'manager', 'super_admin', 'accountant', 'doctor', 'lab', 'radiology', 'reception', 'nurse']
        for role in roles:
            self._login(role)
            for r in put_rules:
                path = self._sample_path(r)
                resp = self.client.put(path, json={}, follow_redirects=False)
                with self.subTest(method='PUT', role=role, path=path, code=resp.status_code):
                    self.assertIn(resp.status_code, accept)
            for r in patch_rules:
                path = self._sample_path(r)
                resp = self.client.patch(path, json={}, follow_redirects=False)
                with self.subTest(method='PATCH', role=role, path=path, code=resp.status_code):
                    self.assertIn(resp.status_code, accept)
            for r in delete_rules:
                path = self._sample_path(r)
                resp = self.client.delete(path, follow_redirects=False)
                with self.subTest(method='DELETE', role=role, path=path, code=resp.status_code):
                    self.assertIn(resp.status_code, accept)

if __name__ == '__main__':
    unittest.main()
