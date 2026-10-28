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


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--probe',action='store_true')
    p.add_argument('--model',default='small.en');p.add_argument('--language',default='en')
    p.add_argument('--device',choices=('auto','cpu','cuda'),default='auto')
    p.add_argument('--journal');p.add_argument('--ready')
    args=p.parse_args()
    import numpy as np
    import torch
    import whisper
    if args.probe:
        print(json.dumps({'available':True,'cuda':torch.cuda.is_available(),'models':whisper.available_models()}));return
    device=('cuda' if torch.cuda.is_available() else 'cpu') if args.device=='auto' else args.device
    if device=='cuda' and not torch.cuda.is_available():raise RuntimeError('CUDA was requested but is unavailable')
    if args.model not in whisper.available_models():raise RuntimeError('Model is not supported by this Whisper installation')
    torch.set_num_threads(min(8,os.cpu_count() or 1))
    model=whisper.load_model(args.model,device=device)
    print('Whisper ready: '+args.model+' / '+device,flush=True)
    # Parent waits for this marker before it opens capture hardware.
    with open(args.ready,'w',encoding='utf-8') as f:f.write(device)
    chunks=queue.Queue(maxsize=3)
    overflow=threading.Event()
    def read():
        try:
            while True:
                buf=bytearray()
                while len(buf)<16000*4*3:
                    part=sys.stdin.buffer.read(16000*4*3-len(buf))
                    if not part:break
                    buf.extend(part)
                if not buf:break
                if len(buf)%4:raise RuntimeError('Truncated float audio')
                try:chunks.put_nowait(bytes(buf))
                except queue.Full:overflow.set()
                if len(buf)<16000*4*3:break
        finally:
            chunks.put(None)
    threading.Thread(target=read,daemon=True).start()
    initialized=False;last_text=time.monotonic();cleared=False
    virtual_end=time.monotonic()
    with open(args.journal,'ab',buffering=0) as journal:
        while True:
            buf=chunks.get()
            if buf is None:break
            if overflow.is_set():
                print('Whisper cannot keep up: dropped audio chunks; choose a smaller model or CUDA',flush=True)
                overflow.clear()
            audio=np.frombuffer(buf,dtype='<f4').copy()
            if np.sqrt(np.mean(audio*audio))<0.002:
                text=''
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
                    print('Whisper CC1: '+text,flush=True)
            elif initialized and not cleared and now-last_text>8:
                journal.write(bytes((odd(0x14),odd(0x2c)))*2);cleared=True
            if journal.tell()>64*1024*1024:raise RuntimeError('Caption journal reached route limit; restart route')


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('Whisper error: '+str(exc),file=sys.stderr,flush=True);sys.exit(1)
