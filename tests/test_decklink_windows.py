"""Windows COM discovery response integration without hardware in CI."""
import copy
import json
from types import SimpleNamespace
from unittest import TestCase, mock

from spankvanc.decklink_windows import discover_attributes, enrich_devices
from spankvanc.engine import plan
import test_decklink


class WindowsDeckLinkAttributesTests(TestCase):
    def test_actual_half_duplex_report_blocks_only_same_subdevice(self):
        fixture = test_decklink.DeckLinkOutputTests(); fixture.setUp()
        name = fixture.cfg['input']['address']
        fixture.cfg['outputs'][0]['address'] = name
        fixture.cap['decklink_outputs'].append({'name': name, 'output': True})
        original = copy.deepcopy(fixture.cap['decklink_devices'][0]['modes'])
        enrich_devices(fixture.cap, [{'name': name, 'model': 'DeckLink SDI', 'duplex': 'half', 'profile_id': 0}])
        self.assertEqual(fixture.cap['decklink_devices'][0]['modes'], original)
        self.assertFalse(plan(fixture.cfg, fixture.cap)['ready'])
        fixture.cfg['outputs'][0]['address'] = fixture.port['name']
        self.assertTrue(plan(fixture.cfg, fixture.cap)['ready'])
        enrich_devices(fixture.cap, [{'name': name, 'duplex': 'full'}])
        fixture.cfg['outputs'][0]['address'] = name
        self.assertTrue(plan(fixture.cfg, fixture.cap)['ready'])

    def test_exact_names_and_failed_discovery_preserve_devices(self):
        cap = {'decklink_outputs': [{'name': 'DeckLink SDI (1)', 'output': True}]}
        before = copy.deepcopy(cap)
        enrich_devices(cap, [{'name': 'DeckLink SDI (2)', 'duplex': 'full'}])
        enrich_devices(cap, [])
        self.assertEqual(cap, before)

    @mock.patch('spankvanc.decklink_windows.os', SimpleNamespace(name='nt'))
    @mock.patch('spankvanc.decklink_windows.subprocess.run')
    def test_bounded_child_process_and_failure(self, run):
        devices = [{'name': 'DeckLink SDI (1)', 'duplex': 'half'}]
        run.return_value = SimpleNamespace(returncode=0, stdout=json.dumps(devices))
        self.assertEqual(discover_attributes(), (devices, ''))
        self.assertEqual(run.call_args.kwargs['timeout'], 12)
        run.return_value = SimpleNamespace(returncode=1, stderr='Driver unavailable')
        self.assertEqual(discover_attributes(), ([], 'Driver unavailable'))
        run.return_value = SimpleNamespace(returncode=0, stdout='invalid')
        self.assertTrue(discover_attributes()[1])
