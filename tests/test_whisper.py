import copy
from pathlib import Path
import tempfile
import unittest
from spankvanc.engine import DEFAULT,validate,plan,command,ConfigError,Engine
from spankvanc.whisper_worker import encode_text,odd,wrap_words
from spankvanc.captions import Service

class WhisperTests(unittest.TestCase):
    def test_608_parity_controls_wrap_and_decoder(self):
        encoded=encode_text('This is a live caption. Café — “yes”. '+ 'A'*45,True)
        self.assertTrue(all(v.bit_count()%2==1 for v in encoded))
        pairs=[tuple(v&127 for v in encoded[i:i+2]) for i in range(0,len(encoded),2)]
        self.assertEqual(pairs[:10],[(20,44)]*2+[(20,37)]*2+[(20,45)]*2+[(20,112)]*2+[(20,36)]*2)
        decoder=Service();columns=0
        for a,b in pairs:
            decoder.pair(a,b)
            self.assertLessEqual(decoder.column,32)
        self.assertEqual(decoder.text().count('A'),45)
        self.assertTrue(all(len(line)<=32 for line in decoder.text().splitlines()))
        # Reserved ASCII glyphs must not accidentally become accented letters.
        encoded=encode_text('x\\^_`{|}~*',True)
        decoder=Service()
        for i in range(0,len(encoded),2):decoder.pair(encoded[i]&127,encoded[i+1]&127)
        self.assertIn('x?????????',decoder.text())
        self.assertEqual(encode_text('  '),b'')

    def route(self):
        cfg=copy.deepcopy(DEFAULT);cfg['input'].update(kind='file',address='source.ts')
        cfg['outputs']=[dict(name='Whisper',kind='file',address='out.ts',captions='recaption',scte='strip',enabled=True)]
        cap=dict(ffmpeg='ffmpeg',libx264=True,aac=True,recaption_decklink=True,
                 whisper=dict(available=True,cuda=True,models=['small.en']))
        return cfg,cap

    def test_gates_and_preview(self):
        cfg,cap=self.route()
        self.assertTrue(plan(cfg,cap)['ready'])
        self.assertIn('pipe:1',plan(cfg,cap)['command'])
        for key,value in [('recaption_decklink',False),('whisper',{'available':False})]:
            self.assertFalse(plan(cfg,dict(cap,**{key:value}))['ready'])
        cfg['whisper']['device']='cuda';cap['whisper']['cuda']=False
        self.assertFalse(plan(cfg,cap)['ready'])
        with self.assertRaises(ConfigError):command(validate(cfg),cap)

    def test_single_capture_and_independent_outputs(self):
        cfg,cap=self.route();cfg['whisper']['audio_channel']=2
        for policy in ('pass','strip'):
            cfg['outputs'].append(dict(name=policy,kind='file',address=policy+'.ts',captions=policy,scte='strip',enabled=True))
        args=command(validate(cfg),cap,Path('/tmp/a journal.pairs'))
        self.assertEqual(args.count('-i'),1)
        self.assertEqual(sum('spankvanc_cc=journal=' in arg for arg in args),1)
        self.assertEqual(args.count('sidedata=mode=delete:type=A53_CC'),1)
        self.assertIn('channelmap=map=1:channel_layout=mono',args)
        self.assertEqual(args[-1],'pipe:1')
        self.assertEqual(args[args.index('-a53cc')+1],'1')

    def test_sdi_replacement_keeps_scte(self):
        cfg,cap=self.route();cfg['input'].update(kind='decklink',address='in',format_code='Hi59')
        cfg['outputs'][0].update(kind='decklink',address='out',video_codec='uncompressed',scte='pass')
        args=command(validate(cfg),cap,'/tmp/journal')
        for flag in ('-spankvanc_scte104','-spankvanc_scte_output','-spankvanc_caption_output'):
            self.assertEqual(args[args.index(flag)+1],'1')
        self.assertEqual(args.count('-i'),1)

    def test_legacy_settings_and_invalid_device(self):
        cfg,cap=self.route();self.assertEqual(validate(cfg)['whisper']['device'],'auto')
        cfg['whisper']['device']='nvenc'
        with self.assertRaises(ConfigError):validate(cfg)

    def test_worker_failure_is_reported_even_if_broken_pipe_stops_route_first(self):
        from unittest.mock import Mock
        engine=Engine.__new__(Engine)
        route=Mock();route.poll.return_value=22
        worker=Mock();worker.wait.return_value=1
        engine.process=route;engine.stop_requested=False;engine.logs=[]
        engine._watch_whisper(worker,route)
        self.assertTrue(any('Whisper worker exited' in s for s in engine.logs))
        route.terminate.assert_not_called()
        engine.logs=[];engine.process=Mock()
        engine._watch_whisper(worker,route)
        self.assertEqual(engine.logs,[])

    def test_whole_words_at_row_boundary_and_long_word_preservation(self):
        self.assertEqual(wrap_words('A'*30+' hello world'),['A'*30,'hello world'])
        self.assertEqual(wrap_words('prefix '+'B'*45+' suffix'),['prefix','B'*32,'B'*13+' suffix'])
        self.assertEqual(wrap_words('A'*32+' word'),['A'*32,'word'])
        self.assertEqual(wrap_words('A'*31+' x'),['A'*31,'x'])

    def test_late_joiner_gets_rollup_mode_and_explicit_column_zero(self):
        decoder=Service()
        encoded=encode_text('A new receiver can decode this',False)
        for i in range(0,len(encoded),2):decoder.pair(encoded[i]&127,encoded[i+1]&127)
        self.assertEqual(decoder.text(),'A new receiver can decode this')
        self.assertEqual(decoder.mode,'roll')
        # A full row followed by a short one must not stick at column 31.
        for text in ('A'*32,'short next row'):
            encoded=encode_text(text,False)
            for i in range(0,len(encoded),2):decoder.pair(encoded[i]&127,encoded[i+1]&127)
        self.assertEqual(decoder.text(),'A'*32+'\nshort next row')

    def test_youtube_replacement_uses_one_fps_stage_before_caption_insertion(self):
        cfg,cap=self.route()
        cfg['outputs'][0].update(kind='youtube',address='',youtube_server='rtmps://a.rtmps.youtube.com:443/live2',youtube_stream_key='fixture')
        args=command(validate(cfg),cap,'/tmp/journal')
        self.assertEqual(args[args.index('-fps_mode:v')+1],'passthrough')
        self.assertNotIn('-r:v',args)
        vf=args[args.index('-vf')+1]
        self.assertLess(vf.index('fps=30'),vf.index('spankvanc_cc'))
        cfg['outputs'][0]['captions']='pass'
        args=command(validate(cfg),cap)
        self.assertEqual(args[args.index('-fps_mode:v')+1],'cfr')
        self.assertEqual(args[args.index('-r:v')+1],'30')
