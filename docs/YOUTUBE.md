# YouTube SDR encoder profile

Select **YouTube · RTMPS**, keep the prefilled server or enter the one shown by
YouTube Studio, and paste only your stream key into the separate masked field.
Choose SCTE **Strip**: this RTMPS profile carries no SCTE-35 stream. For embedded
captions, enable the matching embedded 608/708 option in YouTube Studio and
verify reception with a known caption source.

The preset targets **1080p30 SDR**:

| Setting | Value |
| --- | --- |
| Processing | Deinterlace flagged interlaced frames, fit within 1920×1080, pad to 16:9, square pixels |
| Scan / rate | Progressive, constant 30 frames/s; other source rates are converted |
| Video | H.264 High, level 4.1, 8-bit yuv420p, CABAC |
| Rate control | Select 6, 8, 10 or 14 Mbit/s CBR; VBV buffer is twice the selected rate; filler/HRD signaling |
| GOP | 60 frames / 2 seconds; scene-cut keyframes disabled |
| Prediction | Up to 2 B-frames, 1 reference frame |
| Color | SDR Rec.709 output matrix/tags, limited range; use an SDR Rec.709 source |
| Audio | AAC-LC, stereo, 44.1 kHz, 128 kbit/s when source audio exists |
| Transport | FLV over RTMPS, port 443 |

These choices follow [YouTube's live encoder guidance](https://support.google.com/youtube/answer/2853702?hl=en)
checked 2026-10-27. The current H.264 recommendation for 1080p30 is 14 Mbit/s;
14 Mbit/s remains the default for existing routes. Allow additional upload
capacity for audio, protocol overhead and other traffic. If encoding keeps pace
to a local file but RTMPS falls behind, try a lower **YouTube video bitrate**
before adding buffers. Changing bitrate requires stopping and restarting the
route. Resolution remains 1080p30; 50p/60p presets are not exposed yet.

A workstation test on October 29 found that 14 Mbit/s RTMPS fell to about 24 fps
while the same profile to a local file produced all 600 frames in 20 seconds
of media. At 8 Mbit/s, both YouTube-only and combined SDI/YouTube tests delivered
all frames without capture overruns. This indicates an upload/ingest bottleneck
on that path, not a universal 14 Mbit/s limit. Those isolation tests used a
static caption journal; full live-caption validation is recorded separately.
HDR tone mapping and color-primary conversion are not implemented. Do not send
HDR and assume that changing the output tags makes it SDR.

Each output has its own encoder/filter chain. A concurrent TS output can retain
interlacing and SCTE conversion while YouTube receives progressive video.
Interlaced video is actually filtered, not merely labeled progressive.

A selected FFmpeg needs `yadif`, `scale`, `pad`, `setsar`, `fps`, `setfield`,
`sidedata`, libx264, AAC and RTMPS. Preflight checks the filters/RTMPS capability.
The old minimal extended builds do not contain all these filters: rebuild the
capture executable locally using the updated script and select its path. A
missing-filter readiness error is expected with those older builds.

## Test before going live

Start with a local recording/loopback, then a private/unlisted YouTube test.
Check YouTube Studio's stream health, captions, A/V sync and CPU load. The preset
uses software encoding; the P6000 is not required. Deinterlacing/scaling adds CPU
work. This project has verified actual progressive output and GOP/audio metadata
with synthetic interlaced material; that does not certify a physical SDI source
or YouTube's live acceptance.

Developer verification without publishing a stream:

```bash
python3 tools/verify_youtube.py --output-dir build/youtube-check
```

The tool replaces the generated destination with a local FLV file, then checks
its decoded scan type, frame rate, resolution, aspect ratio, keyframes, audio
and video bitrate using ffprobe. Optional `--ffmpeg` / `--wine` arguments exercise
a Windows executable under Wine. Output directories must be new.
