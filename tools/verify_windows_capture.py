"""Exercise a Windows capture build under Wine; does not claim hardware testing."""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import struct
import subprocess
import sys
from verify_scte_ts import inspect,crc,packet

p=argparse.ArgumentParser();p.add_argument('--wine',type=Path,required=True);p.add_argument('--ffmpeg',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--cxx',type=Path,required=True);a=p.parse_args()
a.output_dir.mkdir(parents=True,exist_ok=True)
root=Path(__file__).resolve().parent.parent

def windows(path):return 'Z:'+str(Path(path).resolve()).replace('/','\\')
def run(args):
    result=subprocess.run([str(x) for x in args],text=True,capture_output=True,timeout=60)
    if result.returncode:raise RuntimeError(f'Exit {result.returncode}: {args}\n{result.stderr[-5000:]}')
    return result.stdout+result.stderr

def win(args):return run([a.wine,a.ffmpeg,*args])
version=win(['-version']);options=win(['-hide_banner','-h','demuxer=decklink']);devices=win(['-hide_banner','-devices']);protocols=win(['-hide_banner','-protocols'])
assert '7.0.2' in version and 'SDK12.8' in version
assert all(name in options for name in ('spankvanc_anc','spankvanc_scte35','spankvanc_scte_strict'))
assert re.search(r'^\s*D\s+decklink\s',devices,re.M)
for protocol in ('udp','srt','rtmp','rtmps','tls'):assert protocol in protocols.split()
(a.output_dir/'version.txt').write_text(version);(a.output_dir/'decklink-options.txt').write_text(options)
# The SAME portable decoder header is compiled as an actual Windows executable.
helper=a.output_dir/'check-scte.exe'
run([a.cxx,'-static','-std=c++17',root/'native/check_scte.cpp','-o',helper])
body=struct.pack('>BIHHHBBB',1,4242,7,4000,300,1,2,1)
msg=b'\xff\xff'+struct.pack('>H',30)+bytes([0,0,1,0,0,0,0,1])+struct.pack('>HH',0x101,14)+body
section=bytes.fromhex(run([a.wine,helper,(b'\x08'+msg).hex(),'90000']).strip())
assert crc(section)==0 and section[13]==5
assert int.from_bytes(section[20:25],'big')&((1<<33)-1)==450000
bad=b'\x08\xff\xff\x00\x10'+bytes([0,0,1,0,0,0,0,1])+struct.pack('>HH',0x777,0)
recovered=run([a.wine,helper,','.join(p.hex() for p in (bad,b'\x08'+msg)),'90000','continue'])
assert 'rejected=1 failed=0' in recovered
assert crc(bytes.fromhex(recovered.splitlines()[0]))==0
strict=subprocess.run([str(a.wine),str(helper),','.join(p.hex() for p in (bad,b'\x08'+msg)),'90000','strict'],text=True,capture_output=True,timeout=60)
assert strict.returncode==2 and not strict.stdout.strip() and 'rejected=1 failed=1' in strict.stderr
live=bytes.fromhex('08ffff00300000e900000000020101000e0300289a80000013bf00000000000101000e0300289a77000013bf0000000000')
live_sections=[bytes.fromhex(line) for line in run([a.wine,helper,live.hex(),'2216250']).splitlines()]
assert len(live_sections)==2
assert [int.from_bytes(s[14:18],'big') for s in live_sections]==[2660992,2660983]
for section in live_sections:
    assert crc(section)==0 and section[13]==5 and not section[19]&0x90
    assert int.from_bytes(section[20:25],'big')&((1<<33)-1)==2671200
fixture=a.output_dir/'scte';run([sys.executable,root/'tools/make_scte_ts_fixture.py',fixture])
source=fixture/'input.ts'
source.write_bytes(source.read_bytes()+b''.join(packet(0x1ffe,s,4+i) for i,s in enumerate(live_sections)))
converted=fixture/'converted-win.ts';clean=fixture/'clean-win.ts'
args=['-hide_banner','-nostdin','-v','error','-n','-copyts','-i',windows(source)]
for output,data in ((converted,True),(clean,False)):
    args+=['-map','0:v','-map','0:a']
    if data:args+=['-map','0:d','-c:d','copy']
    args+=['-c:v','libx264','-threads:v','2','-preset','veryfast','-fps_mode:v','passthrough','-enc_time_base:v','demux','-c:a','aac','-avoid_negative_ts','disabled','-f','mpegts',windows(output)]
win(args)
before,after,stripped=inspect(source),inspect(converted),inspect(clean)
assert len(after['sections'])==6 and not stripped['sections']
assert after['pmt'][0]['cuei'] and any(s['type']==0x86 for s in after['pmt'][0]['streams'])
def first_pts(path):
    data=json.loads(run(['ffprobe','-v','error','-select_streams','v:0','-show_packets','-show_entries','packet=pts','-of','json',path]))
    return int(data['packets'][0]['pts'])
shift=first_pts(converted)-first_pts(source)
for b,c in zip(before['sections'],after['sections']):
    if b['command_type']==0:assert c['command_type']==0;continue
    assert c['event_id']==b['event_id']
    assert ((c['pts_time']+c['pts_adjustment'])-(b['pts_time']+b['pts_adjustment']))% (1<<33)==shift% (1<<33)
# Create caption-bearing MPEG-2 independently with the existing native fixture.
caption_helper=a.output_dir/'caption-fixture'
flags=shlex.split(run(['pkg-config','--cflags','--libs','libavformat','libavcodec','libavutil']))
run(['g++','-std=c++17',root/'tests/caption_fixture.cpp',*flags,'-o',caption_helper])
caption_source=a.output_dir/'caption-source.ts';run([caption_helper,caption_source])
passed=a.output_dir/'caption-pass.ts';removed=a.output_dir/'caption-strip.ts'
win(['-hide_banner','-nostdin','-v','error','-n','-i',windows(caption_source),'-map','0:v','-c:v','libx264','-threads:v','2','-a53cc','1','-f','mpegts',windows(passed),'-map','0:v','-c:v','libx264','-threads:v','2','-a53cc','0','-vf','sidedata=mode=delete:type=A53_CC','-f','mpegts',windows(removed)])
def caption_count(path):
    d=json.loads(run(['ffprobe','-v','error','-select_streams','v:0','-show_frames','-of','json',path]))
    return sum(any('Closed Captions' in x.get('side_data_type','') for x in f.get('side_data_list',[])) for f in d['frames'])
passed_count,removed_count=caption_count(passed),caption_count(removed)
assert passed_count>0 and removed_count==0
text=run(['ffmpeg','-v','error','-f','lavfi','-i',f'movie={passed}[out0+subcc]','-map','0:s:0','-f','srt','-'])
assert 'SPANKVANC CAPTION TEST' in text
report={'windows_executable_ran_under_wine':True,'decklink_options_present':True,'sdk_target':'12.8',
        'rejected_cue_recovery_verified':True,'strict_rejection_stop_verified':True,'windows_scte_decoder_crc_valid':True,'muxed_splice_cues':5,'live_multi_command_sections':2,'preserved_source_nulls':1,'strip_cues':0,
        'scte_clock_shift_matches_video':shift,'caption_pass_frames':passed_count,'caption_strip_frames':removed_count,
        'caption_text_independently_decoded':True,'windows_hardware_verified':False}
(a.output_dir/'verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
