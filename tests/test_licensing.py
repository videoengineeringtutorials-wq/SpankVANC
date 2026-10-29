"""License trust boundaries: server time, persistence, denial and running-route expiry."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from spankvanc.engine import Engine
from spankvanc.licensing import LicenseClient, LicenseError, NoRedirect

KEY = 'SV1-' + 'a' * 43
NOW = 1800000000


class OnlineFixture:
    def __init__(self):
        self.now = NOW
        self.activated = NOW
        self.allowed = True
        self.calls = []
    def __call__(self, request, timeout):
        self.calls.append(json.loads(request.data))
        return io.BytesIO(json.dumps({'valid': True, 'server_time': self.now,
            'activated_at': self.activated, 'expires_at': self.activated + 2592000}
            if self.allowed else {'valid': False, 'reason': 'expired'}).encode())


class LicensingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'private/license.json'
        self.online = OnlineFixture()
        self.elapsed = 0
        self.client = LicenseClient(self.path, opener=self.online, monotonic=lambda: self.elapsed)
    def tearDown(self): self.temp.cleanup()

    def test_missing_key_denies_without_contacting_server(self):
        with self.assertRaises(LicenseError): self.client.require()
        self.assertEqual(self.online.calls, [])

    def test_activate_persist_restart_and_check_do_not_restart_timer(self):
        self.assertTrue(self.client.activate(KEY)['valid'])
        original = self.client.status()['expires_at']
        self.assertEqual(self.online.calls[-1]['action'], 'activate')
        self.assertEqual(set(self.online.calls[-1]), {'key', 'installation', 'action'})
        stored = json.loads(self.path.read_text())
        self.assertNotIn('expires_at', stored)
        self.assertNotIn(KEY, json.dumps(self.client.status()))
        restarted = LicenseClient(self.path, opener=self.online)
        self.assertFalse(restarted.status()['valid'])
        self.online.now += 86400
        restarted.require()
        self.assertEqual(restarted.status()['expires_at'], original)
        self.assertEqual(self.online.calls[-1]['installation'], stored['installation'])
        if __import__('os').name != 'nt': self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_window_uses_server_time_and_monotonic_lease(self):
        self.client.activate(KEY)
        with patch('time.time', return_value=1):
            self.assertTrue(self.client.status()['valid'])
        self.elapsed = 60
        self.assertFalse(self.client.status()['valid'])
        self.assertTrue(self.client.due())
        self.online.allowed = False
        with self.assertRaises(LicenseError): self.client.require()

    def test_short_remaining_window_never_gets_full_minute(self):
        self.online.now = NOW + 2592000 - 3
        self.client.activate(KEY)
        self.elapsed = 3
        self.assertFalse(self.client.status()['valid'])
        self.assertTrue(self.client.due())

    def test_outage_and_malformed_success_fail_closed(self):
        self.client.activate(KEY)
        self.client.opener = Mock(side_effect=OSError('do not echo keys or URLs'))
        self.assertFalse(self.client.check(force=True)['valid'])
        self.assertNotIn('URLs', self.client.status()['message'])
        import http.client
        self.client.opener = Mock(side_effect=http.client.BadStatusLine('malformed reply'))
        self.assertFalse(self.client.check(force=True)['valid'])
        for payload in ({'valid': True}, {'valid': 'yes'}, {'valid': True, 'server_time': NOW,
                'activated_at': NOW, 'expires_at': NOW + 30 * 86400 + 1}):
            self.client.opener = lambda *a, **k: io.BytesIO(json.dumps(payload).encode())
            with self.assertRaises(LicenseError): self.client.require()

    def test_failed_activation_keeps_previous_valid_key_and_persisted_id(self):
        self.client.activate(KEY)
        self.online.allowed = False
        with self.assertRaises(LicenseError): self.client.activate('SV1-' + 'b' * 43)
        self.assertEqual(json.loads(self.path.read_text())['key'], KEY)
        self.assertEqual(self.client.key, KEY)

    def test_invalid_local_key_and_remote_transport_rejected(self):
        for key in ('', 'fake', None, 1):
            with self.assertRaises(LicenseError): self.client.activate(key)
        for url in ('http://example.com/license', 'https://user:secret@example.com/', 'https://example.com/?key=secret'):
            with self.assertRaises(LicenseError): LicenseClient(self.path, url)
        with self.assertRaises(LicenseError):
            NoRedirect().redirect_request(None, None, 302, '', {}, 'https://elsewhere.example/')

    def test_engine_gates_direct_starts_saves_and_monitors(self):
        with patch('spankvanc.engine.doctor', return_value={}):
            engine = Engine(Path(self.temp.name)/'route', license_client=self.client)
        for action in (engine.start, engine.monitor_start, engine.save):
            with self.assertRaises(LicenseError): action({})
        self.assertFalse(engine.state()['plan']['ready'])

    def test_watchdog_stops_both_route_and_monitor_after_revocation(self):
        self.client.activate(KEY)
        with patch('spankvanc.engine.doctor', return_value={}):
            engine = Engine(Path(self.temp.name)/'route', license_client=self.client)
        engine.process = Mock(); engine.process.poll.return_value = None
        self.elapsed = 60
        self.online.allowed = False
        with patch.object(engine, 'stop') as stop, patch.object(engine, 'monitor_stop') as monitor_stop:
            engine.license_tick()
            stop.assert_called_once(); monitor_stop.assert_called_once()
        self.assertFalse(engine.state()['license']['valid'])

    def test_watchdog_terminates_real_child_processes(self):
        import subprocess, sys
        self.client.activate(KEY)
        with patch('spankvanc.engine.doctor', return_value={}):
            engine = Engine(Path(self.temp.name)/'route', license_client=self.client)
        route = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
        monitor = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
        engine.process, engine.monitor_process = route, monitor
        try:
            self.elapsed = 60
            self.online.allowed = False
            engine.license_tick()
            self.assertIsNotNone(route.poll())
            self.assertIsNotNone(monitor.poll())
        finally:
            for child in (route, monitor):
                if child.poll() is None: child.kill()
                child.wait()

    def test_expiry_during_model_load_never_opens_media_and_cleans_worker(self):
        from test_whisper import WhisperTests
        cfg, capabilities = WhisperTests().route()
        self.client.activate(KEY)
        with patch('spankvanc.engine.doctor', return_value=capabilities):
            engine = Engine(Path(self.temp.name)/'route', license_client=self.client)
        worker = Mock()
        def prepare(*args):
            self.online.allowed = False
            return worker, Path(self.temp.name)/'journal'
        with patch('spankvanc.whisper_runtime.prepare', side_effect=prepare), patch('spankvanc.engine.subprocess.Popen') as spawn:
            with self.assertRaises(LicenseError): engine.start(cfg)
            spawn.assert_not_called()
            worker.kill.assert_called_once(); worker.wait.assert_called_once()
