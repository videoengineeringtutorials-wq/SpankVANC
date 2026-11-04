"""Bounded asynchronous translation preview with optional route-scoped CC2 sinks."""
from collections import deque
import json
import os
from pathlib import Path
import queue
import subprocess
import threading

from .process_utils import hidden_process_options


class TranslationPreview:
    def __init__(self, state_dir):
        root = Path(state_dir).resolve().parent
        self.home = Path(os.environ.get('SPANKVANC_TRANSLATION_HOME', str(root / 'translation')))
        self.pending = queue.Queue(maxsize=8)
        self.lock = threading.Lock()
        self.rows = deque(maxlen=40)
        self.status = 'Not installed'
        self.dropped = 0
        self.process = None
        self.ready = threading.Event()
        self.thread = None

    def python_path(self):
        managed=self.home/'python/python.exe'
        return managed if managed.is_file() else self.home / 'venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')

    def available(self):
        python = self.python_path()
        return python.is_file() and (self.home / 'model' / 'ct2' / 'model.bin').is_file()

    def ensure_ready(self, timeout=30):
        with self.lock:
            self._start()
        if not self.ready.wait(timeout):
            raise ValueError('Translation model did not become ready; see Dashboard status')

    def _start(self):
        if self.thread is None:
            self.ready.clear()
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()

    def submit(self, text, sink=None):
        if not isinstance(text, str) or not text.strip() or len(text) > 2000:
            raise ValueError('Enter 1–2000 characters of English text')
        if not (self.home / 'model' / 'ct2' / 'model.bin').is_file():
            raise ValueError('OPUS-MT preview model is not installed')
        with self.lock:
            self._start()
            try:
                self.pending.put_nowait((text.strip(), sink))
            except queue.Full:
                self.dropped += 1
                raise ValueError('Translation preview is busy; phrase skipped')
        return self.state()

    def state(self):
        with self.lock:
            return {'status': self.status, 'rows': list(self.rows), 'pending': self.pending.qsize(), 'dropped': self.dropped}

    def _run(self):
        process = None
        try:
            with self.lock:
                self.status = 'Loading OPUS-MT · CPU INT8'
            python = self.python_path()
            process = subprocess.Popen([str(python), '-u', str(Path(__file__).with_name('translation_worker.py')), str(self.home / 'model')],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, encoding='utf-8', **hidden_process_options())
            self.process = process
            if not json.loads(process.stdout.readline()).get('ready'):
                raise ValueError('Model failed to load')
            with self.lock:
                self.status = 'Ready · OPUS-MT English → Spanish · CPU INT8'
                self.ready.set()
            while True:
                text, sink = self.pending.get()
                process.stdin.write(json.dumps({'english': text})+'\n')
                process.stdin.flush()
                result = json.loads(process.stdout.readline())
                if sink is not None and 'spanish' in result:
                    result['cc2_queued'] = bool(sink(result['spanish']))
                with self.lock:
                    if 'error' in result:
                        self.status = result['error']
                    else:
                        self.rows.append(result)
                        self.status = 'Ready · OPUS-MT English → Spanish · CPU INT8'
        except (OSError, ValueError) as exc:
            with self.lock:
                self.status = 'Translation unavailable: '+str(exc)
                while not self.pending.empty():
                    self.pending.get_nowait()
                self.ready.clear()
                self.thread = None
        finally:
            if process and process.poll() is None:
                process.terminate()
