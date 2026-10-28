"""Contracts for old FFmpeg/Windows trial; no claim of Windows hardware QA."""
import copy
import importlib.util
from pathlib import Path
import signal
import subprocess
import tempfile
import unittest
from unittest import mock

from spankvanc.engine import DEFAULT, command, plan, validate, terminate_process, process_group_options
from spankvanc.ffmpeg_compat import parse_device_names,parse_modes,discover
from test_core import CAP

DEVICES="""[decklink @ 00001234] Blackmagic DeckLink input devices:
[decklink @ 00001234]     'DeckLink Duo (1)'
[decklink @ 00001234]     'DeckLink Duo (2)'
dummy: Immediate exit requested
"""
MODES="""[decklink @ 00001234] Supported formats for 'DeckLink Duo (1)':
        format_code description
        Hi59        1920x1080 at 30000/1001 fps (interlaced, upper field first)
        hp59        1280x720 at 60000/1001 fps
        pal         720x576 at 25000/1000 fps (interlaced, upper field first)
"""
DEVICE={'name':'DeckLink Duo (1)','input':True,'output':None,'modes':parse_modes(MODES)}
LEGACY=dict(CAP,decklink_input=True,decklink_devices=[DEVICE],decklink_profile='compatibility',
            decklink_options=['format_code','raw_format','draw_bars'],source_monitor=False,scte_runtime=False,
            caption_encoders={'h264':True,'mpeg2video':True},caption_strip_filter=True)


def route():
    cfg=copy.deepcopy(DEFAULT);cfg['input'].update(address=DEVICE['name'],format_code='Hi59')
    cfg['outputs'][0].update(kind='file',address='capture.ts',scte='strip')
    return cfg


class LegacyFFmpegTests(unittest.TestCase):
    def test_device_and_mode_parsing_preserves_original_duo_ports(self):
        self.assertEqual(parse_device_names(DEVICES),['DeckLink Duo (1)','DeckLink Duo (2)'])
        m=parse_modes(MODES);self.assertEqual([v['code'] for v in m],['Hi59','hp59','pal '])
        self.assertEqual((m[0]['timescale'],m[0]['duration']),(30000,1001))
        self.assertFalse(parse_modes('1: 1920x1080 at 30000/1001 fps'))
        with mock.patch('spankvanc.ffmpeg_compat.subprocess.run') as run:
            run.side_effect=[mock.Mock(stdout='',stderr=DEVICES,returncode=1),
                             mock.Mock(stdout='',stderr=MODES,returncode=1),
                             mock.Mock(stdout='',stderr=MODES,returncode=1)]
            devices,error=discover('old-ffmpeg.exe')
            self.assertFalse(error);self.assertEqual(len(devices),2)
            self.assertIsNone(devices[0]['output'])

    def test_legacy_command_omits_custom_and_new_flags(self):
        cfg=validate(route());self.assertTrue(plan(cfg,LEGACY)['ready'])
        args=command(cfg,LEGACY)
        for name in ('-spankvanc_anc','-spankvanc_scte35','-signal_loss_action','-fps_mode:v','-enc_time_base:v','h264_nvenc'):
            self.assertNotIn(name,args)
        self.assertEqual(args[args.index('-vsync')+1],'0')
        self.assertEqual(args[args.index('-draw_bars')+1],'0')
        self.assertIn('libx264',args)
        cfg['outputs'][0]['scte']='convert';self.assertFalse(plan(cfg,LEGACY)['ready'])
        cfg['outputs'][0]['scte']='strip'
        cap=dict(LEGACY,decklink_options=['format_code','bm_v210'])
        args=command(cfg,cap);self.assertIn('-bm_v210',args);self.assertNotIn('-raw_format',args)

    def test_unsupported_caption_and_mode_paths_block(self):
        self.assertFalse(plan(route(),dict(LEGACY,caption_encoders={'h264':False}))['ready'])
        cfg=route();cfg['outputs'][0]['captions']='strip'
        self.assertFalse(plan(cfg,dict(LEGACY,caption_strip_filter=False))['ready'])
        self.assertFalse(plan(cfg,dict(LEGACY,decklink_options=['raw_format']))['ready'])
        args=command(validate(cfg),dict(LEGACY,caption_encoders={'h264':False}))
        self.assertNotIn('-a53cc',args)
        self.assertIn('sidedata=mode=delete:type=A53_CC',args)

    def test_extended_ffmpeg7_uses_draw_bars_not_new_loss_option(self):
        cap=dict(LEGACY,decklink_profile='extended',source_monitor=True,scte_runtime=True)
        cfg=route();cfg['outputs'][0]['scte']='convert'
        args=command(validate(cfg),cap)
        self.assertIn('-spankvanc_anc',args)
        self.assertIn('-spankvanc_scte35',args)
        self.assertIn('-draw_bars',args)
        self.assertNotIn('-signal_loss_action',args)
        self.assertIn('demux',args)

    def test_windows_process_group_and_graceful_stop(self):
        process=mock.Mock()
        with mock.patch('spankvanc.engine.os.name','nt'),mock.patch.object(subprocess,'CREATE_NEW_PROCESS_GROUP',0x200,create=True),mock.patch.object(signal,'CTRL_BREAK_EVENT',1,create=True):
            self.assertEqual(process_group_options(),{'creationflags':0x200})
            terminate_process(process);process.send_signal.assert_called_once_with(1)
            process.terminate.assert_not_called()
            process.send_signal.side_effect=OSError('No console')
            terminate_process(process);process.terminate.assert_called_once()


class PortableLauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p=Path(__file__).resolve().parent.parent/'windows/launcher.py'
        spec=importlib.util.spec_from_file_location('windows_launcher_test',p)
        cls.launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.launcher)

    def test_capture_override_preserves_existing_ffmpeg(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);capture=root/'capture-ffmpeg/ffmpeg.exe';capture.parent.mkdir();capture.touch()
            with mock.patch.dict('os.environ',{},clear=True):
                self.launcher.prepare_environment('existing-ffmpeg.exe',{},root)
                import os
                self.assertEqual(os.environ['SPANKVANC_FFMPEG'],'existing-ffmpeg.exe')
                self.assertEqual(os.environ['SPANKVANC_DECKLINK_FFMPEG'],str(capture.resolve()))
                self.launcher.prepare_environment('existing-ffmpeg.exe',{'decklink_ffmpeg_path':'explicit.exe'},root)
                self.assertEqual(os.environ['SPANKVANC_DECKLINK_FFMPEG'],'explicit.exe')

    def test_ffmpeg_paths_and_safe_initial_route(self):
        with tempfile.TemporaryDirectory(prefix='windows trial ') as d:
            root=Path(d);binary=root/'ffmpeg/ffmpeg.exe';binary.parent.mkdir();binary.touch()
            with mock.patch.dict('os.environ',{},clear=True):
                self.assertEqual(self.launcher.find_ffmpeg({},root),str(binary.resolve()))
            state=root/'runtime';self.launcher.first_route(state,root)
            import json
            cfg=json.loads((state/'route.json').read_text());cfg=validate(cfg)
            self.assertEqual(cfg['outputs'][0]['kind'],'file');self.assertEqual(cfg['outputs'][0]['scte'],'strip')
            self.assertEqual(cfg['input']['address'],'')
            (state/'route.json').write_text('{"existing":"user route"}')
            self.launcher.first_route(state,root)
            self.assertIn('existing',(state/'route.json').read_text())
