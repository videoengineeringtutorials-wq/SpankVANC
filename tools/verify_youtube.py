"""Encode an interlaced synthetic source to a local FLV with the actual YouTube profile.
No YouTube connection or credentials are used. Optional Windows binary runs under Wine.
"""
import argparse,copy,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from spankvanc.engine import DEFAULT,validate,command
p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--ffmpeg',default='ffmpeg');p.add_argument('--wine');p.add_argument('--caption-input',type=Path);a=p.parse_args()
a.output_dir.mkdir(parents=True,exist_ok=True)
def run(args):
 r=subprocess.run([str(x) for x in args],text=True,capture_output=True,timeout=120)
 if r.returncode:raise RuntimeError(r.stderr[-5000:])
 return r.stdout
def path(value):return 'Z:'+str(value.resolve()).replace('/','\\') if a.wine else str(value.resolve())
source=a.output_dir/'interlaced.ts';target=a.output_dir/'youtube.flv'
run(['ffmpeg','-v','error','-n','-f','lavfi','-i','testsrc2=size=640x360:rate=60000/1001','-f','lavfi','-i','sine=sample_rate=48000','-t','5','-vf','tinterlace=interleave_top','-c:v','mpeg2video','-flags','+ilme+ildct','-q:v','3','-c:a','aac',source])
source_info=json.loads(run(['ffprobe','-v','error','-select_streams','v','-show_streams','-of','json',source]))['streams'][0]
assert source_info['field_order'] in ('tt','tb')
cfg=copy.deepcopy(DEFAULT);cfg['input'].update(kind='file',address=path(source),realtime=False)
cfg['outputs'][0].update(kind='youtube',address='',youtube_stream_key='synthetic-test-key',scte='strip')
args=command(validate(cfg));args[0]=a.ffmpeg;args[-1]=path(target)
if a.wine:args=[a.wine,*args]
log=run(args)
info=json.loads(run(['ffprobe','-v','error','-show_streams','-show_frames','-of','json',target]))
v=next(s for s in info['streams'] if s['codec_type']=='video');audio=next(s for s in info['streams'] if s['codec_type']=='audio')
assert (v['width'],v['height'],v['r_frame_rate'],v['sample_aspect_ratio'],v['pix_fmt'])==(1920,1080,'30/1','1:1','yuv420p'),v
assert v['field_order']=='progressive' and v['profile']=='High' and v['color_space']=='bt709',v
frames=[f for f in info['frames'] if f['media_type']=='video']
assert all(not f['interlaced_frame'] for f in frames)
keyframes=[i for i,f in enumerate(frames) if f['key_frame']]
assert len(keyframes)>=3 and all(b-a==60 for a,b in zip(keyframes,keyframes[1:])),keyframes
assert audio['codec_name']=='aac' and audio['profile']=='LC' and audio['sample_rate']=='44100' and audio['channels']==2,audio
packets=json.loads(run(['ffprobe','-v','error','-select_streams','v','-show_packets','-of','json',target]))['packets']
bitrate=sum(int(p['size']) for p in packets)*8/(len(frames)/30)
assert 12_000_000<bitrate<16_000_000,bitrate
report={'source_interlaced':True,'output_progressive':True,'resolution':'1920x1080','fps':30,'keyframe_frame_indices':keyframes,'measured_video_bitrate':round(bitrate),'audio':'AAC-LC stereo 44100 Hz','windows_binary_under_wine':bool(a.wine),'youtube_live_ingestion_tested':False}
if a.caption_input:
 marked=a.output_dir/'caption-interlaced.ts'
 run(['ffmpeg','-v','error','-n','-i',a.caption_input,'-vf','setfield=tff','-c:v','mpeg2video','-flags','+ilme+ildct','-a53cc','1','-f','mpegts',marked])
 counts={}
 for policy in ('pass','strip'):
  cfg['input']['address']=path(marked);cfg['outputs'][0]['captions']=policy
  output=a.output_dir/('caption-'+policy+'.flv')
  caption_args=command(validate(cfg));caption_args[0]=a.ffmpeg;caption_args[-1]=path(output)
  run(([a.wine]+caption_args) if a.wine else caption_args)
  data=json.loads(run(['ffprobe','-v','error','-select_streams','v','-show_frames','-of','json',output]))
  counts[policy]=sum(any('Closed Captions' in item.get('side_data_type','') for item in frame.get('side_data_list',[])) for frame in data['frames'])
  assert all(not frame['interlaced_frame'] for frame in data['frames'])
  if policy=='pass':
   text=run(['ffmpeg','-v','error','-f','lavfi','-i',f'movie={output}[out0+subcc]','-map','0:s:0','-f','srt','-'])
   assert 'SPANKVANC CAPTION TEST' in text
 assert counts['pass']>0 and counts['strip']==0,counts
 report['caption_frames_after_deinterlace']=counts
 report['caption_text_independently_decoded']=True
(a.output_dir/'verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
