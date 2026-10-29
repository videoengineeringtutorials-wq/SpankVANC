"""Windows-only isolated install/uninstall/reinstall regression; starts no media."""

import os,json,subprocess,time,hashlib
from pathlib import Path
import sys
base=Path(sys.argv[2]).resolve();base.mkdir(parents=True,exist_ok=True)
root=base/'repair-0111'
profile=base/'repair-profile-0111';profile.mkdir(exist_ok=True)
env=dict(os.environ,LOCALAPPDATA=str(profile))
exe=Path(sys.argv[1]).resolve()
def install():
 r=subprocess.run([str(exe),'/S','/NOINTEGRATION','/D='+str(root)],env=env,timeout=120)
 assert r.returncode==0,('install',r.returncode)
 manifest=json.loads((root/'PACKAGE.json').read_text())
 for name,h in manifest['files'].items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==h,name
install()
(root/'settings.json').write_text('{"test_preserved":true}')
(root/'runtime').mkdir(exist_ok=True);(root/'runtime/local-engine.txt').write_text('preserve')
child=subprocess.Popen([str(root/'python/pythonw.exe'),str(root/'setup/setup.py'),'--no-browser'],env=env)
try:
 session=profile/'SpankVANC-Setup/session.json'
 for _ in range(100):
  if session.exists():break
  assert child.poll() is None,'wizard exited'
  time.sleep(.1)
 assert session.exists(),'no session'
 original_session=session.read_bytes()
 second=subprocess.run([str(root/'python/pythonw.exe'),str(root/'setup/setup.py'),'--no-browser'],env=env,timeout=15)
 assert second.returncode==0,'Second launch failed'
 assert session.read_bytes()==original_session,'Second launch replaced live session'
 assert child.poll() is None,'Original wizard stopped'
 r=subprocess.run([str(root/'Uninstall.exe'),'/S','_?='+str(root)],env=env,timeout=120)
 assert r.returncode==0,('uninstall',r.returncode)
 assert child.wait(timeout=15)==0
 assert not (root/'PACKAGE.json').exists(),'uninstall failed'
 assert json.loads((root/'settings.json').read_text())['test_preserved']
 assert (root/'runtime/local-engine.txt').read_text()=='preserve'
 install()
 assert json.loads((root/'settings.json').read_text())['test_preserved']
 assert (root/'runtime/local-engine.txt').read_text()=='preserve'
 install()
 assert json.loads((root/'settings.json').read_text())['test_preserved']
 print('Native install, idle-wizard uninstall, same-folder reinstall, repair, settings and engine preservation: PASS',flush=True)
finally:
 if child.poll() is None:child.terminate();child.wait(timeout=10)
