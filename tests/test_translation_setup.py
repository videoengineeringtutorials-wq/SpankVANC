"""Optional installer translation step: caching, failure preservation and scope."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch

spec=importlib.util.spec_from_file_location('translation_setup',Path(__file__).resolve().parents[1]/'windows/translation_setup.py')
helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)


class TranslationSetupTests(unittest.TestCase):
    def fixture(self,folder):
        setup=Mock();setup.root=Path(folder)/'app';setup.root.mkdir()
        setup.data=Path(folder)/'data';setup.data.mkdir()
        setup.python=setup.data/'speech-python/python.exe'
        setup.deps={'translation':{'revision':'test','runtime_packages':['ctranslate2==4.6.0'],
                                  'converter_packages':['transformers==4.57.6'],'source_files':{},'base_url':'https://example.invalid'}}
        python=helper.python_path(setup.root/'translation');python.parent.mkdir(parents=True);python.touch()
        return setup

    def cached(self,setup):
        model=setup.root/'translation/model';model.mkdir()
        (model/'fixture').write_bytes(b'model')
        (model/'provenance.json').write_text(json.dumps({'revision':'test','sha256':{'fixture':hashlib.sha256(b'model').hexdigest()}}))
        return model

    def test_cached_model_avoids_conversion_and_download(self):
        with tempfile.TemporaryDirectory() as folder:
            setup=self.fixture(folder);self.cached(setup)
            with patch.object(helper,'verify') as verify:helper.install(setup)
            setup.download.assert_not_called();verify.assert_called_once()
            commands=[c.args[0] for c in setup.command.call_args_list]
            self.assertEqual(len(commands),1)
            self.assertEqual(commands[0][0],helper.python_path(setup.root/'translation'))

    def test_conversion_failure_keeps_previous_model(self):
        with tempfile.TemporaryDirectory() as folder:
            setup=self.fixture(folder);model=self.cached(setup)
            (model/'fixture').write_bytes(b'old corrupt cached content')
            def run(args,**kwargs):
                if '-c' in args:raise RuntimeError('conversion failed')
            setup.command.side_effect=run
            with self.assertRaisesRegex(RuntimeError,'conversion failed'):helper.install(setup)
            self.assertEqual((model/'fixture').read_bytes(),b'old corrupt cached content')
            installs=[c.args[0] for c in setup.command.call_args_list if '--target' in c.args[0]]
            self.assertEqual(len(installs),1)
            self.assertEqual(installs[0][0],setup.python)
            self.assertNotEqual(installs[0][installs[0].index('--target')+1],setup.python.parent)

    def test_inference_verification_rejects_empty_translation(self):
        with tempfile.TemporaryDirectory() as folder:
            setup=self.fixture(folder);setup.command.return_value='{"ready":true}\n{"error":"failed"}\n'
            with self.assertRaises(ValueError):helper.verify(setup,Path('python'),Path('model'))
            setup.command.return_value='{"ready":true}\n{"spanish":"Buenas noches."}\n'
            helper.verify(setup,Path('python'),Path('model'))
