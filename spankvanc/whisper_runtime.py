"""Lifecycle and dependency detection for the isolated Whisper worker."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

WORKER=Path(__file__).with_name('whisper_worker.py')


def python_path():return os.environ.get('SPANKVANC_WHISPER_PYTHON',sys.executable)


def probe():
    try:
        r=subprocess.run([python_path(),str(WORKER),'--probe'],capture_output=True,text=True,timeout=45)
        if r.returncode:return {'available':False,'error':'Whisper worker dependencies unavailable in configured Python'}
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (OSError,ValueError,subprocess.TimeoutExpired):
        return {'available':False,'error':'Could not probe configured Whisper Python'}


def prepare(state_dir,cfg,log,group_options):
    folder=Path(state_dir)/'whisper';folder.mkdir(parents=True,exist_ok=True,mode=0o700)
    journal=folder/'cc1.pairs';ready=folder/'ready'
    journal.write_bytes(b'');ready.unlink(missing_ok=True)
    w=cfg['whisper']
    process=subprocess.Popen([python_path(),'-u',str(WORKER),'--journal',str(journal.resolve()),
        '--ready',str(ready.resolve()),'--model',w['model'],'--language',w['language'],'--device',w['device']],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
        env=dict(os.environ,PYTHONIOENCODING="utf-8"),**group_options)
    import threading
    def read():
        for line in process.stdout:log(line.decode('utf-8',errors='replace').rstrip())
    threading.Thread(target=read,daemon=True).start()
    end=time.monotonic()+180
    while not ready.exists():
        if process.poll() is not None:raise RuntimeError('Whisper model failed to load; see engine log')
        if time.monotonic()>end:
            process.kill();process.wait();raise RuntimeError('Whisper model loading timed out')
        time.sleep(.1)
    return process,journal
