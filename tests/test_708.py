"""Output format migration, capability gates and independent command construction."""
import copy
import unittest
from spankvanc.engine import validate, plan, command, ConfigError
import test_whisper

class Output708Tests(unittest.TestCase):
    def fixture(self):
        cfg,cap=test_whisper.WhisperTests().route()
        cap['caption_formats_decklink']=True
        return cfg,cap

    def test_legacy_caption_behavior_is_preserved(self):
        cfg,cap=self.fixture()
        self.assertEqual(validate(cfg)['outputs'][0]['caption_format'],'608')
        cfg['outputs'][0]['captions']='pass'
        self.assertEqual(validate(cfg)['outputs'][0]['caption_format'],'both')
        args=command(validate(cfg),cap)
        self.assertNotIn('-vf',args)
        self.assertNotIn('pipe:1',args)

    def test_three_generated_formats_have_independent_filters(self):
        cfg,cap=self.fixture()
        cfg['outputs']=[dict(cfg['outputs'][0],name=mode,address=mode+'.ts',caption_format=mode) for mode in ('608','708','both')]
        args=command(validate(cfg),cap,'/tmp/fixture.pairs')
        filters=[args[i+1] for i,arg in enumerate(args) if arg=='-vf']
        self.assertEqual(len(filters),3)
        self.assertNotIn(':format=',filters[0])
        self.assertTrue(filters[1].endswith(':format=cea708'))
        self.assertTrue(filters[2].endswith(':format=both'))
        self.assertEqual(args.count('-i'),1)
        self.assertEqual(args.count('pipe:1'),1)
        for mode in ('708','both'):
            cfg['outputs']= [dict(cfg['outputs'][0],caption_format=mode)]
            self.assertTrue(plan(cfg,cap)['ready'])
            self.assertFalse(plan(cfg,dict(cap,caption_formats_decklink=False))['ready'])
        cfg['outputs'][0]['caption_format']='invalid'
        with self.assertRaises(ConfigError):validate(cfg)

    def test_sdi_service_announcement_and_scte_are_independent(self):
        cfg,cap=self.fixture()
        cfg['input'].update(kind='decklink',address='input',format_code='Hi59')
        cfg['outputs'][0].update(kind='decklink',address='output',video_codec='uncompressed',caption_format='both',scte='pass')
        args=command(validate(cfg),cap,'/tmp/fixture.pairs')
        self.assertEqual(args[args.index('-spankvanc_caption_format')+1],'3')
        self.assertEqual(args[args.index('-spankvanc_caption_language')+1],'eng')
        self.assertEqual(args[args.index('-spankvanc_scte_output')+1],'1')
        cfg['outputs'][0]['caption_format']='708'
        args=command(validate(cfg),cap,'/tmp/fixture.pairs')
        self.assertEqual(args[args.index('-spankvanc_caption_format')+1],'2')

    def test_pass_selects_types_without_source_conversion_or_speech(self):
        cfg,cap=self.fixture();cfg['outputs'][0].update(captions='pass',caption_format='708')
        args=command(validate(cfg),cap)
        self.assertIn('spankvanc_cc=source=1:format=cea708',args)
        self.assertNotIn('pipe:1',args)
        self.assertNotIn('-spankvanc_caption_format',args)
        cfg['outputs'][0]['captions']='strip'
        args=command(validate(cfg),cap)
        self.assertNotIn('spankvanc_cc=source=1:format=cea708',args)
        self.assertIn('sidedata=mode=delete:type=A53_CC',args)
