"""Resumable, per-user Windows setup wizard. Never ships a capture engine or SDK."""
from __future__ import annotations
import argparse
from collections import deque
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import urllib.request
import webbrowser
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
WEB = HERE / 'web' if (HERE / 'web').is_dir() else HERE / 'setup_web'
DEPENDENCIES = HERE / 'dependencies.json' if (HERE / 'dependencies.json').is_file() else HERE / 'setup_dependencies.json'
DISTRO = 'SpankVANC-Build'
DRIVER_URL = 'https://www.blackmagicdesign.com/support/family/capture-and-playback'
SDK_URL = 'https://www.blackmagicdesign.com/support/download/82671d9009c448d7b4ac61fdfacf3d6d/Windows'


def safe_extract(archive, destination):
    destination = Path(destination).resolve()
    with zipfile.ZipFile(archive) as source:
        for info in source.infolist():
            name = info.filename.replace('\\', '/')
            parts = PurePosixPath(name)
            if parts.is_absolute() or '..' in parts.parts or ':' in name or info.external_attr >> 16 & 0o170000 == 0o120000:
                raise ValueError('Archive contains an unsafe path.')
            target = (destination / name).resolve()
            if not target.is_relative_to(destination): raise ValueError('Archive path escapes its destination.')
        source.extractall(destination)


def load_object(path):
    if not path.exists(): return {}
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict): raise ValueError('Settings must contain a JSON object; existing file was not replaced.')
    return data


def save_object(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(data, indent=2)+'\n', encoding='utf-8')
    temporary.replace(path)


def capture_helper(root=ROOT):
    path = root / 'app/windows_build_capture.py'
    if not path.is_file(): path = root / 'windows/build_capture.py'
    spec = importlib.util.spec_from_file_location('spankvanc_setup_build', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


class Setup:
    def __init__(self, root=ROOT, data=None):
        self.root = Path(root)
        self.data = Path(data) if data else Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'SpankVANC-Setup'
        self.data.mkdir(parents=True, exist_ok=True)
        self.settings = self.root / 'settings.json'
        self.state_file = self.data / 'progress.json'
        self.progress = load_object(self.state_file)
        self.deps = load_object(DEPENDENCIES)
        self.lock = threading.RLock()
        self.logs = deque(maxlen=160)
        self.running = False
        self.step = 'Ready to set up this PC'
        self.error = ''
        self.ready = False
        self.reboot = False
        self.sdk = self.progress.get('sdk', '')
        self.python = self.data / 'speech-python/python.exe'
        self.distro_dir = self.data / 'linux-build'
        self.cache = self.data / 'downloads'
        self.log_path = self.data / 'setup.log'

    def log(self, text):
        # No route settings, stream keys or activation keys are read into setup logs.
        text = str(text).rstrip()
        with self.lock:
            self.logs.append(text)
            with self.log_path.open('a', encoding='utf-8') as stream: stream.write(text+'\n')

    def state(self):
        with self.lock:
            return dict(running=self.running, step=self.step, error=self.error, ready=self.ready,
                        reboot=self.reboot, sdk=bool(self.sdk), sdk_label=self.sdk or '',
                        logs=list(self.logs), log_path=str(self.log_path))

    def command(self, args, *, capture=False, input_text=None, timeout=None):
        env = dict(os.environ, PYTHONNOUSERSITE='1', PYTHONUTF8='1')
        env.pop('PYTHONPATH', None); env.pop('PYTHONHOME', None)
        for name in list(env):
            if name.startswith('PIP_'):env.pop(name)
        env['PIP_CONFIG_FILE']=os.devnull
        flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        if capture or input_text is not None:
            result = subprocess.run(list(map(str, args)), input=input_text, capture_output=True,
                text=True, errors='replace', env=env, creationflags=flags, timeout=timeout)
            if result.returncode: raise RuntimeError('A setup command failed: '+result.stderr[-1500:]+result.stdout[-1500:])
            return result.stdout.replace('\x00', '').strip()
        with subprocess.Popen(list(map(str,args)), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, errors='replace', env=env, creationflags=flags) as process:
            for line in process.stdout: self.log(line)
            if process.wait(): raise RuntimeError('This setup step failed. Review the log, then choose Retry setup.')

    def download(self, name):
        item = self.deps[name]
        self.cache.mkdir(exist_ok=True)
        path = self.cache / item['filename']
        def matches(p):
            if not p.is_file(): return False
            h = hashlib.sha256()
            with p.open('rb') as stream:
                for block in iter(lambda:stream.read(1024*1024), b''):h.update(block)
            return h.hexdigest() == item['sha256']
        if not matches(path):
            partial = path.with_suffix(path.suffix+'.part')
            self.log('Downloading '+item['filename']+' from its official source…')
            with urllib.request.urlopen(item['url'],timeout=60) as response, partial.open('wb') as output:
                shutil.copyfileobj(response,output)
            if not matches(partial): raise ValueError('Download checksum did not match. Nothing was installed; retry or obtain an updated installer.')
            partial.replace(path)
        return path

    def remember(self, **fields):
        self.progress.update(fields); save_object(self.state_file, self.progress)

    def select_sdk(self, value):
        path=Path(str(value).strip().strip('"')).expanduser()
        if not path.exists():raise ValueError('That SDK path was not found. Choose its folder or ZIP again.')
        if path.suffix.lower()=='.zip' and path.is_file():
            identity=hashlib.sha256(path.read_bytes()).hexdigest()[:16]
            destination=self.data/('sdk-'+identity);destination.mkdir(exist_ok=True)
            safe_extract(path,destination);path=destination
        elif path.is_file():path=path.parent
        candidates=[path,path/'Win/include',path/'include']
        if not any((p/'DeckLinkAPIVersion.h').is_file() for p in candidates):
            if path==Path(path.anchor):raise ValueError('Select the SDK folder, not an entire drive.')
            for current,dirs,files in os.walk(path):
                relative=Path(current).relative_to(path)
                if len(relative.parts)>=4:dirs[:]=[]
                if 'DeckLinkAPIVersion.h' in files and Path(current).parent.name.lower()=='win':candidates.append(Path(current))
        sdk_checker=self.root/'build-support/tools/bootstrap_windows_capture.py'
        if not sdk_checker.exists():sdk_checker=self.root/'tools/bootstrap_windows_capture.py'
        spec=importlib.util.spec_from_file_location('spankvanc_setup_sdk',sdk_checker)
        checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)
        valid=[]
        for candidate in candidates:
            if (candidate/'DeckLinkAPIVersion.h').is_file():
                try:checker.sdk_version(candidate)
                except ValueError:continue
                if candidate.resolve() not in valid:valid.append(candidate.resolve())
        if len(valid)!=1:raise ValueError('Choose the DeckLink SDK 12.8 folder (or its Win/include folder). Newer SDKs are not supported by this build.')
        self.sdk=str(valid[0]);self.remember(sdk=self.sdk)
        self.log('Existing DeckLink SDK 12.8 selected. No new download is needed.')

    def pick_sdk(self, folder=False):
        if os.name!='nt':raise ValueError('The SDK picker runs on Windows.')
        script="""[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
Add-Type -AssemblyName System.Windows.Forms
"""
        if folder:
            script+="""$d=New-Object System.Windows.Forms.FolderBrowserDialog
$d.Description='Choose your existing DeckLink SDK 12.8 folder or Win include folder'
$d.ShowNewFolderButton=$false
if($d.ShowDialog() -eq 'OK'){[Console]::Write($d.SelectedPath)}"""
        else:
            script+="""$d=New-Object System.Windows.Forms.OpenFileDialog
$d.Title='Choose your downloaded DeckLink SDK 12.8 ZIP'
$d.Filter='DeckLink SDK ZIP|*.zip'
if($d.ShowDialog() -eq 'OK'){[Console]::Write($d.FileName)}"""
        self.step='Choose an SDK folder in the Windows dialog' if folder else 'Choose an SDK ZIP in the Windows dialog'
        chosen=self.command(['powershell.exe','-NoProfile','-STA','-Command',script],capture=True)
        if chosen:self.select_sdk(chosen)
        self.step='Ready to set up this PC'

    def ensure_wsl(self):
        helper = capture_helper(self.root); wsl = helper.wsl_executable()
        try:names=self.command([wsl,'--list','--quiet'],capture=True,timeout=30)
        except (OSError,RuntimeError,subprocess.TimeoutExpired):names=''
        if DISTRO in names.splitlines() and not self.progress.get('owns_distro'):
            raise ValueError('A Linux environment already uses the setup name. Contact support; it was not modified.')
        try:
            self.command([wsl,'-d',DISTRO,'-u','root','--exec','true'],capture=True,timeout=30)
            return True
        except (OSError, RuntimeError, subprocess.TimeoutExpired): pass
        # WSL 1 avoids requiring firmware virtualization. Enable its Windows
        # feature under a separate UAC prompt; the wizard itself stays per-user.
        query = "(Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux).State.ToString()"
        import base64
        action = "$ErrorActionPreference='Stop';$s="+query+r";if($s -ne 'Enabled'){Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux -All -NoRestart | Out-Null;exit 3010}; & $env:WINDIR\System32\wsl.exe --version *> $null;if($LASTEXITCODE -ne 0){ & $env:WINDIR\System32\wsl.exe --install --no-distribution --enable-wsl1 --web-download;if($LASTEXITCODE -ne 0){exit $LASTEXITCODE}};exit 0"
        encoded = base64.b64encode(action.encode('utf-16le')).decode()
        outer = "$p=Start-Process powershell.exe -Verb RunAs -Wait -PassThru -ArgumentList '-NoProfile -EncodedCommand "+encoded+"';[Console]::Write($p.ExitCode)"
        code = self.command(['powershell.exe','-NoProfile','-Command',outer],capture=True,timeout=180)
        if code.strip() == '3010':
            self.reboot = True
            self.log('Windows needs a restart. Save your work, restart, and open Finish SpankVANC Setup from the desktop.')
            return False
        if code.strip() != '0': raise ValueError('Windows build support was not enabled. Approve its administrator prompt, then retry.')
        self.log('Preparing a separate Linux build environment. Existing distributions are left alone.')
        image = self.download('ubuntu')
        self.distro_dir.mkdir(exist_ok=True)
        # Never replace/unregister an existing distro or change the default distro.
        wsl=capture_helper(self.root).wsl_executable()
        self.remember(owns_distro=True)
        self.command([wsl,'--import',DISTRO,str(self.distro_dir),str(image),'--version','1'])
        return True

    def runtime(self, force=False):
        self.step='Checking the Microsoft C++ runtime'
        # Preserve an existing runtime instead of upgrading a working broadcast PC.
        if not force and (Path(os.environ.get('WINDIR',r'C:\Windows'))/'System32/msvcp140.dll').is_file():return True
        binary=self.download('vcredist')
        self.log('Microsoft runtime setup will open. Review its license and complete installation, then return here.')
        result=subprocess.run([str(binary),'/install','/norestart'])
        if result.returncode==3010:
            self.reboot=True;self.log('Restart Windows, then reopen Finish SpankVANC Setup.');return False
        if result.returncode not in (0,1638):raise ValueError('The Microsoft C++ runtime was not installed. Complete its installer and retry.')
        return True

    def speech(self, device):
        self.step = 'Installing speech recognition'
        if not self.python.is_file() or self.progress.get('python_runtime_sha256')!=self.deps['python']['sha256']:
            archive = self.download('python')
            destination = self.python.parent
            destination.mkdir(exist_ok=True)
            safe_extract(archive,destination)
            self.command([self.python,'-I','-c','import sys,pip; print(sys.version)'])
            self.remember(python_runtime_sha256=self.deps['python']['sha256'])
        index = self.deps['cpu_index'] if device == 'cpu' else self.deps['cuda_index']
        if self.progress.get('speech_profile')!=device:
            self.command([self.python,'-I','-m','pip','install','--disable-pip-version-check',
                'torch=='+self.deps['torch']+('+cpu' if device=='cpu' else '+cu118'),'--index-url',index])
            self.command([self.python,'-I','-m','pip','install','--disable-pip-version-check',
                'openai-whisper=='+self.deps['whisper'],'--index-url','https://pypi.org/simple'])
        probe=[self.python,'-I','-c','import whisper,numpy,torch; print("Speech packages loaded; CUDA:",torch.cuda.is_available())']
        try:self.command(probe)
        except RuntimeError as exc:
            if os.name!='nt' or not any(word in str(exc).lower() for word in ('dll','c10','winerror 126')):raise
            if not self.runtime(force=True):raise ValueError('Restart Windows, then resume setup.') from exc
            self.command(probe)
        if device=='cuda':
            try:self.command([self.python,'-I','-c','import torch; assert torch.cuda.is_available(), "CUDA unavailable"'])
            except RuntimeError as exc:raise ValueError('This CUDA profile did not find a compatible GPU/driver. Choose CPU and retry.') from exc
        self.step = 'Downloading the speech model'
        # Whisper verifies the model against its upstream SHA-256 URL digest.
        self.command([self.python,'-I','-c',"import whisper; whisper.load_model("+repr(self.deps['model'])+",device='cpu',download_root="+repr(str(self.data/'models'))+"); print('Speech model ready')"])
        self.remember(speech_profile=device)
        # Save only after installation and model loading succeed. Retain all
        # existing routes, engines and other settings.
        settings = load_object(self.settings)
        settings['whisper_python_path'] = str(self.python)
        settings['whisper_model_cache'] = str(self.data/'models')
        save_object(self.settings,settings)

    def build(self):
        self.step = 'Building your media engine (this can take an hour or more)'
        helper = capture_helper(self.root); wsl = helper.wsl_executable()
        helper_path = self.root/'build-support/tools/bootstrap_windows_capture.py'
        if not helper_path.exists(): helper_path = self.root/'tools/bootstrap_windows_capture.py'
        build = '/root/.cache/spankvanc/windows-sdk12.8-ffmpeg7.0.2'
        # The minimal Ubuntu image starts as root and has no Python initially.
        self.command([wsl,'-d',DISTRO,'-u','root','--exec','sh','-c',
            'apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y python3 ca-certificates'])
        def linux(path):return helper.wsl_path(str(Path(path).resolve()),DISTRO)
        self.command([wsl,'-d',DISTRO,'-u','root','--exec','env','DEBIAN_FRONTEND=noninteractive','python3',linux(helper_path),
            '--sdk-include',linux(self.sdk),'--build-dir',build,'--install-deps'])
        import datetime
        output=self.root/'capture-ffmpeg-local';output.mkdir(exist_ok=True)
        binary=output/('ffmpeg-setup-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.exe')
        self.command([wsl,'-d',DISTRO,'-u','root','--exec','cp',build+'/capture/bin/ffmpeg.exe',linux(binary)])
        helper.verify_capture(binary)
        helper.save_capture_path(self.root,binary)

    def verify(self):
        settings=load_object(self.settings)
        binary=Path(settings.get('decklink_ffmpeg_path','missing'))
        if not binary.is_file(): raise ValueError('The local media engine has not been built yet.')
        capture_helper(self.root).verify_capture(binary)
        self.command([settings['whisper_python_path'],'-I','-c','import whisper,numpy,torch; print("Speech recognition ready")'])
        self.ready=True; self.step='Setup complete'
        self.log('Your app is ready. Open SpankVANC, enter a license key, then make a short test recording.')

    def run(self, device):
        if os.name != 'nt': raise ValueError('This setup wizard installs on Windows 11 x64.')
        if sys.getwindowsversion().build<22000:raise ValueError('This guided setup requires Windows 11. Your PC was not changed.')
        if device not in ('cpu','cuda'): raise ValueError('Choose CPU or the tested CUDA 11.8 profile.')
        if not self.sdk: raise ValueError('First select your SDK 12.8 download using Choose SDK.')
        if not (Path(self.sdk)/'DeckLinkAPIVersion.h').is_file():
            raise ValueError('The selected SDK is no longer available. Choose its ZIP again before continuing.')
        self.reboot=False;self.ready=False
        self.step='Checking this PC'
        # Do not reconfigure engines or dependencies underneath an active app.
        with socket.socket() as sock:
            if sock.connect_ex(('127.0.0.1',8877))==0: raise ValueError('Close SpankVANC before running setup. Keep any active broadcast in mind before closing it.')
        if shutil.disk_usage(self.data).free < 12*1024**3: raise ValueError('Setup needs at least 12 GB of free space for downloads, build tools and speech recognition.')
        self.step='Preparing Windows build support'
        if not self.ensure_wsl(): return
        if not self.runtime(): return
        self.speech(device)
        existing=load_object(self.settings).get('decklink_ffmpeg_path')
        valid=False
        if existing and Path(existing).is_file():
            try:capture_helper(self.root).verify_capture(Path(existing));valid=True
            except (OSError,ValueError):pass
        if not valid:self.build()
        self.verify()

    def start(self, task):
        with self.lock:
            if self.running: raise ValueError('A setup step is already running.')
            self.running=True;self.error=''
        def work():
            try: task()
            except Exception as exc:
                self.error=str(exc);self.log('Setup stopped: '+str(exc))
            finally:
                with self.lock:self.running=False
        threading.Thread(target=work,daemon=True).start()


def handler(setup,token,port):
    class Handler(BaseHTTPRequestHandler):
        def reply(self, data, status=200, mime='application/json'):
            raw=json.dumps(data).encode() if mime=='application/json' else data
            self.send_response(status);self.send_header('Content-Type',mime)
            self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers();self.wfile.write(raw)
        def host_ok(self):return self.headers.get('Host') in (f'127.0.0.1:{port}',f'localhost:{port}')
        def do_GET(self):
            if not self.host_ok():return self.reply({'error':'Invalid host'},403)
            if self.path=='/api/state':
                if not secrets.compare_digest(self.headers.get('X-Setup-Token',''),token):return self.reply({'error':'Invalid setup token'},403)
                return self.reply(setup.state())
            files={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript'),'/style.css':('style.css','text/css')}
            if self.path not in files:return self.reply({'error':'Not found'},404)
            name,mime=files[self.path];data=(WEB/name).read_bytes().replace(b'__SETUP_TOKEN__',token.encode())
            return self.reply(data,mime=mime)
        def do_POST(self):
            if not self.host_ok() or not secrets.compare_digest(self.headers.get('X-Setup-Token',''),token):return self.reply({'error':'Invalid setup token'},403)
            if self.headers.get('Origin') not in (None,f'http://127.0.0.1:{port}',f'http://localhost:{port}'):return self.reply({'error':'Invalid origin'},403)
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=4096:raise ValueError('Invalid request size')
                data=json.loads(self.rfile.read(length))
                if not isinstance(data,dict):raise ValueError('Setup request must contain an object.')
                if self.path=='/api/pick-sdk':setup.start(setup.pick_sdk)
                elif self.path=='/api/pick-sdk-folder':setup.start(lambda:setup.pick_sdk(folder=True))
                elif self.path=='/api/select-sdk':
                    value=data.get('path')
                    if not isinstance(value,str) or not value.strip():raise ValueError('Enter the existing SDK folder path.')
                    setup.start(lambda:setup.select_sdk(value))
                elif self.path=='/api/install':
                    if data.get('consent') is not True:raise ValueError('Review the setup actions and select the consent box first.')
                    device=data.get('device','cpu');setup.start(lambda:setup.run(device))
                elif self.path in ('/api/driver','/api/sdk'):
                    webbrowser.open(DRIVER_URL if self.path.endswith('driver') else SDK_URL)
                elif self.path=='/api/launch':
                    if setup.running or not setup.ready:raise ValueError('Finish setup before opening the app.')
                    subprocess.Popen([str(setup.root/'python/python.exe'),str(setup.root/'app/windows_launcher.py')],cwd=setup.root)
                    threading.Thread(target=self.server.shutdown,daemon=True).start()
                elif self.path=='/api/close':
                    if setup.running:raise ValueError('Wait for the running setup step before closing.')
                    threading.Thread(target=self.server.shutdown,daemon=True).start()
                else:return self.reply({'error':'Not found'},404)
                self.reply(setup.state())
            except (OSError,ValueError,KeyError,TypeError) as exc:self.reply({'error':str(exc)},400)
        def log_message(self,*args):pass
    return Handler


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--no-browser',action='store_true');args=p.parse_args()
    setup=Setup()
    handle=None
    kernel=None
    if os.name=='nt':
        import ctypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p]
        kernel.CreateMutexW.restype=ctypes.c_void_p
        kernel.CloseHandle.argtypes=[ctypes.c_void_p]
        identity=hashlib.sha256(str(setup.data).encode()).hexdigest()[:16]
        handle=kernel.CreateMutexW(None,False,'Local\\SpankVANCSetup-'+identity)
        if not handle:raise OSError('Could not acquire the setup lock.')
        if ctypes.get_last_error()==183:
            session=load_object(setup.data/'session.json')
            port=session.get('port')
            if not args.no_browser and type(port)==int and 1<=port<=65535:webbrowser.open('http://127.0.0.1:'+str(port))
            kernel.CloseHandle(handle)
            return
    server=ThreadingHTTPServer(('127.0.0.1',0),handler(setup,'',0))
    server.RequestHandlerClass=handler(setup,secrets.token_urlsafe(32),server.server_port)
    save_object(setup.data/'session.json',{'port':server.server_port,'pid':os.getpid(),'root':str(setup.root.resolve())})
    if not args.no_browser:webbrowser.open('http://127.0.0.1:'+str(server.server_port))
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:
        server.server_close()
        if handle:kernel.CloseHandle(handle)


if __name__=='__main__':
    try:main()
    except Exception as exc:
        if os.name=='nt':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None,'Setup could not start: '+str(exc),'SpankVANC setup',16)
        else:raise
