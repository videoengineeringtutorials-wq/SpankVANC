"""Reproducible SCTE conversion + encoded TS clock/signaling regression bench."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from verify_scte_ts import inspect

p=argparse.ArgumentParser();p.add_argument('--ffmpeg',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args()
root=Path(__file__).resolve().parent
subprocess.run([sys.executable,str(root/'make_scte_ts_fixture.py'),str(a.output_dir)],check=True)
source=a.output_dir/'input.ts';converted=a.output_dir/'converted.ts';stripped=a.output_dir/'stripped.ts'
args=[str(a.ffmpeg),'-hide_banner','-nostdin','-v','warning','-n','-copyts','-i',str(source)]
for path,data in ((converted,True),(stripped,False)):
    args+=['-map','0:v','-map','0:a']
    if data:args+=['-map','0:d','-c:d','copy']
    args+=['-c:v','libx264','-threads:v','2','-preset','veryfast','-fps_mode:v','passthrough','-enc_time_base:v','demux','-c:a','aac','-avoid_negative_ts','disabled','-f','mpegts',str(path)]
subprocess.run(args,check=True)
original=inspect(source);result=inspect(converted);clean=inspect(stripped)
assert result['pmt'][0]['cuei']
assert any(s['type']==0x86 and s['descriptors']=='8a0101' for s in result['pmt'][0]['streams'])
assert len(result['sections'])==len(original['sections'])==4
assert sum(s['command_type']==0 for s in result['sections'])==1
assert not clean['sections'] and not any(s['type']==0x86 for s in clean['pmt'][0]['streams'])
def first_pts(path):
    r=subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_packets','-show_entries','packet=pts','-of','json',str(path)],text=True)
    return int(json.loads(r)['packets'][0]['pts'])
shift=first_pts(converted)-first_pts(source)
for before,after in zip(original['sections'],result['sections']):
    if before['command_type']==0:
        assert after['command_type']==0
        continue
    assert after['event_id']==4242 and not after['cancel']
    target_before=(before['pts_time']+before['pts_adjustment'])% (1<<33)
    target_after=(after['pts_time']+after['pts_adjustment'])% (1<<33)
    assert (target_after-target_before)% (1<<33)==shift% (1<<33)
report={'video_pts_shift':shift,'converted_cues':sum(s['command_type']!=0 for s in result['sections']),'source_nulls':sum(s['command_type']==0 for s in result['sections']),'strip_cues':len(clean['sections']),
        'crc_valid':True,'cuei_registration':True,'scte_pid':result['sections'][0]['pid'],'target_clock_verified':True}
(a.output_dir/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
if result['sections']:
    raw=bytes.fromhex(result['sections'][0]['section']);(a.output_dir/'output-section.bin').write_bytes(raw)
    subprocess.run(['tstabcomp','--decompile',str(a.output_dir/'output-section.bin'),'--output',str(a.output_dir/'output-section.xml')],check=True)
print(json.dumps(report,indent=2))
