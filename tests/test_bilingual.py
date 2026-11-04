import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from spankvanc.bilingual import BilingualJournal, encode_spanish
from spankvanc.captions import SourceMonitor
from spankvanc.engine import validate, plan, command, ConfigError
from spankvanc.whisper_worker import encode_text
import test_whisper


def decode(payload):
    monitor=SourceMonitor()
    triplets=b''.join(b'\xfc'+payload[i:i+2] for i in range(0,len(payload),2))
    monitor.feed({'signal':True,'cc':triplets.hex()})
    return [service.text() for service in monitor.services]


class BilingualTests(unittest.TestCase):
    def test_spanish_accents_channel_and_extended_replacement(self):
        for text in ['¡Sí! ¿Qué pasó? El niño está aquí.', 'ÁÉÍÓÚÜ ü ñ Ñ á é í ó ú', 'a'*31+'Á', 'Niña: “¡Hola!”']:
            data=encode_spanish(text)
            self.assertTrue(all(v.bit_count()%2 for v in data))
            decoded=decode(data)
            self.assertEqual(decoded[0],'')
            self.assertEqual(decoded[2: ],['',''])
            self.assertEqual(decoded[1].replace('\n',' '), text.replace('“','"').replace('”','"'))

    def test_language_switching_is_isolated(self):
        data=encode_text('English first.')+encode_spanish('Español aquí.')+encode_text('English next.')+encode_spanish('¡Buenas noches!')
        decoded=decode(data)
        self.assertEqual(decoded[:2],['English first.\nEnglish next.','Español aquí.\n¡Buenas noches!'])

    def test_budget_closed_route_and_manual_preview_isolation(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch('spankvanc.bilingual.time.monotonic',return_value=100):
                journal=BilingualJournal(Path(folder)/'pairs')
                self.assertTrue(journal.english('Good evening.'))
                self.assertTrue(journal.spanish('Buenas noches.'))
                for i in range(15):journal.spanish('More Spanish text to fill the caption budget.')
                self.assertGreater(journal.skipped,0)
                self.assertLessEqual(journal.end,104)
                size=journal.path.stat().st_size
                journal.close()
                self.assertFalse(journal.spanish('Late stale translation.'))
                self.assertEqual(journal.path.stat().st_size,size)

    def test_validation_defaults_and_capability_gates(self):
        cfg,cap=test_whisper.WhisperTests().route()
        self.assertFalse(validate(cfg)['outputs'][0]['spanish_cc2'])
        cfg['outputs'][0]['spanish_cc2']=True
        self.assertFalse(plan(cfg,cap)['ready'])
        cap.update(translation_available=True,bilingual_decklink=True,caption_formats_decklink=True)
        self.assertTrue(plan(cfg,cap)['ready'])
        for field,value in [('captions','pass'),('captions','strip'),('caption_format','708'),('spanish_cc2','true')]:
            invalid=copy.deepcopy(cfg);invalid['outputs'][0][field]=value
            with self.assertRaises(ConfigError):validate(invalid)
        cfg['whisper']['language']='es'
        with self.assertRaises(ConfigError):validate(cfg)

    def test_selected_outputs_only_use_bilingual_journal(self):
        cfg,cap=test_whisper.WhisperTests().route()
        cfg['outputs'][0].update(spanish_cc2=True,caption_format='both')
        cfg['outputs'].append(dict(cfg['outputs'][0],name='English',address='english.ts',spanish_cc2=False))
        cfg['outputs'].append(dict(cfg['outputs'][0],name='Pass',address='pass.ts',spanish_cc2=False,captions='pass'))
        args=command(validate(cfg),cap,'/tmp/english.pairs',bilingual_journal='/tmp/bilingual.pairs')
        filters=[args[i+1] for i,v in enumerate(args) if v=='-vf']
        self.assertIn(Path('/tmp/bilingual.pairs').as_posix().encode().hex(),filters[0])
        self.assertIn(':cc2=1',filters[0])
        self.assertIn(Path('/tmp/english.pairs').as_posix().encode().hex(),filters[1])
        self.assertNotIn(':cc2=1',filters[1])
        self.assertEqual(args.count('-i'),1)
