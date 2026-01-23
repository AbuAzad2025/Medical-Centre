import unittest
from app_factory import create_app, db


class PerfEndpointTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def test_perf_json(self):
        r = self.client.get('/__perf/finance')
        self.assertEqual(r.status_code, 200)
        self.assertIn('application/json', r.content_type)

    def test_perf_html(self):
        r = self.client.get('/__perf/finance?format=html')
        self.assertEqual(r.status_code, 200)
        self.assertIn('text/html', r.content_type)


if __name__ == '__main__':
    unittest.main()
