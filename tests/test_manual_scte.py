import copy
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.parse import urlsplit, parse_qs

from spankvanc.engine import Engine, DEFAULT, ConfigError, validate, command, plan
from spankvanc.manual_scte import section, crc, prepare_journals
from test_core import CAP, route

ROOT = Path(__file__).resolve().parent.parent

class ManualScteTests(unittest.TestCase):
    def test_immediate_cues_decode_to_104_and_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            reverse = Path(folder)/'reverse'
            subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror',str(ROOT/'native/check_scte_output.cpp'),'-o',str(reverse)],check=True)
            forward = Path(folder)/'forward'
            subprocess.run(['g++','-std=c++17',str(ROOT/'native/check_scte.cpp'),'-o',str(forward)],check=True)
            for action in ('start', 'end'):
                cue = section(123, action, 60.1)
                self.assertEqual(crc(cue), 0)
                result = subprocess.run([str(reverse),cue.hex(),'90000'],capture_output=True,text=True,check=True)
                decoded = subprocess.run([str(forward),','.join(result.stdout.splitlines()),'90000'],capture_output=True,text=True,check=True)
                self.assertEqual(bytes.fromhex(decoded.stdout.strip()), cue)
            for duration in (0,6553.6,0.11,True,'nan','inf',None):
                with self.assertRaises(ConfigError): section(1,'start',duration)

    def test_journal_output_isolation_and_live_guards(self):
        with tempfile.TemporaryDirectory() as folder, patch('spankvanc.engine.doctor',return_value=CAP):
            engine = Engine(Path(folder))
            cfg = route()
            cfg['outputs'][0]['scte']='manual'
            cfg['outputs'].append(dict(cfg['outputs'][0],name='Second'))
            engine.manual_journals = prepare_journals(Path(folder),cfg)
            with self.assertRaises(ConfigError): engine.inject_scte({'output':0,'action':'start'})
            engine.process = Mock(); engine.process.poll.return_value = None
            result=engine.inject_scte({'output':0,'action':'start','duration':30})
            with self.assertRaises(ConfigError): engine.inject_scte({'output':0,'action':'start'})
            for index in (True,-1,2):
                with self.assertRaises(ConfigError): engine.inject_scte({'output':index,'action':'start'})
            end=engine.inject_scte({'output':0,'action':'end'})
            self.assertEqual(result['event_id'],end['event_id'])
            self.assertEqual(engine.manual_journals[0].stat().st_size,128)
            self.assertEqual(engine.manual_journals[1].stat().st_size,0)
            fresh=prepare_journals(Path(folder),cfg)
            self.assertNotEqual(fresh,engine.manual_journals)
            self.assertTrue(all(p.stat().st_size==0 for p in fresh.values()))

    def test_route_requires_new_engine_and_only_maps_av(self):
        cfg=route();cfg['outputs'][0]['scte']='manual'
        self.assertFalse(plan(cfg,CAP)['ready'])
        self.assertTrue(plan(cfg,dict(CAP,manual_scte35=True))['ready'])
        args=command(validate(cfg),CAP,manual_journals={0:'cue.bin'})
        self.assertIn('cue.bin',args)
        self.assertNotIn('0:d:0',args)
        self.assertNotIn('-spankvanc_scte35',args)
        for kind in ('rtmp','youtube'):
            cfg['outputs'][0].update(kind=kind,address='')
            with self.assertRaises(ConfigError): validate(cfg)

    def test_srt_modes_preserve_options_and_migrate_urls(self):
        for mode in ('caller','listener','rendezvous'):
            cfg=route();cfg['input'].update(kind='srt',address='srt://127.0.0.1:9000?mode=listener&streamid=a%26b&latency=200000')
            cfg['outputs'][0].update(kind='srt',address='srt://127.0.0.1:9001?passphrase=secretsecret&localport=9002',srt_mode=mode)
            normalized=validate(cfg)
            self.assertEqual(normalized['input']['srt_mode'],'listener')
            query=parse_qs(urlsplit(normalized['outputs'][0]['address']).query)
            self.assertEqual(query['mode'],[mode]);self.assertEqual(query['localport'],['9002'])
            self.assertEqual(query['passphrase'],['secretsecret'])
            self.assertEqual(parse_qs(urlsplit(normalized['input']['address']).query)['streamid'],['a&b'])
        cfg['outputs'][0]['srt_mode']='invalid'
        with self.assertRaises(ConfigError):validate(cfg)
