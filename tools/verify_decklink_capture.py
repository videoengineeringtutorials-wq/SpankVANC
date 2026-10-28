"""Capture a short local-file bench route and verify decoded A/V and captions.

Does not touch the control panel's saved route or send to network destinations.
Requires exclusive access to the selected SDI input while this test runs.
"""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from spankvanc.engine import DEFAULT, Engine, plan

p = argparse.ArgumentParser()
p.add_argument('--device', required=True)
p.add_argument('--mode', required=True)
p.add_argument('--seconds', type=int, default=12)
p.add_argument('--output-dir', type=Path, required=True)
a = p.parse_args()
if not 3 <= a.seconds <= 60:
    p.error('Capture duration must be 3–60 seconds')
a.output_dir.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='spankvanc-bench-') as state:
    engine = Engine(Path(state))
    cfg = copy.deepcopy(DEFAULT)
    cfg['input'].update(address=a.device, format_code=a.mode)
    cfg['outputs'] = [dict(name=name, kind='file', address=str((a.output_dir / (name+'.ts')).resolve()),
                          video_codec=codec, captions=captions, scte='strip', enabled=True)
                      for name, codec, captions in [('h264-pass', 'h264', 'pass'),
                                                    ('mpeg2-pass', 'mpeg2video', 'pass'),
                                                    ('h264-strip', 'h264', 'strip')]]
    readiness = plan(cfg, engine.capabilities)
    if not readiness['ready']:
        raise SystemExit('; '.join(readiness['blockers']))
    try:
        engine.start(cfg)
        deadline = time.monotonic() + a.seconds
        while time.monotonic() < deadline:
            if not engine.state()['running']:
                raise RuntimeError('Capture stopped early: '+'\n'.join(engine.state()['logs']))
            time.sleep(.25)
    finally:
        engine.stop()
        (a.output_dir/'engine.log').write_text('\n'.join(engine.state()['logs'])+'\n')
    results = {}
    for out in cfg['outputs']:
        result = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', out['address']],
                                check=True, capture_output=True, text=True)
        streams = json.loads(result.stdout)['streams']
        video = next(s for s in streams if s['codec_type']=='video')
        audio = next(s for s in streams if s['codec_type']=='audio')
        frames = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-show_frames', '-show_entries', 'frame=interlaced_frame:frame_side_data=side_data_type',
            '-of', 'json', out['address']], text=True))['frames']
        cc = sum(any('Closed Captions' in d.get('side_data_type', '') for d in f.get('side_data_list', [])) for f in frames)
        assert frames, 'No decoded video frames'
        assert audio['codec_name']=='aac' and audio['sample_rate']=='48000' and audio['channels']==2
        assert (video['width'], video['height'])==(1920,1080)
        assert cc > 0 if out['captions']=='pass' else cc==0, 'Caption policy verification failed'
        if a.mode.startswith('Hi'):
            assert all(f['interlaced_frame'] for f in frames), 'Interlacing lost'
        results[out['name']] = dict(video=video['codec_name'], width=video['width'], height=video['height'],
            field_order=video.get('field_order'), audio=audio['codec_name'], sample_rate=audio['sample_rate'],
            channels=audio['channels'], frames=len(frames), caption_frames=cc)
    (a.output_dir/'verification.json').write_text(json.dumps(results, indent=2)+'\n')
    print(json.dumps(results, indent=2))
