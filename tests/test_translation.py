import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from spankvanc.translation import TranslationPreview
from spankvanc.engine import Engine


class TranslationTests(unittest.TestCase):
    def test_uninstalled_and_invalid_requests(self):
        with tempfile.TemporaryDirectory() as folder:
            preview=TranslationPreview(Path(folder)/'runtime')
            for text in (None, '', 'x'*2001, 'hello'):
                with self.assertRaises(ValueError):preview.submit(text)
            self.assertIsNone(preview.process)

    def test_installer_runtime_path_is_detected(self):
        with tempfile.TemporaryDirectory() as folder:
            preview=TranslationPreview(Path(folder)/'runtime')
            python=preview.home/'python/python.exe'
            python.parent.mkdir(parents=True);python.touch()
            model=preview.home/'model/ct2/model.bin'
            model.parent.mkdir(parents=True);model.touch()
            self.assertEqual(preview.python_path(),python)
            self.assertTrue(preview.available())

    def test_bounded_queue(self):
        with tempfile.TemporaryDirectory() as folder:
            preview=TranslationPreview(Path(folder)/'runtime')
            model=preview.home/'model'/'ct2'/'model.bin'
            model.parent.mkdir(parents=True);model.touch()
            preview.thread=object() # keep inference paused to exercise overload
            for i in range(8):preview.submit(str(i))
            with self.assertRaisesRegex(ValueError, 'busy'):preview.submit('overflow')
            self.assertEqual(preview.state()['dropped'],1)
            self.assertEqual(preview.state()['pending'],8)

    def test_whisper_preview_failure_preserves_log(self):
        engine=object.__new__(Engine)
        engine.logs=[]
        with patch('spankvanc.translation.TranslationPreview') as cls:
            engine.translation=cls.return_value
            engine.translation.submit.side_effect=ValueError('busy')
            engine._whisper_log('Whisper CC1: Good evening.')
            engine.translation.submit.assert_called_once_with('Good evening.')
            self.assertEqual(engine.logs,['Whisper CC1: Good evening.'])
