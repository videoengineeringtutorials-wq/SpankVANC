"""Build a portable x64 Windows trial with a verified CPython embed runtime."""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import struct
import tomllib
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parent.parent
APP_VERSION=tomllib.loads((ROOT/'pyproject.toml').read_text())['project']['version']
VERSION='3.14.10'
URL=f'https://www.python.org/ftp/python/{VERSION}/python-{VERSION}-embed-amd64.zip'
DIGEST='90905e64a840557d8c1bc4f5b74db3d7ee85e3ffb217611cac1c7813acea4159'
p=argparse.ArgumentParser();p.add_argument('--runtime',type=Path,default=ROOT/f'build/windows-downloads/python-{VERSION}-embed-amd64.zip')
p.add_argument('--output',type=Path,default=ROOT/f'releases/SpankVANC-{APP_VERSION}-Windows11-x64-App.zip')
p.add_argument('--verification',type=Path,help='Verification report for the bundled binary')
p.add_argument('--capture-ffmpeg',type=Path,help='Bundle a separately built extended Windows capture executable')
a=p.parse_args()
if a.capture_ffmpeg or a.verification:
    raise SystemExit("FFmpeg bundling is disabled: the pinned DeckLink capture build is nonfree and unredistributable. Build it locally and configure its path; see docs/REDISTRIBUTION.md.")
if not a.runtime.exists():
    a.runtime.parent.mkdir(parents=True,exist_ok=True)
    with urllib.request.urlopen(URL,timeout=60) as r:a.runtime.write_bytes(r.read())
raw=a.runtime.read_bytes()
if hashlib.sha256(raw).hexdigest()!=DIGEST:raise SystemExit('Python runtime hash does not match the official pinned release')
files={}
with zipfile.ZipFile(io.BytesIO(raw)) as archive:
    if archive.testzip():raise SystemExit('Python archive failed its integrity test')
    for name in archive.namelist():
        if name.endswith('/'):continue
        parts=Path(name).parts
        if name.startswith('/') or '..' in parts:raise SystemExit('Unsafe runtime archive member')
        files['python/'+name]=archive.read(name)
exe=files['python/python.exe'];pe=struct.unpack_from('<I',exe,0x3c)[0]
assert exe[:2]==b'MZ' and exe[pe:pe+4]==b'PE\x00\x00' and struct.unpack_from('<H',exe,pe+4)[0]==0x8664
files['python/python314._pth']=b'python314.zip\r\n.\r\n..\\app\r\n'
for path in sorted((ROOT/'spankvanc').rglob('*')):
    if path.is_file() and '__pycache__' not in path.parts and path.suffix!='.pyc':
        files['app/'+path.relative_to(ROOT).as_posix()]=path.read_bytes()
files['app/windows_launcher.py']=(ROOT/'windows/launcher.py').read_bytes()
for name in ('Start SpankVANC.cmd','Configure FFmpeg.cmd','Diagnostics.cmd','README.txt'):
    data=(ROOT/'windows'/name).read_bytes()
    if name.endswith('.cmd'):assert b'\r\n' in data and b'python.exe' in data
    files[name]=data
files['ffmpeg/README.txt']=(ROOT/'windows/ffmpeg-README.txt').read_bytes()
for path in sorted((ROOT/'docs').glob('*.md')):
    if path.name != 'WORKSTATION_HANDOFF.md':files['docs/'+path.name]=path.read_bytes()
files['CHANGELOG.md']=(ROOT/'CHANGELOG.md').read_bytes()
files['THIRD_PARTY_NOTICES.md']=(ROOT/'THIRD_PARTY_NOTICES.md').read_bytes()

files['LICENSE.txt']=(ROOT/'LICENSE').read_bytes()
manifest={'application':'SpankVANC','package':'Windows 11 x64 app only','app_version':APP_VERSION,
          'built_at':datetime.now(timezone.utc).isoformat(),'python':{'version':VERSION,'url':URL,'archive_sha256':DIGEST},
          'ffmpeg':'User-provided; not bundled','gpu_encoding':False,'windows_hardware_verified':False,
          'feature_limits':['FFmpeg and Desktop Video must be supplied separately',
                            'Extended caption monitoring and SCTE conversion require a local patched FFmpeg build',
                            'No SDI playout, Whisper or serial dispatch'],
          'files':{name:hashlib.sha256(data).hexdigest() for name,data in sorted(files.items())}}
files['PACKAGE.json']=(json.dumps(manifest,indent=2)+'\n').encode()
a.output.parent.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(a.output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
    for name,data in sorted(files.items()):archive.writestr('SpankVANC-Windows/'+name,data)
with zipfile.ZipFile(a.output) as archive:
    assert archive.testzip() is None
    assert len(archive.namelist())==len(files)
    assert not any('/runtime/' in name or '/.ssh/' in name for name in archive.namelist())
    for name,digest in manifest['files'].items():assert hashlib.sha256(archive.read('SpankVANC-Windows/'+name)).hexdigest()==digest
digest=hashlib.sha256(a.output.read_bytes()).hexdigest()
a.output.with_suffix('.zip.sha256').write_text(digest+'  '+a.output.name+'\n')
print(f'{a.output} ({a.output.stat().st_size:,} bytes)')
print('SHA256 '+digest)
print('Verified: pinned runtime hash, x64 PE header, ZIP integrity, launcher paths and every packaged file hash.')
