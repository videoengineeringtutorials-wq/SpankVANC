"""Local build helper: reject unsupported SDKs, verify sources and preserve settings."""
import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest import mock
ROOT=Path(__file__).resolve().parent.parent

def module(name,path):
 spec=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
bootstrap=module('bootstrap_test','tools/bootstrap_windows_capture.py')
windows=module('windows_build_test','windows/build_capture.py')

class LocalBuildTests(unittest.TestCase):
 def test_sdk_version_rejected_before_install_or_build(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);(root/'DeckLinkAPIVersion.h').write_text('#define BLACKMAGIC_DECKLINK_API_VERSION 0x0e020000\n');(root/'DeckLinkAPI.idl').touch()
   with mock.patch.object(bootstrap.subprocess,'run') as run:
    with self.assertRaisesRegex(ValueError,'requires SDK 12.8'):bootstrap.main(['--sdk-include',str(root),'--build-dir',str(root/'build'),'--install-deps'])
    run.assert_not_called();self.assertFalse((root/'build').exists())
   (root/'DeckLinkAPIVersion.h').write_text('#define BLACKMAGIC_DECKLINK_API_VERSION 0x0c080000\n')
   self.assertEqual(bootstrap.sdk_version(root),0x0c080000)

 def test_cached_source_hash_mismatch_is_not_extracted(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);(root/'ffmpeg-7.0.2.tar.xz').write_bytes(b'bad download')
   run=mock.Mock()
   with self.assertRaisesRegex(ValueError,'SHA-256 mismatch'):bootstrap.fetch('ffmpeg-7.0.2.tar.xz',root,run)
   run.assert_not_called();self.assertFalse((root/'ffmpeg-7.0.2').exists())

 def test_capture_settings_preserve_general_engine_and_other_fields(self):
  with tempfile.TemporaryDirectory(prefix='build helper ') as folder:
   root=Path(folder);path=root/'settings.json';path.write_text(json.dumps({'ffmpeg_path':'C:\\old\\ffmpeg.exe','other':42}))
   binary=root/'new capture/ffmpeg.exe';windows.save_capture_path(root,binary)
   saved=json.loads(path.read_text());self.assertEqual(saved['ffmpeg_path'],'C:\\old\\ffmpeg.exe');self.assertEqual(saved['other'],42)
   self.assertEqual(saved['decklink_ffmpeg_path'],str(binary.resolve()))
   path.write_text('bad json')
   with self.assertRaises(ValueError):windows.save_capture_path(root,binary)
   self.assertEqual(path.read_text(),'bad json')

 def test_wsl_path_passes_spaces_as_one_argument_without_shell(self):
  with mock.patch.object(windows.subprocess,'check_output',return_value='/mnt/c/SDK files/Win/include\n') as query:
   self.assertEqual(windows.wsl_path('C:\\SDK files\\Win\\include'),'/mnt/c/SDK files/Win/include')
   self.assertEqual(query.call_args.args[0][-1],'C:/SDK files/Win/include')
   self.assertNotIn('shell',query.call_args.kwargs)

 def test_unpatched_executable_does_not_pass_extended_verification(self):
  result=mock.Mock(returncode=0,stdout='stock FFmpeg',stderr='')
  with mock.patch.object(windows.subprocess,'run',return_value=result):
   with self.assertRaisesRegex(ValueError,'Extended DeckLink options'):windows.verify_capture(Path('ffmpeg.exe'))

class WindowsEngineDiscoveryTests(unittest.TestCase):
 def test_prefer_installed_wsl_when_system_launcher_is_broken(self):
  with mock.patch.object(windows.Path,'is_file',return_value=True):
   self.assertEqual(Path(windows.wsl_executable()).parts[-2:],('WSL','wsl.exe'))
  with mock.patch.object(windows.Path,'is_file',return_value=False):
   self.assertEqual(windows.wsl_executable(),'wsl.exe')

 def test_capture_only_engine_is_rejected_before_saving(self):
  def query(args,**kwargs):
   text = ('spankvanc_anc spankvanc_scte35 spankvanc_scte_strict' if 'demuxer=decklink' in args
           else 'old output build' if 'muxer=decklink' in args else 'version')
   return mock.Mock(returncode=0,stdout=text,stderr='')
  with mock.patch.object(windows.subprocess,'run',side_effect=query):
   with self.assertRaisesRegex(ValueError,'VANC caption playout is missing'):
    windows.verify_capture(Path('ffmpeg.exe'))
