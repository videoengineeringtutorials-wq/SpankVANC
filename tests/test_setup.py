"""Guided setup: fail safely, preserve settings, and resume verified components."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,Mock
import zipfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('guided_setup',ROOT/'windows/setup.py')
setup=importlib.util.module_from_spec(spec);spec.loader.exec_module(setup)

class SetupTests(unittest.TestCase):
    def test_archive_rejects_traversal_windows_drives_and_backslashes(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name in ('../escape','/absolute','C:/escape','..\\escape'):
                archive=root/'sdk.zip'
                with zipfile.ZipFile(archive,'w') as z:z.writestr(name,'bad')
                with self.assertRaises(ValueError):setup.safe_extract(archive,root/'out')
            self.assertFalse((root/'escape').exists())

    def test_bad_download_cannot_replace_cached_file_or_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);wizard=setup.Setup(root,root/'data')
            (root/'settings.json').write_text('{"ffmpeg_path":"working.exe","other":42}')
            before=(root/'settings.json').read_bytes()
            wizard.cache.mkdir();cached=wizard.cache/'test.zip';cached.write_bytes(b'old')
            wizard.deps['fixture']={'filename':'test.zip','sha256':hashlib.sha256(b'good').hexdigest(),'url':'https://example.com/test.zip'}
            with patch.object(setup.urllib.request,'urlopen',return_value=io.BytesIO(b'bad')):
                with self.assertRaisesRegex(ValueError,'checksum'):wizard.download('fixture')
            self.assertEqual(cached.read_bytes(),b'old')
            self.assertEqual((root/'settings.json').read_bytes(),before)

    def test_verified_download_is_reused_offline(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);wizard=setup.Setup(root,root/'data');wizard.cache.mkdir()
            (wizard.cache/'fixture').write_bytes(b'verified')
            wizard.deps['fixture']={'filename':'fixture','sha256':hashlib.sha256(b'verified').hexdigest()}
            with patch.object(setup.urllib.request,'urlopen') as download:
                self.assertEqual(wizard.download('fixture').read_bytes(),b'verified');download.assert_not_called()

    def test_speech_failure_keeps_previous_paths_and_no_success_checkpoint(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);wizard=setup.Setup(root,root/'data')
            settings={'ffmpeg_path':'working.exe','whisper_python_path':'existing-python.exe','other':42}
            setup.save_object(wizard.settings,settings)
            wizard.python.parent.mkdir();wizard.python.touch()
            wizard.progress['python_runtime_sha256']=wizard.deps['python']['sha256']
            with patch.object(wizard,'command',side_effect=RuntimeError('failed package install')):
                with self.assertRaises(RuntimeError):wizard.speech('cpu')
            self.assertEqual(setup.load_object(wizard.settings),settings)
            self.assertNotIn('speech_profile',wizard.progress)

    def test_speech_install_preserves_fields_and_points_to_isolated_model_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);wizard=setup.Setup(root,root/'data')
            settings={'ffmpeg_path':'working.exe','decklink_ffmpeg_path':'capture.exe','other':42}
            setup.save_object(wizard.settings,settings)
            wizard.python.parent.mkdir();wizard.python.touch()
            wizard.progress['python_runtime_sha256']=wizard.deps['python']['sha256']
            with patch.object(wizard,'command') as command:wizard.speech('cpu')
            installs=[c.args[0] for c in command.call_args_list if 'pip' in c.args[0]]
            self.assertEqual(len(installs),2)
            self.assertTrue(all('--no-cache-dir' in args for args in installs))
            saved=setup.load_object(wizard.settings)
            for name,value in settings.items():self.assertEqual(saved[name],value)
            self.assertEqual(saved['whisper_model_cache'],str(wizard.data/'models'))
            self.assertTrue(any('torch==2.7.1+cpu' in call.args[0] for call in command.call_args_list))
            self.assertTrue(any('download_root=' in ' '.join(map(str,call.args[0])) for call in command.call_args_list))
            self.assertEqual(wizard.progress['speech_profile'],'cpu')

    def test_corrupt_existing_settings_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'settings.json';path.write_text('broken')
            with self.assertRaises(ValueError):setup.load_object(path)
            self.assertEqual(path.read_text(),'broken')

class SetupHttpTests(unittest.TestCase):
    def setUp(self):
        from http.server import ThreadingHTTPServer
        import threading
        self.temp=tempfile.TemporaryDirectory()
        self.wizard=setup.Setup(Path(self.temp.name),Path(self.temp.name)/'data')
        self.server=ThreadingHTTPServer(('127.0.0.1',0),setup.handler(self.wizard,'test-token',0))
        self.port=self.server.server_port
        self.server.RequestHandlerClass=setup.handler(self.wizard,'test-token',self.port)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.temp.cleanup()
    def request(self,path,data,headers=None):
        import http.client
        c=http.client.HTTPConnection('127.0.0.1',self.port)
        c.request('POST',path,json.dumps(data),headers or {})
        r=c.getresponse();status=r.status;r.read();c.close();return status
    def test_external_or_unauthenticated_requests_cannot_install(self):
        with patch.object(self.wizard,'start') as start:
            self.assertEqual(self.request('/api/install',{'consent':True}),403)
            self.assertEqual(self.request('/api/install',{'consent':True},{'X-Setup-Token':'test-token','Origin':'https://example.com'}),403)
            start.assert_not_called()
    def test_consent_and_object_body_required_before_any_setup_task(self):
        with patch.object(self.wizard,'start') as start:
            headers={'X-Setup-Token':'test-token'}
            self.assertEqual(self.request('/api/install',{'consent':False},headers),400)
            self.assertEqual(self.request('/api/install',[],headers),400)
            start.assert_not_called()

class ExistingSdkTests(unittest.TestCase):
    def test_existing_root_include_header_and_zip_are_all_selectable(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);include=base/'already downloaded SDK/Win/include';include.mkdir(parents=True)
            (include/'DeckLinkAPIVersion.h').write_text('#define BLACKMAGIC_DECKLINK_API_VERSION 0x0c080000\n')
            (include/'DeckLinkAPI.idl').touch()
            wizard=setup.Setup(ROOT,base/'private')
            for path in (include.parent.parent,include,include/'DeckLinkAPIVersion.h'):
                wizard.select_sdk(str(path));self.assertEqual(Path(wizard.sdk),include.resolve())
            archive=base/'sdk.zip'
            with zipfile.ZipFile(archive,'w') as z:
                for file in include.iterdir():z.write(file,'SDK/Win/include/'+file.name)
            wizard.select_sdk(str(archive));self.assertTrue(Path(wizard.sdk).is_dir())
            self.assertIn('sdk-',wizard.sdk)
    def test_invalid_selection_keeps_previous_sdk(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);wizard=setup.Setup(ROOT,base/'private');wizard.sdk='previous valid SDK'
            bad=base/'newer';bad.mkdir();(bad/'DeckLinkAPIVersion.h').write_text('#define BLACKMAGIC_DECKLINK_API_VERSION 0x0e040000\n')
            (bad/'DeckLinkAPI.idl').touch()
            with self.assertRaises(ValueError):wizard.select_sdk(str(bad))
            self.assertEqual(wizard.sdk,'previous valid SDK')
