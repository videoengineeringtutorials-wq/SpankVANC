"""Isolated Windows engine exercise under local Wine; no network or DeckLink I/O."""
from pathlib import Path
import json
import os
import subprocess
import tempfile
import time
from spankvanc.manual_scte import append_cue, section, crc

ROOT=Path(__file__).resolve().parent.parent
BUILD=ROOT/'build/windows-cross'
env=dict(os.environ,WINEDEBUG='-all',WINEPREFIX=str(BUILD/'wine-prefix-cli'),WINEDLLPATH=str(BUILD/'wine/usr/lib/x86_64-linux-gnu/wine'))
launcher=[str(BUILD/'wine/usr/lib/wine/wine64'),str(BUILD/'ffmpeg-7.0.2/ffmpeg.exe')]
def win(path):return 'Z:'+str(path).replace('/','\\')
def sections(path,pid):
    found=[]
    data=path.read_bytes()
    for offset in range(0,len(data),188):
        p=data[offset:offset+188]
        assert len(p)==188 and p[0]==0x47
        if ((p[1]&31)<<8|p[2])!=pid or not p[1]&0x40:continue
        start=4+(p[4]+1 if p[3]&0x20 else 0)
        start+=1+p[start]
        size=3+((p[start+1]&15)<<8|p[start+2])
        found.append(p[start:start+size])
    return found
with tempfile.TemporaryDirectory() as folder:
    directory=Path(folder)
    journals=[directory/'first.bin',directory/'second.bin']
    for path in journals:path.touch()
    paths=[directory/'first.ts',directory/'clean.ts',directory/'second.ts']
    source=directory/'source.ts'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=160x90:rate=25','-t','4','-c:v','mpeg2video',str(source)],check=True)
    args=launcher+['-hide_banner','-nostdin','-y','-re','-i',win(source)]
    for i,path in enumerate(paths):
        args+=['-map','0:v','-t','4','-c:v','mpeg2video','-f','mpegts']
        if i!=1:args+=['-spankvanc_manual_scte',win(journals[0 if i==0 else 1])]
        args+=[win(path)]
    log=directory/'ffmpeg.log'
    with log.open('w') as stream:
        process=subprocess.Popen(args,env=env,stdout=subprocess.DEVNULL,stderr=stream)
        try:
            time.sleep(1)
            cues=[section(42,'start',30),section(42,'end')]
            append_cue(journals[0],cues[0]);time.sleep(.5);append_cue(journals[0],cues[1])
            assert process.wait(timeout=30)==0,log.read_text()
        finally:
            if process.poll() is None:process.kill();process.wait()
    actual=sections(paths[0],0x1ffe)
    assert actual==cues,[p.hex() for p in actual]
    assert all(crc(cue)==0 for cue in actual)
    assert not sections(paths[1],0x1ffe) and not sections(paths[2],0x1ffe)
    for index,path in enumerate(paths):
        pmts=sections(path,0x1000)
        assert pmts and all(crc(pmt)==0 for pmt in pmts)
        for pmt in pmts:
            assert (b'CUEI' in pmt)==(index!=1)
            assert (b'\x86\xff\xfe\xf0\x03\x8a\x01\x01' in pmt)==(index!=1)
        probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-show_streams','-of','json',str(path)]))
        assert probe['streams'][0]['nb_read_frames']=='100',probe
    print('PASS: live Start/End emitted once each with valid CRC/PMT; two other outputs have no cues; all three retain 100 video frames.')
