"""Actual Windows engine encoding and independent native-708 decode, no SDI I/O."""
from pathlib import Path
import json
import os
import re
import subprocess
from spankvanc.whisper_worker import encode_text
ROOT=Path(__file__).resolve().parent.parent
BUILD=ROOT/'build/windows-cross'
OUT=ROOT/'build/verification-708-0.13.0';OUT.mkdir(exist_ok=True)
env=dict(os.environ,WINEDEBUG='-all',WINEPREFIX=str(BUILD/'wine-prefix-cli'),WINEDLLPATH=str(BUILD/'wine/usr/lib/x86_64-linux-gnu/wine'))
launcher=[str(BUILD/'wine/usr/lib/wine/wine64'),str(BUILD/'ffmpeg-7.0.2/ffmpeg.exe')]
def win(path):return 'Z:'+str(path.resolve()).replace('/','\\')
def run(args,**kw):
    p=subprocess.run(args,capture_output=True,text=True,timeout=60,**kw)
    if p.returncode:raise AssertionError(p.stderr[-4000:]+p.stdout[-2000:])
    return p.stdout
source=OUT/'source.ts'
run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=size=320x180:rate=30000/1001','-t','8','-c:v','mpeg2video',str(source)])
# Continuous journal as in production: every row re-establishes receiver state.
text='NATIVE SERVICE ONE CAPTION TEST. '+'A'*32+' Short next row. '+ 'Words keep their boundaries.'
journal=OUT/'captions.pairs'
journal.write_bytes(encode_text(text,True)+bytes([0x80,0x80])*30+encode_text('LAST ROW',False)+bytes([0x80,0x80])*40+bytes([0x94,0x2c])*2)
inspect=OUT/'inspect-a53'
flags=run(['pkg-config','--cflags','--libs','libavformat','libavcodec','libavutil']).split()
run(['gcc',str(ROOT/'tests/inspect_a53.c'),*flags,'-o',str(inspect)])
args=launcher+['-v','warning','-y','-i',win(source)]
paths={}
for codec in ('h264','mpeg2video'):
    for mode in ('608','708','both'):
        path=OUT/f'{codec}-{mode}.ts';paths[codec,mode]=path
        args+=['-map','0:v:0','-c:v','libx264' if codec=='h264' else codec,'-threads:v','2','-a53cc','1',
               '-vf','spankvanc_cc=journal='+win(journal).encode().hex()+':format='+{'608':'cea608','708':'cea708','both':'both'}[mode],'-f','mpegts',win(path)]
run(args,env=env)
report={}
for (codec,mode),path in paths.items():
    frames=run([str(inspect),str(path)]).splitlines()
    assert len(frames)==240,(codec,mode,len(frames))
    valid608=valid708=0;seq=None;packets=0
    for line in frames:
        data=bytes.fromhex(line.split(' ',1)[1]);assert len(data)==60
        triplets=[data[i:i+3] for i in range(0,len(data),3)]
        digital=[]
        for triplet in triplets:
            kind=triplet[0]&3
            if not triplet[0]&4:continue
            if kind<2:
                valid608+=1
                assert all(v.bit_count()%2==1 for v in triplet[1:])
            else:
                valid708+=1;digital.append(triplet)
        if digital:
            assert digital[0][0]&3==3
            raw=b''.join(t[1:] for t in digital)
            assert len(raw)==(raw[0]&63)*2
            current=raw[0]>>6
            if seq is not None:assert current==(seq+1)%4
            seq=current;packets+=1
            length=raw[1]&31;assert raw[1]>>5==1 and length>0
            assert len(raw) in (length+2,length+3)
            if len(raw)==length+3:assert raw[-1]==0
    assert bool(valid608)==(mode!='708') and bool(valid708)==(mode!='608'),(mode,valid608,valid708)
    prefix=OUT/f'decoded-{codec}-{mode}'
    for old in OUT.glob(prefix.name+'*.srt'):old.unlink()
    decode=subprocess.run(['ccextractor',str(path),'-svc','1','-out=srt','-o',str(prefix)+'.srt'],capture_output=True,text=True,timeout=30)
    assert decode.returncode==0,decode.stderr
    subtitles='\n'.join(p.read_text(errors='replace') for p in OUT.glob(prefix.name+'*.srt'))
    if mode!='608':
        for expected in ('NATIVE SERVICE ONE CAPTION TEST.','A'*32,'Short next row.','Words keep their boundaries.','LAST ROW'):
            assert expected in " ".join(subtitles.split()),(codec,mode,expected,subtitles,decode.stderr)
    else:assert not subtitles.strip(),subtitles
    if mode!='708':
        decoded=run(['ffmpeg','-v','error','-f','lavfi','-i',f'movie={path}[out0+subcc]','-map','0:s:0','-f','srt','-'])
        assert 'NATIVE SERVICE ONE CAPTION TEST.' in decoded
    report[f'{codec}-{mode}']=dict(frames=len(frames),valid_608=valid608,valid_708=valid708,dtvcc_packets=packets,native_708_text_verified=mode!='608')
(OUT/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
