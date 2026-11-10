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

    def test_null_serial_only_requires_no_video_engine_or_destination(self):
        from unittest.mock import patch
        cfg,cap=self.route()
        cfg['outputs'][0].update(kind='null',address='')
        cfg['whisper']['serial_port']='COM6'
        cap.update(libx264=False,aac=False,recaption_decklink=False)
        cap['whisper']['serial']=True
        result=plan(cfg,cap)
        self.assertTrue(result['ready'],result['blockers'])
        self.assertEqual(result['outputs'][0]['video_codec'],'none')
        with patch('spankvanc.engine.executable',return_value='ffmpeg') as executable:
            args=command(validate(cfg),cap)
        executable.assert_called_once_with(False)
        self.assertIn('pipe:1',args)
        for option in ('-c:v','-vf','-a53cc','-c:a'):
            self.assertEqual(args.count(option),1 if option=='-c:a' else 0)
        self.assertEqual(args[args.index('-c:a')+1],'pcm_f32le')
        self.assertEqual(args.count('-i'),1)
        cfg['whisper']['serial_port']=''
        self.assertTrue(any('EN530 serial port' in b for b in plan(cfg,cap)['blockers']))
        cfg['whisper']['serial_port']='COM6';cap['whisper']['serial']=False
        self.assertFalse(plan(cfg,cap)['ready'])

    def test_null_and_video_share_one_capture_and_speech_pipe(self):
        cfg,cap=self.route()
        cfg['whisper']['serial_port']='COM6';cap['whisper']['serial']=True
        cfg['outputs'].append(dict(name='Serial',kind='null',address='',captions='pass',scte='strip',enabled=True))
        self.assertTrue(plan(cfg,cap)['ready'])
        args=command(validate(cfg),cap,'/tmp/journal')
        self.assertEqual(args.count('-i'),1)
        self.assertEqual(args.count('pipe:1'),1)
        self.assertEqual(sum('spankvanc_cc=journal=' in a for a in args),1)

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

class FasterWhisperTests(unittest.TestCase):
    def segment(self, words, probability=0):
        from types import SimpleNamespace as NS
        return NS(no_speech_prob=probability, words=[NS(word=w, end=e) for w,e in words], text='')

    def test_overlapping_windows_timestamp_shift_and_real_repetition(self):
        from spankvanc.whisper_worker import WordCommitter
        c=WordCommitter()
        self.assertEqual(c.commit([self.segment([('Hello,',1),('world',2),('later',3.9)])],0,3.65),'Hello, world')
        self.assertEqual(c.commit([self.segment([('world!',.2),('later',1.9),('world',3)])],2,5.65),'later world')
        self.assertEqual(c.commit([self.segment([('noise',5)],.9)],2,9),'')

    def test_missing_timestamps_fallback(self):
        from types import SimpleNamespace as NS
        from spankvanc.whisper_worker import WordCommitter
        c=WordCommitter()
        self.assertEqual(c.commit([NS(no_speech_prob=0,words=None,text='Hello world')],0,4),'Hello world')
        self.assertEqual(c.commit([NS(no_speech_prob=0,words=None,text='world again')],2,6),'again')

    def test_en530_wire_format_and_recovery(self):
        import sys
        from types import SimpleNamespace as NS
        from unittest.mock import Mock, patch
        from spankvanc.whisper_worker import EN530Sender,en530_frames
        frames=en530_frames('“Hello”… '+ 'A'*70+'\x01')
        self.assertTrue(all(f.startswith(b'\x01 ') and f.endswith(b'\r') and len(f)<=35 for f in frames))
        self.assertTrue(all(all(32<=v<127 for v in f[2:-1]) for f in frames))
        port=Mock();port.write.side_effect=lambda data:len(data)
        port.readline.side_effect=[b'E1\r',b'OK\r']
        module=NS(Serial=Mock(return_value=port),SEVENBITS=7,PARITY_ODD='O',STOPBITS_ONE=1)
        with patch.dict(sys.modules,serial=module):
            sender=EN530Sender('COM6');sender.submit('hello');sender.close()
        self.assertEqual([c.args[0] for c in port.write.call_args_list],[b'\x01 hello\r',b'\x012\r'])
        self.assertEqual(module.Serial.call_args.kwargs['baudrate'],1200)
        port.close.assert_called_once()

    def test_backend_preflight_and_legacy_defaults(self):
        cfg,cap=WhisperTests().route()
        self.assertEqual(validate(cfg)['whisper']['backend'],'openai')
        cfg['whisper'].update(backend='faster',serial_port='COM6')
        self.assertFalse(plan(cfg,cap)['ready'])
        cap['whisper'].update(faster=dict(available=True,cuda=True,models=['small.en']),serial=True)
        self.assertTrue(plan(cfg,cap)['ready'])
        cfg['whisper']['compute_type']='bogus'
        with self.assertRaises(ConfigError):validate(cfg)
