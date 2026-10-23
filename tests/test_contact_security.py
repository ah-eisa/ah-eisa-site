"""Offline regression fixtures. Notifications are replaced; no real credentials."""
import importlib.util
import io
import json
from email.message import Message
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path('/app/tara_publisher.py') if Path('/app/tara_publisher.py').exists() else Path(__file__).resolve().parents[1] / 'tara_publisher.py'
spec = importlib.util.spec_from_file_location('contact_under_review', SOURCE)
contact = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contact)

class ContactSecurity(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        contact.STATE_DIR = self.scratch.name
        contact.LEADS_FILE = str(Path(self.scratch.name) / 'leads.json')
        contact.rate_limiter = contact.RateLimiter()
        self.alerts = []
        self.patches = [patch.object(contact, name, self.notify) for name in ('send_telegram_alert', 'send_email_alert')]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def notify(self, *args, **kwargs):
        self.alerts.append(True)
        return True, 'dummy sink'

    def handler(self, data=None, peer='127.0.0.1', canonical='203.0.113.9', length=None):
        raw = json.dumps(data).encode() if data is not None else b''
        handler = object.__new__(contact.TaraPublishHandler)
        handler.client_address = (peer, 12345)
        handler.headers = Message()
        handler.headers['Content-Type'] = 'application/json'
        handler.headers['Content-Length'] = str(len(raw)) if length is None else str(length)
        if canonical is not None:
            handler.headers['X-Ah-Eisa-Client-IP'] = canonical
        handler.rfile = io.BytesIO(raw)
        handler.path = '/api/contact'
        handler.response = None
        handler.send_json = lambda status, value: setattr(handler, 'response', (status, value))
        return handler

    def valid(self):
        return {'name': 'Fixture User', 'email': 'fixture@example.invalid', 'subject': 'Offline fixture', 'message': 'Synthetic local inquiry only.'}

    def test_only_loopback_proxy_can_supply_canonical_identity(self):
        handler = self.handler(peer='203.0.113.7', canonical='198.51.100.6')
        self.assertEqual(handler.canonical_client_ip(), '203.0.113.7')
        handler = self.handler(canonical='2001:db8::1')
        self.assertEqual(handler.canonical_client_ip(), '2001:db8::1')

    def test_legacy_forwarded_values_do_not_select_quota(self):
        handler = self.handler(canonical=None)
        handler.headers['X-Forwarded-For'] = '198.51.100.12'
        handler.headers['X-Real-IP'] = '198.51.100.13'
        self.assertEqual(handler.canonical_client_ip(), '127.0.0.1')

    def test_negative_and_duplicate_lengths_are_rejected(self):
        handler = self.handler(self.valid(), length='-1')
        handler.handle_contact()
        self.assertEqual(handler.response[0], 400)
        handler = self.handler(self.valid())
        handler.headers['Content-Length'] = '1'
        handler.handle_contact()
        self.assertEqual(handler.response[0], 400)
        self.assertFalse(self.alerts)

    def test_nonobject_and_nontext_fields_are_rejected(self):
        for data in ([1], {'_hp_company': []}, {**self.valid(), 'name': {'nested': 'value'}}):
            handler = self.handler(data)
            handler.handle_contact()
            self.assertEqual(handler.response[0], 400)
        self.assertFalse(self.alerts)

    def test_valid_inquiry_persists_privately_before_dummy_notifications(self):
        handler = self.handler(self.valid())
        handler.handle_contact()
        self.assertEqual(handler.response[0], 200)
        target = Path(contact.LEADS_FILE)
        self.assertEqual(len(json.loads(target.read_text())), 1)
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
        self.assertEqual(len(self.alerts), 2)

    def test_failed_persistence_never_reports_success_or_notifies(self):
        with patch.object(contact, 'save_lead_record', return_value=False):
            handler = self.handler(self.valid())
            handler.handle_contact()
        self.assertEqual(handler.response[0], 503)
        self.assertFalse(self.alerts)

    def test_corrupt_store_is_preserved(self):
        target = Path(contact.LEADS_FILE)
        target.write_text('synthetic invalid store')
        self.assertFalse(contact.save_lead_record({'fixture': True}))
        self.assertEqual(target.read_text(), 'synthetic invalid store')

    def test_retired_publisher_never_writes_an_article(self):
        before = list(Path(self.scratch.name).iterdir())
        for route in ('/publish', '/api/publish', '/api/publish/'):
            handler = self.handler({'title': 'Fixture', 'body': 'Fixture'})
            handler.path = route
            handler.do_POST()
            self.assertEqual(handler.response[0], 410)
        self.assertEqual(list(Path(self.scratch.name).iterdir()), before)
        self.assertFalse(self.alerts)

    def test_per_ip_and_global_budgets_remain_enforced(self):
        limiter = contact.RateLimiter()
        for _ in range(5):
            self.assertTrue(limiter.check_and_record('203.0.113.1')[0])
        self.assertFalse(limiter.check_and_record('203.0.113.1')[0])
        for i in range(25):
            self.assertTrue(limiter.check_and_record(f'198.51.100.{i}')[0])
        self.assertFalse(limiter.check_and_record('192.0.2.1')[0])

if __name__ == '__main__':
    unittest.main(verbosity=2)
