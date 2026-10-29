"""Repair identity, backup preservation and setup lifecycle guards."""
import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('maintenance',ROOT/'windows/maintenance.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class RepairTests(unittest.TestCase):
 def test_recognized_app_can_be_repaired_and_user_files_are_preserved(self):
  with tempfile.TemporaryDirectory() as folder:
   base=Path(folder);root=base/'app';root.mkdir();data=base/'private'
   (root/'PACKAGE.json').write_text(json.dumps({'application':'SpankVANC'}))
   (root/'app.py').write_text('old code');(root/'settings.json').write_text('{"other":42}')
   (root/'runtime').mkdir();(root/'runtime/route.json').write_text('saved route')
   incoming=base/'incoming.json';incoming.write_text(json.dumps({'application':'SpankVANC','app_version':'0.11.1','files':{'app.py':'unused'}}))
   with patch.object(m,'stop_idle_setup') as stop:backup=m.prepare_install(root,incoming,data)
   stop.assert_called_once();self.assertEqual((backup/'app.py').read_text(),'old code')
   self.assertEqual((root/'settings.json').read_text(),'{"other":42}')
   self.assertEqual((root/'runtime/route.json').read_text(),'saved route')
   self.assertTrue((root/m.MARKER).exists())
 def test_uninstall_leftover_marker_allows_reinstall(self):
  with tempfile.TemporaryDirectory() as folder:
   base=Path(folder);root=base/'app';root.mkdir()
   (root/m.MARKER).write_text(json.dumps({'application':'SpankVANC'}))
   (root/'settings.json').write_text('private settings')
   incoming=base/'incoming.json';incoming.write_text(json.dumps({'application':'SpankVANC','files':{}}))
   with patch.object(m,'stop_idle_setup'):m.prepare_install(root,incoming,base/'private')
   self.assertEqual((root/'settings.json').read_text(),'private settings')
 def test_unrelated_folder_is_rejected_without_changes(self):
  with tempfile.TemporaryDirectory() as folder:
   base=Path(folder);root=base/'unrelated';root.mkdir();(root/'keep.txt').write_text('keep')
   incoming=base/'incoming.json';incoming.write_text(json.dumps({'application':'SpankVANC','files':{}}))
   with self.assertRaisesRegex(ValueError,'unrelated'):m.prepare_install(root,incoming,base/'private')
   self.assertEqual((root/'keep.txt').read_text(),'keep');self.assertFalse((root/m.MARKER).exists())
 def test_running_app_is_never_stopped(self):
  with patch.object(m,'processes',return_value=[{'pid':1,'kind':'app','children':0}]) as processes:
   with self.assertRaisesRegex(ValueError,'Close SpankVANC'):m.stop_idle_setup(Path('/app'),Path('/data'))
   self.assertEqual(processes.call_count,1)
