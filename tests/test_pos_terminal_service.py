import unittest
import os
from services.pos_terminal_service import PosTerminalService
import services.pos_terminal_service as pos_module


class PosTerminalServiceTestCase(unittest.TestCase):
    def setUp(self):
        self._orig_enabled = os.environ.get('POS_ENABLED')
        self._orig_base = os.environ.get('POS_BASE_URL')
        self._orig_urlopen = pos_module.request.urlopen

    def tearDown(self):
        if self._orig_enabled is None:
            os.environ.pop('POS_ENABLED', None)
        else:
            os.environ['POS_ENABLED'] = self._orig_enabled
        if self._orig_base is None:
            os.environ.pop('POS_BASE_URL', None)
        else:
            os.environ['POS_BASE_URL'] = self._orig_base
        pos_module.request.urlopen = self._orig_urlopen

    def test_base_url_default(self):
        os.environ.pop('POS_BASE_URL', None)
        url = PosTerminalService.base_url()
        self.assertEqual(url, 'http://127.0.0.1:9100/api/pos')

    def test_is_enabled_disabled(self):
        os.environ.pop('POS_ENABLED', None)
        os.environ.pop('POS_BASE_URL', None)
        self.assertFalse(PosTerminalService.is_enabled())

    def test_is_enabled_by_flag_values(self):
        os.environ.pop('POS_BASE_URL', None)
        for v in ['1', 'true', 'yes', 'on']:
            os.environ['POS_ENABLED'] = v
            self.assertTrue(PosTerminalService.is_enabled())
        os.environ['POS_ENABLED'] = '0'
        self.assertFalse(PosTerminalService.is_enabled())

    def test_is_enabled_by_base_url(self):
        os.environ.pop('POS_ENABLED', None)
        os.environ['POS_BASE_URL'] = 'http://pos.example/api'
        self.assertTrue(PosTerminalService.is_enabled())

    def test_charge_disabled(self):
        os.environ.pop('POS_ENABLED', None)
        os.environ.pop('POS_BASE_URL', None)
        out = PosTerminalService.charge(10.0, 'ILS')
        self.assertFalse(out.get('success'))
        self.assertIn('not enabled', out.get('message', '').lower())

    def test_charge_url_error(self):
        os.environ['POS_BASE_URL'] = 'http://127.0.0.1:9999/api/pos'
        os.environ['POS_ENABLED'] = 'true'
        class Boom:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
        def raise_url_error(req, timeout=15):
            raise pos_module.error.URLError('conn')
        pos_module.request.urlopen = raise_url_error
        out = PosTerminalService.charge(15.0, 'ILS')
        self.assertFalse(out.get('success'))
        self.assertIn('conn', str(out.get('message')))


if __name__ == '__main__':
    unittest.main()
