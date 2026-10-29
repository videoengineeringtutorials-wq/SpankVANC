"""Installer repair/uninstall preflight. Preserve user data and close idle setup."""
import argparse
import base64
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import urllib.request

MARKER='.spankvanc-install.json'


def powershell(script, data):
    payload=base64.b64encode(script.encode('utf-16le')).decode()
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',payload],
        input=json.dumps(data),text=True,capture_output=True,encoding='utf-8',errors='replace',
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),timeout=30)
    if result.returncode:raise ValueError('Could not check running setup processes. Close setup and retry.')
    return json.loads(result.stdout or '[]')


def processes(root, stop=None):
    if os.name!='nt':return []
    script=r"""$ErrorActionPreference='Stop';[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
$d=[Console]::In.ReadToEnd()|ConvertFrom-Json;$root=$d.root.TrimEnd('\')+'\';$all=@(Get-CimInstance Win32_Process);$found=@()
foreach($p in $all){
 $inside=$p.ExecutablePath -and $p.ExecutablePath.StartsWith($root,[StringComparison]::OrdinalIgnoreCase)
 $wizard=$p.CommandLine -and $p.CommandLine.IndexOf($root+'setup\setup.py',[StringComparison]::OrdinalIgnoreCase) -ge 0
 if(($inside -and $p.Name -match '^(pythonw?|ffmpeg.*)\.exe$') -or $wizard){
  $kind=if($wizard){'setup'}else{'app'};$children=@($all|Where-Object {$_.ParentProcessId -eq $p.ProcessId}).Count
  if($d.stop -and $p.ProcessId -eq $d.stop){if($kind -ne 'setup' -or $children -ne 0){throw 'Setup is not idle'};Stop-Process -Id $p.ProcessId}
  $found+=@{pid=$p.ProcessId;kind=$kind;children=$children}
 }
}
ConvertTo-Json -InputObject $found -Compress
"""
    return powershell(script,dict(root=str(root),stop=stop))


def stop_idle_setup(root, data):
    current=processes(root)
    if any(p['kind']!='setup' for p in current):raise ValueError('Close SpankVANC before repairing or uninstalling. No running app was stopped.')
    if not current:return
    session_path=data/'session.json'
    try:
        session=json.loads(session_path.read_text(encoding='utf-8'))
        if session.get('root') and Path(session['root']).resolve()!=root:raise ValueError('Another setup window owns this session.')
        port=session['port']
        if type(port)!=int or not 1<=port<=65535:raise ValueError('Invalid session')
        base='http://127.0.0.1:'+str(port)
        with urllib.request.urlopen(base+'/',timeout=3) as r:html=r.read().decode('utf-8')
        token=re.search(r'name="setup-token" content="([^"]+)"',html)[1]
        headers={'X-Setup-Token':token,'Content-Type':'application/json'}
        with urllib.request.urlopen(urllib.request.Request(base+'/api/state',headers=headers),timeout=3) as r:state=json.load(r)
    except (OSError,ValueError,KeyError,TypeError):
        # 0.11.0 could delete setup files while leaving pythonw alive. Only
        # recover that demonstrably uninstalled, childless wizard automatically.
        if (root/'setup/setup.py').exists() or (root/'PACKAGE.json').exists() or any(p['children'] for p in current):
            raise ValueError('Close the existing Finish Setup window and retry. If a folder dialog is open, cancel it first.')
        for p in current:processes(root,stop=p['pid'])
    else:
        if state.get('running'):raise ValueError('Setup is busy. Finish its current step or cancel the SDK dialog, then retry uninstall/repair.')
        with urllib.request.urlopen(urllib.request.Request(base+'/api/close',data=b'{}',headers=headers),timeout=5) as r:r.read()
    for _ in range(40):
        if not processes(root):return
        time.sleep(.2)
    raise ValueError('Setup has not closed yet. Wait a moment, then retry; no app files were changed.')


def read_identity(root):
    for name in (MARKER,'PACKAGE.json'):
        try:
            data=json.loads((root/name).read_text(encoding='utf-8'))
            if data.get('application')=='SpankVANC':return True
        except (OSError,ValueError,AttributeError):pass
    return False


def prepare_install(root, incoming, data):
    root=Path(root).resolve();data=Path(data)
    package=json.loads(Path(incoming).read_text(encoding='utf-8'))
    if package.get('application')!='SpankVANC' or not isinstance(package.get('files'),dict):raise ValueError('Installer payload identity is invalid.')
    names=list(package['files'])+['PACKAGE.json','settings.json']
    for name in names:
        if not (root/name).resolve().is_relative_to(root):raise ValueError('Unsafe installer file path.')
    nonempty=root.exists() and any(root.iterdir())
    if nonempty and not read_identity(root):
        # Recognize only the default 0.11.0 leftover Python files, and only if
        # their bytes match the audited runtime. Arbitrary folders stay protected.
        base=Path(os.environ.get('LOCALAPPDATA',Path.home()))/'Programs/SpankVANC'
        legacy=root.parent==base.resolve() and root.name=='0.11.0'
        for file in root.rglob('*'):
            if file.is_dir():continue
            name=file.relative_to(root).as_posix()
            expected=package['files'].get(name)
            if not name.startswith('python/') or not expected or hashlib.sha256(file.read_bytes()).hexdigest()!=expected:legacy=False;break
        if not legacy:raise ValueError('This folder contains unrelated files. Choose a new folder; nothing was replaced.')
    stop_idle_setup(root,data)
    backup=None
    if nonempty:
        backup=data/'repair-backups'/('install-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
        for name in names:
            source=root/name
            if source.is_file():
                target=backup/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
        if backup and backup.exists():(backup/'repair-info.json').write_text(json.dumps({'root':str(root),'version':package.get('app_version')},indent=2))
    root.mkdir(parents=True,exist_ok=True)
    (root/MARKER).write_text(json.dumps({'application':'SpankVANC','schema':1,'version':package.get('app_version')},indent=2))
    return backup


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('install','uninstall'));p.add_argument('root',type=Path);p.add_argument('manifest',nargs='?',type=Path);a=p.parse_args()
    data=Path(os.environ.get('LOCALAPPDATA',Path.home()))/'SpankVANC-Setup'
    try:
        if a.action=='install':prepare_install(a.root,a.manifest,data)
        else:stop_idle_setup(a.root.resolve(),data)
    except Exception as exc:print(str(exc));return 2
    print('Preflight passed. User settings and local engines are preserved.');return 0

if __name__=='__main__':raise SystemExit(main())
