"""Independent 608 CC1/CC2 and native 708 decoding of actual Windows outputs."""
from pathlib import Path
import json
import os
import subprocess
from spankvanc.whisper_worker import encode_text, odd
from spankvanc.bilingual import encode_spanish

ROOT=Path(__file__).resolve().parent.parent
BUILD=ROOT/'build/windows-cross'
OUT=ROOT/'build/verification-bilingual';OUT.mkdir(exist_ok=True)
env=dict(os.environ,WINEDEBUG='-all',WINEPREFIX=str(BUILD/'wine-prefix-cli'),WINEDLLPATH=str(BUILD/'wine/usr/lib/x86_64-linux-gnu/wine'))
launcher=[str(BUILD/'wine/usr/lib/wine/wine64'),str(BUILD/'ffmpeg-7.0.2/ffmpeg.exe')]
def win(path):return 'Z:'+str(path.resolve()).replace('/','\\')
def run(args,**kw):
    p=subprocess.run(args,capture_output=True,text=True,timeout=90,**kw)
    if p.returncode:raise AssertionError(p.stderr[-4000:]+p.stdout[-1000:])
    return p.stdout
source=OUT/'source.ts'
run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=size=320x180:rate=30000/1001','-t','10','-c:v','mpeg2video',str(source)])
clear=lambda channel:bytes(odd(v) for _ in range(2) for v in (0x14 if channel==1 else 0x1c,0x2c))
english=encode_text('ENGLISH ONLY',True)
spanish=encode_spanish('¡Sí! El niño está aquí. ÁÉÍÓÚÜ ¿Qué?')
silence=bytes((0x80,0x80))*120
journal=OUT/'bilingual.pairs';journal.write_bytes(english+spanish+silence+clear(1)+clear(2))
mono=OUT/'english.pairs';mono.write_bytes(english+silence+clear(1))
args=launcher+['-v','warning','-y','-i',win(source)]
paths={}
for codec in ('h264','mpeg2video'):
    for mode in ('608','both','english','strip'):
        path=OUT/f'{codec}-{mode}.ts';paths[codec,mode]=path
        vf='sidedata=mode=delete:type=A53_CC' if mode=='strip' else 'spankvanc_cc=journal='+win(mono if mode=='english' else journal).encode().hex()+('' if mode=='english' else ':cc2=1')+(':format=both' if mode=='both' else '')
        args+=['-map','0:v:0','-c:v','libx264' if codec=='h264' else codec,'-threads:v','2','-a53cc','1','-vf',vf,'-f','mpegts',win(path)]
run(args,env=env)
report={}
for (codec,mode),path in paths.items():
    texts={}
    for channel,options in [('cc1',['-1']),('cc2',['-1','-cc2']),('service1',['-svc','1'])]:
        prefix=OUT/f'{codec}-{mode}-{channel}'
        for old in OUT.glob(prefix.name+'*.srt'):old.unlink()
        extraction=subprocess.run(['ccextractor',str(path),*options,'-out=srt','-o',str(prefix)+'.srt'],capture_output=True,text=True,timeout=30)
        if extraction.returncode and not (mode=='strip' and 'No captions were found' in extraction.stdout+extraction.stderr):
            raise AssertionError(extraction.stdout+extraction.stderr)
        text=' '.join(' '.join(p.read_text(encoding='utf-8-sig') for p in OUT.glob(prefix.name+'*.srt')).split())
        texts[channel]=text
    frames=json.loads(run(['ffprobe','-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=nb_read_frames','-of','json',str(path)]))['streams'][0]['nb_read_frames']
    assert int(frames)==300,(codec,mode,frames)
    if mode=='strip':assert not any(texts.values()),texts
    else:
        assert 'ENGLISH ONLY' in texts['cc1'],texts
        assert 'niño' not in texts['cc1'],texts
        if mode=='english':assert not texts['cc2'] and not texts['service1'],texts
        else:
            assert 'ENGLISH' not in texts['cc2'],texts
            for expected in ('¡Sí!','niño','está aquí.','ÁÉÍÓÚÜ','¿Qué?'):assert expected in texts['cc2'],(expected,texts)
            if mode=='both':
                assert 'ENGLISH ONLY' in texts['service1'] and 'niño' not in texts['service1'],texts
            else:assert not texts['service1'],texts
    report[f'{codec}-{mode}']={'frames':int(frames),'decoded':texts}
(OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print('PASS: H.264/MPEG-2 CC1 English, CC2 Spanish glyphs, English Service1 isolation, English-only/strip, 300 frames each')
