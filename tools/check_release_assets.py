"""Reject nonfree engines, SDK inputs and workstation state in public ZIP assets."""
import hashlib,json
from pathlib import Path
import sys,zipfile

def check(path):
 with zipfile.ZipFile(path) as archive:
  assert archive.testzip() is None,'Corrupt ZIP'
  names=archive.namelist();app=any(n.endswith('/PACKAGE.json') for n in names)
  for name in names:
   parts=Path(name).parts;lower=name.lower()
   assert not name.startswith('/') and '..' not in parts,'Unsafe archive path'
   assert not any(p.lower() in ('runtime','diagnostics','.git','.ssh','capture-ffmpeg','capture-ffmpeg-local','decklinksdk','sdk') for p in parts),'Forbidden state or dependency directory: '+name
   assert Path(name).name not in ('settings.json','route.json','WORKSTATION_HANDOFF.md','.env','id_rsa','id_ed25519'),'Workstation state: '+name
   assert not Path(name).name.startswith('DeckLinkAPI'),'SDK file: '+name
   suffix=Path(name).suffix.lower()
   if suffix in ('.exe','.dll','.pyd'):
    assert app and len(parts)>2 and parts[1]=='python','Media/dependency binary: '+name
   assert suffix not in ('.a','.o','.so','.ts','.flv','.ndjson','.pem','.key','.pfx'), 'Build/capture artifact: '+name
  if app:
   prefix='SpankVANC-Windows/'
   manifest=json.loads(archive.read(prefix+'PACKAGE.json'))
   assert manifest['ffmpeg']=='User-provided; not bundled'
   assert prefix+'python/LICENSE.txt' in names
   if tuple(map(int,manifest['app_version'].split('.'))) >= (0,6,1):
    for required in ('Build Extended Capture.cmd','Setup Guide.url','app/windows_build_capture.py','build-support/tools/bootstrap_windows_capture.py','build-support/tools/build_windows_capture.sh','build-support/tools/patch_ffmpeg_decklink.py','build-support/tools/patch_ffmpeg_monitor_scte.py','build-support/native/scte104.hpp','build-support/windows/mingw-toolchain.cmake','docs/WINDOWS_BEGINNER.md'):
     assert prefix+required in names,'Missing setup/build support: '+required
   for name,digest in manifest['files'].items():
    assert hashlib.sha256(archive.read(prefix+name)).hexdigest()==digest,'Manifest mismatch: '+name
  else:
   assert 'SpankVANC/LICENSE' in names and 'SpankVANC/docs/REDISTRIBUTION.md' in names
 print(str(path)+': public asset checks passed')

if __name__=='__main__':
 if len(sys.argv)<2:raise SystemExit('Usage: check_release_assets.py public-source.zip public-app.zip')
 for name in sys.argv[1:]:check(Path(name))
