"""Portable Windows launcher. Uses a caller-provided FFmpeg; installs no drivers."""
from __future__ import annotations
import argparse
import copy
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser

ROOT=Path(__file__).resolve().parent.parent
SETTINGS=ROOT/'settings.json'


def read_settings(path=SETTINGS):
    if not path.exists():return {}
    data=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data,dict):raise ValueError('settings.json must contain an object')
    return data


def find_ffmpeg(settings,root=ROOT):
    candidates=[os.environ.get('SPANKVANC_FFMPEG'),settings.get('ffmpeg_path'),
                str(root/'ffmpeg/ffmpeg.exe'),shutil.which('ffmpeg')]
    return next((str(Path(os.path.expandvars(p)).expanduser().resolve()) for p in candidates
                 if isinstance(p,str) and p and Path(os.path.expandvars(p)).expanduser().is_file()),None)


def configure(settings,root=ROOT):
    print('Enter the full path to your EXISTING DeckLink-enabled ffmpeg.exe.')
    print('You may drag ffmpeg.exe from Explorer into this window, then press Enter.')
    value=input('FFmpeg path: ').strip().strip('"')
    binary=Path(os.path.expandvars(value)).expanduser()
    if not binary.is_file():raise ValueError('That file was not found. Run Configure FFmpeg.cmd to try again.')
    p=subprocess.run([str(binary),'-hide_banner','-version'],capture_output=True,text=True,errors='replace',timeout=20)
    if p.returncode:raise ValueError('FFmpeg could not run. Keep its required DLL files alongside it.')
    settings=dict(settings,ffmpeg_path=str(binary.resolve()))
    (root/'settings.json').write_text(json.dumps(settings,indent=2)+'\n',encoding='utf-8')
    print('Saved FFmpeg location locally. No system settings were changed.')
    return settings


def prepare_environment(binary,settings,root=ROOT):
    os.environ['SPANKVANC_FFMPEG']=binary
    if settings.get('whisper_python_path'):
        os.environ['SPANKVANC_WHISPER_PYTHON']=settings['whisper_python_path']
    # Override separately only when the user supplied a custom capture binary.
    bundled=root/'capture-ffmpeg/ffmpeg.exe'
    capture=settings.get('decklink_ffmpeg_path') or os.environ.get('SPANKVANC_DECKLINK_FFMPEG')
    os.environ['SPANKVANC_DECKLINK_FFMPEG']=capture or (str(bundled.resolve()) if bundled.is_file() else binary)


def diagnostics(root=ROOT):
    from spankvanc.engine import doctor,scrub,executable
    folder=root/'diagnostics';folder.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now().strftime('%Y%m%d-%H%M%S')
    report={'python':sys.version,'platform':sys.platform,'capabilities':doctor()}
    path=folder/f'diagnostics-{stamp}.json'
    path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    logs=[]
    for label,args in [('Version',['-version']),('Build',['-buildconf']),
                       ('Devices',['-devices']),('DeckLink options',['-h','demuxer=decklink']),
                       ('DeckLink inputs',['-f','decklink','-list_devices','1','-i','dummy'])]:
        try:
            p=subprocess.run([executable(True),'-hide_banner','-nostdin',*args],capture_output=True,
                             text=True,errors='replace',timeout=20)
            logs.append(label+'\n'+scrub(p.stdout+p.stderr))
        except (OSError,subprocess.TimeoutExpired) as exc:logs.append(label+'\n'+str(exc))
    path.with_suffix('.txt').write_text('\n\n'.join(logs),encoding='utf-8')
    print('Diagnostics saved:',path)
    print('The report excludes route settings and destination credentials.')
    print('Detected inputs:',', '.join(d['name'] for d in report['capabilities']['decklink_devices']) or 'none')
    print('Live source monitor:',report['capabilities']['source_monitor'])
    print('SCTE-104 conversion:',report['capabilities']['scte_runtime'])
    return path


def first_route(state_dir,root=ROOT):
    from spankvanc.engine import DEFAULT
    path=state_dir/'route.json'
    if path.exists():return
    captures=state_dir/'captures';captures.mkdir(parents=True,exist_ok=True)
    cfg=copy.deepcopy(DEFAULT)
    cfg['name']='Windows DeckLink Duo trial'
    cfg['outputs'][0].update(kind='file',address=str((captures/f'capture-{datetime.now():%Y%m%d-%H%M%S}.ts').resolve()),scte='strip')
    # Device and mode intentionally remain a user choice; Duo is not Duo 2.
    path.write_text(json.dumps(cfg,indent=2)+'\n',encoding='utf-8')


def open_when_ready(port):
    url=f'http://127.0.0.1:{port}'
    end=time.monotonic()+60
    while time.monotonic()<end:
        try:
            with urllib.request.urlopen(url,timeout=1) as response:
                if b'SpankVANC' in response.read(8192):
                    webbrowser.open(url);return
        except OSError:pass
        time.sleep(.5)


def main(argv=None):
    parser=argparse.ArgumentParser(description='SpankVANC Windows portable trial')
    parser.add_argument('--configure',action='store_true')
    parser.add_argument('--diagnostics',action='store_true')
    parser.add_argument('--no-browser',action='store_true')
    parser.add_argument('--port',type=int,default=8877)
    args=parser.parse_args(argv)
    if not 1<=args.port<=65535:parser.error('Port must be 1–65535')
    try:
        os.chdir(ROOT)
        settings=read_settings()
        if args.configure:
            configure(settings);return 0
        binary=find_ffmpeg(settings)
        if not binary:
            settings=configure(settings);binary=find_ffmpeg(settings)
        if not binary:raise ValueError('FFmpeg was not found.')
        prepare_environment(binary,settings)
        if args.diagnostics:
            diagnostics();return 0
        state=ROOT/'runtime';state.mkdir(parents=True,exist_ok=True)
        first_route(state)
        # Do not open a second capture/control instance on the same port.
        with socket.socket() as sock:
            if sock.connect_ex(('127.0.0.1',args.port))==0:
                raise ValueError(f'Port {args.port} is already in use. Close the other SpankVANC window or use --port 8878.')
        print('SpankVANC Windows trial — CPU encoding (no NVENC).',flush=True)
        print('FFmpeg:',binary,flush=True)
        print('SDI capture FFmpeg:',os.environ['SPANKVANC_DECKLINK_FFMPEG'],flush=True)
        print('Choose the exact DeckLink Duo input and advertised source mode.',flush=True)
        print('Keep this window open; press Ctrl+C here to stop the app.',flush=True)
        print('The capabilities panel detects live caption telemetry and SCTE conversion in the capture build.',flush=True)
        if not args.no_browser:threading.Thread(target=open_when_ready,args=(args.port,),daemon=True).start()
        from spankvanc.server import serve
        serve(args.port,state)
        return 0
    except (ValueError,OSError,subprocess.SubprocessError) as exc:
        print('SpankVANC:',exc,file=sys.stderr)
        print('Use Configure FFmpeg.cmd or Diagnostics.cmd for troubleshooting.',file=sys.stderr)
        return 1


if __name__=='__main__':raise SystemExit(main())
