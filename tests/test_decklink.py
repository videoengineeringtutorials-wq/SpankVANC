"""DeckLink discovery, validation and command contracts without a test card."""
import copy
import json
from pathlib import Path
from unittest import TestCase, mock

from spankvanc.engine import DEFAULT, ConfigError, command, decklink_devices, plan, validate
from test_core import CAP

DEVICE = {"device": 0, "name": "DeckLink Mini Recorder", "input": True, "output": False,
          "modes": [{"code": "Hi59", "name": "1080i59.94", "duration": 1001, "timescale": 30000}]}


def route():
    cfg = copy.deepcopy(DEFAULT)
    cfg['input'].update(address=DEVICE['name'], format_code='Hi59')
    cfg['outputs'][0].update(kind='file', address='capture.ts', scte='strip')
    return cfg


class DeckLinkTests(TestCase):
    def test_preflight_needs_real_device_mode_and_capture_binary(self):
        cap = dict(CAP, decklink_input=True, decklink_devices=[DEVICE])
        self.assertTrue(plan(route(), cap)['ready'])
        for changed in ({'decklink_input': False}, {'decklink_devices': []}):
            self.assertFalse(plan(route(), dict(cap, **changed))['ready'])
        for code in ('', 'Hi50'):
            cfg = route(); cfg['input']['format_code'] = code
            self.assertFalse(plan(cfg, cap)['ready'])
        cfg = route(); cfg['outputs'][0]['scte'] = 'convert'
        self.assertFalse(plan(cfg, cap)['ready'])
        self.assertFalse(plan(cfg, dict(cap, scte_runtime=True))['ready'])
        self.assertTrue(plan(cfg, dict(cap, scte_runtime=True, scte_recovery=True))['ready'])
        cfg['input']['scte_error_policy']='stop'
        self.assertTrue(plan(cfg, dict(cap, scte_runtime=True))['ready'])
        args=command(validate(cfg),dict(cap,decklink_options=['spankvanc_scte_strict']))
        self.assertEqual(args[args.index('-spankvanc_scte_strict')+1],'1')
        cfg['input']['scte_error_policy']='continue'
        cfg['outputs'].append(dict(cfg['outputs'][0], name='Strip', address='strip.ts', scte='strip'))
        args=command(validate(cfg))
        self.assertEqual(args.count('0:d:0'),1)
        self.assertIn('-spankvanc_scte35',args)
        cfg = route(); cfg['outputs'][0].update(kind='decklink', address='DeckLink Duo', video_codec='uncompressed')
        self.assertFalse(plan(cfg, cap)['ready'])

    def test_capture_uses_named_device_explicit_mode_and_embedded_audio(self):
        cfg = validate(route())
        with mock.patch('spankvanc.engine.executable', return_value='/private/ffmpeg'):
            args = command(cfg)
        self.assertEqual(args[0], '/private/ffmpeg')
        for flag, value in (('-f', 'decklink'), ('-video_input', 'sdi'), ('-audio_input', 'embedded'),
                            ('-channels', '2'), ('-raw_format', 'yuv422p10'),
                            ('-format_code', 'Hi59'), ('-i', DEVICE['name']), ('-field_order', 'tt')):
            self.assertEqual(args[args.index(flag)+1], value)
        self.assertNotIn('-re', args)
        cfg['outputs'].append(dict(cfg['outputs'][0], name='Clean', address='clean.ts', captions='strip'))
        args = command(cfg)
        self.assertEqual(args.count('-i'), 1)
        self.assertIn('sidedata=mode=delete:type=A53_CC', args)

    def test_old_settings_load_and_invalid_modes_fail(self):
        cfg = route(); del cfg['input']['format_code']
        self.assertEqual(validate(cfg)['input']['format_code'], '')
        for invalid in (True, 'Hi59 -x', 'abc', 1234, '\nHi59'):
            cfg['input']['format_code'] = invalid
            with self.assertRaises(ConfigError): validate(cfg)

    @mock.patch('spankvanc.engine.Path.is_file', return_value=True)
    @mock.patch('spankvanc.engine.subprocess.run')
    def test_discovery_uses_stdout_and_does_not_hide_failure(self, run, _):
        run.return_value = mock.Mock(returncode=0, stdout=json.dumps(DEVICE)+'\n', stderr='SDK diagnostic warning')
        self.assertEqual(decklink_devices(), ([DEVICE], ''))
        run.return_value = mock.Mock(returncode=1, stdout='', stderr='Driver unavailable')
        self.assertEqual(decklink_devices(), ([], 'Driver unavailable'))
