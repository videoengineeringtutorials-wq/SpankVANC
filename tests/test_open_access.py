"""Application access remains available with no key, network or license state."""
import json
from pathlib import Path
import tempfile
from unittest import TestCase, mock

from spankvanc.engine import Engine
from test_core import CAP, route
from test_decklink import DEVICE, route as deck_route


class OpenAccessTests(TestCase):
    @mock.patch('urllib.request.urlopen', side_effect=OSError('Offline'))
    @mock.patch('spankvanc.engine.doctor', return_value=CAP)
    def test_offline_startup_save_and_refresh_ignore_expired_license(self, doctor, network):
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder)
            (state/'license.json').write_text(json.dumps({'key':'obsolete','expires_at':1}))
            engine = Engine(state)
            engine.save(route())
            self.assertTrue(engine.state()['plan']['ready'])
            self.assertNotIn('license', engine.state())
            engine.refresh_devices()
            self.assertEqual(doctor.call_count, 2)
            network.assert_not_called()

    @mock.patch('urllib.request.urlopen', side_effect=OSError('Offline'))
    @mock.patch('spankvanc.engine.threading.Thread')
    @mock.patch('spankvanc.engine.subprocess.Popen')
    @mock.patch('spankvanc.engine.doctor', return_value=CAP)
    def test_route_start_has_no_activation_requirement(self, doctor, popen, thread, network):
        with tempfile.TemporaryDirectory() as folder:
            engine = Engine(Path(folder))
            popen.return_value.poll.return_value = None
            result = engine.start(route())
            self.assertTrue(result['running'])
            popen.assert_called_once()
            network.assert_not_called()

    @mock.patch('urllib.request.urlopen', side_effect=OSError('Offline'))
    @mock.patch('spankvanc.engine.threading.Thread')
    @mock.patch('spankvanc.engine.subprocess.Popen')
    @mock.patch('spankvanc.engine.doctor')
    def test_source_monitor_has_no_activation_requirement(self, doctor, popen, thread, network):
        doctor.return_value = dict(CAP, source_monitor=True, decklink_input=True, decklink_devices=[DEVICE])
        with tempfile.TemporaryDirectory() as folder:
            engine = Engine(Path(folder))
            popen.return_value.poll.return_value = None
            self.assertTrue(engine.monitor_start(deck_route())['monitor_running'])
            popen.assert_called_once()
            network.assert_not_called()
