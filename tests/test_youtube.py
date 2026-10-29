"""YouTube destination assembly, migration and credential redaction."""
import json
import unittest
from spankvanc.engine import validate,plan,command,YOUTUBE_SERVER,ConfigError
from test_core import route,CAP

class YouTubeTests(unittest.TestCase):
    def config(self,**fields):
        cfg=route();cfg['outputs'][0].update(kind='youtube',address='',**fields)
        return cfg

    def test_separate_fields_build_destination_and_hide_key_in_plan(self):
        cfg=validate(self.config(youtube_server=YOUTUBE_SERVER+'/',youtube_stream_key='fake-test-key'))
        self.assertEqual(cfg['outputs'][0]['address'],YOUTUBE_SERVER+'/fake-test-key')
        self.assertIn(YOUTUBE_SERVER+'/fake-test-key',command(cfg,CAP))
        self.assertNotIn('fake-test-key',json.dumps(plan(cfg,CAP)))
        self.assertEqual(validate(cfg),cfg)

    def test_existing_destination_migrates_and_empty_key_blocks_start(self):
        cfg=self.config();cfg['outputs'][0]['address']='rtmps://a.rtmps.youtube.com/live2/fake-old-key'
        out=validate(cfg)['outputs'][0]
        self.assertEqual(out['youtube_server'],'rtmps://a.rtmps.youtube.com/live2')
        self.assertEqual(out['youtube_stream_key'],'fake-old-key')
        empty=validate(self.config())
        self.assertEqual(empty['outputs'][0]['youtube_server'],YOUTUBE_SERVER)
        self.assertTrue(any('paste a YouTube stream key' in b for b in plan(empty,CAP)['blockers']))

    def test_rejects_pasted_urls_and_invalid_servers_without_echoing_keys(self):
        for key in ('rtmps://example.com/live/SECRET','bad key','bad\nkey','bad?key'):
            with self.assertRaises(ConfigError) as error:validate(self.config(youtube_stream_key=key))
            self.assertNotIn(key,str(error.exception))
        for server in ('rtmp://example.com/live','rtmps://example.com','rtmps://user:pass@example.com/live','rtmps://example.com/live?x=1'):
            with self.assertRaises(ConfigError):validate(self.config(youtube_server=server,youtube_stream_key='fake-key'))

    def test_youtube_profile_does_not_inherit_interlace_or_crf(self):
        from test_windows_compat import route as deck_route,LEGACY
        cfg=deck_route();cfg['outputs'].append(dict(cfg['outputs'][0],name='YouTube',kind='youtube',address='',youtube_stream_key='fake-key'))
        args=command(validate(cfg),LEGACY)
        youtube=args[args.index('capture.ts')+1:]
        self.assertNotIn('+ilme+ildct',youtube);self.assertNotIn('tff=1',youtube)
        self.assertNotIn('-crf',youtube);self.assertNotIn('demux',youtube)
        self.assertEqual(youtube[youtube.index('-field_order')+1],'progressive')
        self.assertEqual(youtube[youtube.index('-g')+1],'60')
        self.assertIn('14M',youtube);self.assertIn('yadif=',youtube[youtube.index('-vf')+1])
        self.assertIn('+ilme+ildct',args[:args.index('capture.ts')])
        self.assertFalse(plan(validate(cfg),dict(LEGACY,youtube_profiles={}))['ready'])

    def test_selectable_bitrate_applies_to_rate_control_and_persists(self):
        for rate in (6, 8, 10, 14):
            cfg = validate(self.config(youtube_stream_key='fake-key', youtube_bitrate_mbps=rate))
            self.assertEqual(validate(cfg), cfg)
            args = command(cfg, CAP)
            for flag in ('-b:v', '-minrate:v', '-maxrate:v'):
                self.assertEqual(args[args.index(flag)+1], f'{rate}M')
            self.assertEqual(args[args.index('-bufsize:v')+1], f'{rate*2}M')
            self.assertTrue(any(f'{rate} Mbit/s CBR' in n for n in plan(cfg, CAP)['notes']))
            cfg['outputs'][0]['kind'] = 'file'
            cfg['outputs'][0]['address'] = 'output.ts'
            self.assertNotIn('youtube_bitrate_mbps', validate(cfg)['outputs'][0])
        self.assertEqual(validate(self.config())['outputs'][0]['youtube_bitrate_mbps'], 14)
        for invalid in (True, '8', None, 0, 7, 15, 8.0):
            with self.assertRaises(ConfigError):
                validate(self.config(youtube_bitrate_mbps=invalid))
