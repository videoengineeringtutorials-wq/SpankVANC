"""Isolated local Whisper worker; stdin is routed mono 16 kHz float PCM.

This file also runs by absolute path under a separate Python installation.
It imports no SpankVANC package and never imports or executes legacy scripts.
"""
import argparse
import json
import os
import queue
import sys
import threading
import time
import unicodedata
from collections import deque
import re


def odd(value):
    return value | (0x80 if value.bit_count() % 2 == 0 else 0)


def wrap_words(text, width=32):
    """Keep ordinary words intact; split only a single word wider than a row."""
    lines=[];line=""
    for word in text.split():
        if len(word)>width:
            if line:lines.append(line);line=""
            while len(word)>width:
                lines.append(word[:width]);word=word[width:]
        if line and len(line)+1+len(word)>width:
            lines.append(line);line=""
        line=(line+" "+word) if line else word
    if line:lines.append(line)
    return lines


def encode_text(text, initialize=False):
    # Basic 608 has replacements at these ASCII positions. Transliterate and
    # substitute rather than emit bytes which display as different characters.
    text=unicodedata.normalize('NFKD',text.translate(str.maketrans({'’':"'",'‘':"'",'“':'"','”':'"','—':'-','–':'-','…':'...'})))
    text=''.join(c for c in text if not unicodedata.combining(c))
    text=' '.join(''.join(c if 32<=ord(c)<127 and c not in '*\\^_`{|}~' else '?' for c in text).split())
    if not text:return b''
    pairs=[]
    def control(a,b):pairs.extend(((a,b),(a,b)))
    if initialize:
        control(0x14,0x2c) # erase displayed memory
    for line in wrap_words(text):
        # Refresh mode, channel and row for late-joining/reacquiring receivers.
        # RU2 does not erase an existing two-row roll-up window.
        control(0x14,0x25) # two-row roll-up CC1
        control(0x14,0x2d) # roll up and start next row
        control(0x14,0x70) # row 15, explicit indent zero
        control(0x14,0x24) # delete residual text from the destination row
        data=line.encode('ascii')
        if len(data)%2:data+=b'\x00' # null second byte, not a visible pad
        pairs.extend(zip(data[::2],data[1::2]))
    return bytes(odd(v) for pair in pairs for v in pair)


def normalize_word(word):
    return re.sub(r"[^\w]+", "", word.lower(), flags=re.UNICODE)


def merge_new_words(previous, current, max_overlap=30):
    """Fallback text overlap matching for segments without usable word timestamps."""
    a, b = previous.split(), current.split()
    na, nb = [normalize_word(w) for w in a], [normalize_word(w) for w in b]
    for count in range(min(max_overlap, len(a), len(b)), 0, -1):
        if na[-count:] == nb[:count] and all(na[-count:]):
            return ' '.join(b[count:])
    return current


class WordCommitter:
    """Commit stable words once across overlapping recognition windows."""
    def __init__(self):
        self.until = 0.0
        self.recent = deque(maxlen=80)
        self.tail = ''

    def commit(self, segments, start, safe_end):
        words = []
        for seg in segments:
            if seg.no_speech_prob > 0.75:
                continue
            if seg.words is None:
                raw = seg.text.strip()
                words.extend(merge_new_words(self.tail, raw).split())
                self.tail = raw
                continue
            for w in seg.words:
                end = start + w.end
                if not self.until + 0.03 < end <= safe_end:
                    continue
                word = w.word.strip()
                token = normalize_word(word)
                duplicate = token and any(t == token and abs(end - e) <= 0.85 for t, e in self.recent)
                if word and not duplicate:
                    words.append(word)
                    if token:
                        self.recent.append((token, end))
                self.until = max(self.until, end)
        return ' '.join(words)


def en530_frames(text):
    text = text.translate(str.maketrans({'’':"'",'‘':"'",'“':'"','”':'"','—':'-','–':'-','…':'...'}))
    text = ''.join(c if 32 <= ord(c) < 127 else '?' for c in text)
    return [b'\x01 ' + line.encode('ascii') + b'\r' for line in wrap_words(text)]


class EN530Sender:
    """Bounded, asynchronous serial output; failures stop the route visibly."""
    def __init__(self, port):
        import serial
        self.serial = serial.Serial(port, baudrate=1200, bytesize=serial.SEVENBITS,
            parity=serial.PARITY_ODD, stopbits=serial.STOPBITS_ONE, timeout=1, write_timeout=2)
        self.queue = queue.Queue(maxsize=8)
        self.error = None
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        try:
            while True:
                text = self.queue.get()
                if text is None:
                    break
                for frame in en530_frames(text):
                    if self.serial.write(frame) != len(frame):
                        raise OSError('Incomplete EN530 serial write')
                    if self.serial.readline().strip() == b'E1':
                        self.serial.write(b'\x012\r')
                        self.serial.readline()
        except Exception as exc:
            self.error = exc
        finally:
            self.serial.close()

    def submit(self, text):
        if self.error:
            raise RuntimeError('EN530 serial output failed: ' + str(self.error))
        try:
            self.queue.put_nowait(text)
        except queue.Full:
            raise RuntimeError('EN530 serial output cannot keep up')

    def close(self):
        if self.error:
            raise RuntimeError('EN530 serial output failed: ' + str(self.error))
        self.queue.put(None, timeout=2)
        self.thread.join(timeout=30)
        if self.thread.is_alive() or self.error:
            raise RuntimeError('EN530 serial output failed to drain')


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--probe',action='store_true')
    p.add_argument('--backend',choices=('openai','faster'),default='openai')
    p.add_argument('--compute-type',default='auto')
    p.add_argument('--serial-port',default='')
    p.add_argument('--model',default='small.en');p.add_argument('--language',default='en')
    p.add_argument('--device',choices=('auto','cpu','cuda'),default='auto')
    p.add_argument('--journal');p.add_argument('--ready')
    args=p.parse_args()
    import numpy as np
    if args.backend == 'faster':
        import ctranslate2
        from faster_whisper import WhisperModel
        from faster_whisper.utils import available_models
        cuda = ctranslate2.get_cuda_device_count() > 0
        models = available_models()
    else:
        import torch
        import whisper
        cuda = torch.cuda.is_available()
        models = whisper.available_models()
    if args.probe:
        print(json.dumps({'available':True,'cuda':cuda,'models':models}));return
    device = ('cuda' if cuda else 'cpu') if args.device == 'auto' else args.device
    if device == 'cuda' and not cuda:
        raise RuntimeError('CUDA was requested but is unavailable')
    if args.model not in models:
        raise RuntimeError('Model is not supported by this Whisper installation')
    if args.backend == 'faster':
        model = WhisperModel(args.model, device=device, compute_type=args.compute_type,
            download_root=os.environ.get('SPANKVANC_WHISPER_MODEL_CACHE'))
    else:
        torch.set_num_threads(min(8,os.cpu_count() or 1))
        model = whisper.load_model(args.model,device=device,download_root=os.environ.get('SPANKVANC_WHISPER_MODEL_CACHE'))
    sender = EN530Sender(args.serial_port) if args.serial_port else None
    print('Whisper ready: '+args.model+' / '+device,flush=True)
    # Parent waits for this marker before it opens capture hardware.
    with open(args.ready,'w',encoding='utf-8') as f:f.write(device)
    block_samples = 16000 * (2 if args.backend == 'faster' else 3)
    chunks=queue.Queue(maxsize=3)
    overflow=threading.Event()
    def read():
        samples = 0
        try:
            while True:
                buf=bytearray()
                while len(buf)<block_samples*4:
                    part=sys.stdin.buffer.read(block_samples*4-len(buf))
                    if not part:break
                    buf.extend(part)
                if not buf:break
                if len(buf)%4:raise RuntimeError('Truncated float audio')
                samples += len(buf)//4
                try:chunks.put_nowait((bytes(buf), samples))
                except queue.Full:overflow.set()
                if len(buf)<block_samples*4:break
        finally:
            chunks.put(None)
    threading.Thread(target=read,daemon=True).start()
    initialized=False;last_text=time.monotonic();cleared=False
    virtual_end=time.monotonic()
    committer = WordCommitter()
    context = np.empty(0, dtype=np.float32)
    previous_total = 0
    with open(args.journal,'ab',buffering=0) as journal:
        while True:
            buf=chunks.get()
            if buf is None:break
            if overflow.is_set():
                print('Whisper cannot keep up: dropped audio chunks; choose a smaller model or CUDA',flush=True)
                overflow.clear()
            buf, total = buf
            audio=np.frombuffer(buf,dtype='<f4').copy()
            if args.backend == 'faster':
                if total - previous_total != len(audio):
                    context = np.empty(0, dtype=np.float32)
                previous_total = total
                context = np.concatenate((context, audio))[-64000:]
                audio = context
            if sender and sender.error:
                raise RuntimeError('EN530 serial output failed: ' + str(sender.error))
            if np.sqrt(np.mean(audio*audio))<0.002:
                text=''
            elif args.backend == 'faster':
                segments, _ = model.transcribe(audio, language=args.language, task='transcribe',
                    beam_size=3, temperature=0, condition_on_previous_text=False,
                    word_timestamps=True, vad_filter=False, no_speech_threshold=0.6)
                text = committer.commit(list(segments), (total-len(audio))/16000, total/16000-0.35)
            else:
                result=model.transcribe(audio,language=args.language,task='transcribe',fp16=device=='cuda',
                    condition_on_previous_text=False,temperature=0,verbose=None,
                    no_speech_threshold=0.6,compression_ratio_threshold=2.0)
                text=' '.join(s['text'].strip() for s in result.get('segments',[])
                    if s.get('no_speech_prob',0)<0.6 and s.get('avg_logprob',0)>-1.0)
            now=time.monotonic()
            if text:
                if virtual_end>now+8:
                    print('Whisper caption backlog: dropped transcript to keep captions live',flush=True);continue
                payload=encode_text(text,not initialized)
                if payload:
                    journal.write(payload);initialized=True;cleared=False;last_text=now
                    virtual_end=max(virtual_end,now)+len(payload)/2/(30000/1001)
                    if sender:sender.submit(text)
                    print('Whisper CC1: '+text,flush=True)
            elif initialized and not cleared and now-last_text>8:
                journal.write(bytes((odd(0x14),odd(0x2c)))*2);cleared=True
                print('Whisper clear',flush=True)
            if journal.tell()>64*1024*1024:raise RuntimeError('Caption journal reached route limit; restart route')

    if sender:sender.close()


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('Whisper error: '+str(exc),file=sys.stderr,flush=True);sys.exit(1)
