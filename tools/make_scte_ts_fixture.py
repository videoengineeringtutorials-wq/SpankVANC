"""Build a small TS with a real SCTE-35 section for mux regression tests.

Uses an independent PMT/section packet builder, not the modified FFmpeg muxer.
"""
from pathlib import Path
import struct
import subprocess
import sys
from verify_scte_ts import crc,packet,sections

root=Path(__file__).resolve().parent.parent
out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
seed=out/'seed.ts'
subprocess.run(['ffmpeg','-v','error','-n','-f','lavfi','-i','testsrc2=size=320x180:rate=25','-f','lavfi','-i','sine=sample_rate=48000','-t','4','-c:v','libx264','-threads:v','2','-preset','ultrafast','-c:a','aac','-f','mpegts',str(seed)],check=True)
compiler=out/'check-scte'
subprocess.run(['g++','-std=c++17',str(root/'native/check_scte.cpp'),'-o',str(compiler)],check=True)
body=struct.pack('>BIHHHBBB',1,4242,7,4000,300,1,2,1)
msg=b'\xff\xff'+struct.pack('>H',30)+bytes([0,0,1,0,0,0,0,1])+struct.pack('>HH',0x101,14)+body
cue=bytes.fromhex(subprocess.check_output([str(compiler),(b'\x08'+msg).hex(),'90000'],text=True).strip())
(out/'input-section.bin').write_bytes(cue)
raw=seed.read_bytes();tables=sections(raw);pid,pmt=next((pid,s) for pid,s in tables if s[0]==2)
assert len(pmt)<150 and crc(pmt)==0
length=(pmt[10]&15)<<8|pmt[11]
program=pmt[12:12+length]+b'\x05\x04CUEI'
patched=bytearray(pmt[:10]+struct.pack('>H',0xf000|len(program))+program+pmt[12+length:-4]+b'\x86\xff\xfe\xf0\x03\x8a\x01\x01')
n=len(patched)+4-3;patched[1]=(patched[1]&0xf0)|(n>>8);patched[2]=n;patched+=struct.pack('>I',crc(patched))
result=bytearray();pmt_cc=0;cue_cc=0
for offset in range(0,len(raw),188):
 p=raw[offset:offset+188];p_pid=(p[1]&31)<<8|p[2]
 if p_pid==pid:
  result+=packet(pid,patched,pmt_cc);pmt_cc=(pmt_cc+1)&15
 else:result+=p
 # Repeat a fixed target time, like a source retransmitting its cue.
 if offset in (188*100,188*500,188*900):result+=packet(0x1ffe,cue,cue_cc);cue_cc=(cue_cc+1)&15
# An explicit source splice_null must survive; it is not an internal heartbeat.
null_msg=b'\xff\xff'+struct.pack('>H',16)+bytes([0,0,2,0,0,0,0,1])+struct.pack('>HH',0x102,0)
null_section=bytes.fromhex(subprocess.check_output([str(compiler),(b'\x08'+null_msg).hex(),'180000'],text=True).strip())
result+=packet(0x1ffe,null_section,cue_cc)
(out/'input.ts').write_bytes(result)
print(out/'input.ts')
