# SpankVANC

A local broadcast routing and monitoring app for DeckLink SDI, captions and
SCTE cues. Python serves a browser control panel on **127.0.0.1:8877**; media
processing runs in a separately installed FFmpeg. No PHP or cloud backend.

**Version 0.6.0 — experimental.** Test on a spare route before using a live
program. CPU encoding is used; an NVIDIA GPU is not required.

## Get running

- **Windows 11:** download the **Windows x64 App** ZIP from
  [Releases](https://github.com/videoengineeringtutorials-wq/SpankVANC/releases),
  extract it completely, and run **Start SpankVANC.cmd**. Python is included;
  FFmpeg and Blackmagic Desktop Video are installed separately.
- **Linux / source:** install Python 3.11+ and FFmpeg, then run
  `python3 -m spankvanc serve` from this checkout. Open the local browser URL.
- Follow the [setup guide](docs/SETUP.md) for dependencies, device selection,
  first test, upgrades, logs and troubleshooting.

**Public downloads contain no FFmpeg binary, DeckLink SDK or driver installer.**
The pinned extended capture build uses FFmpeg's nonfree configuration and must
be built locally. See [redistribution audit](docs/REDISTRIBUTION.md) and
[third-party notices](THIRD_PARTY_NOTICES.md) before packaging dependencies.
Historical Extended trial ZIPs are not public release assets.

## Features and requirements

| Feature | Status / requirement |
| --- | --- |
| Local file, UDP, SRT, RTMP input/output | Available when supported by installed FFmpeg |
| DeckLink SDI input and embedded stereo audio | DeckLink-enabled FFmpeg + compatible Desktop Video |
| Device / mode discovery | FFmpeg or optional Linux native diagnostic; select actual detected mode |
| Up to eight outputs | Each has its own codec, caption and cue policies |
| TS video / audio | H.264 or MPEG-2, AAC-LC 48 kHz / 192 kbit/s |
| YouTube | Separate server/key fields; progressive 1080p30 SDR, 14 Mbit/s CBR, two-second GOP; see [encoder profile](docs/YOUTUBE.md) |
| UDP TS datagrams | Default 1316 bytes; aligned packet sizes validated |
| Caption pass / strip | Depends on source and FFmpeg A/53 capture/encoder support; verify at receiver |
| Live caption monitor | Local patched FFmpeg required; CC1–CC4 text, 708 packet counters, history and signal status |
| SDI SCTE-104 → SCTE-35 in TS | Local patched FFmpeg required; program splice start/end, normal/immediate, cancellation, duration, time_signal and raw descriptors |
| Multiple SCTE commands in one MOM | Converted in source order; descriptors scoped to their preceding command |
| Rejected SCTE messages | Continue A/V by default with retained diagnostics; optional strict stop |

SCTE conversion supports timestamp type 0 only. Unsupported operations are
reported and handled by the selected rejection policy. RTMP/YouTube has no SCTE
carriage in this release. Incoming captions are displayed locally; burned-in
text cannot be removed. HDR conversion and full native CEA-708 text decoding
are not implemented.

SDI playout, reverse SCTE-35 → 104, general ANC transport, Whisper recaptioning
and live serial GPO dispatch are **not integrated**. Firmware/native helpers are
bench tools. Preflight blocks unfinished features.

## Hardware and verification

User reports confirm original DeckLink Duo / Desktop Video 12.8 input discovery,
SDI capture, UDP output and live captions on Windows 11. A Linux Mini Recorder
was also used for input development. A live multi-command SCTE payload is covered
by regression tests. These observations do not establish compatibility with
every card, driver, format or caption source.

Actual Windows executable tests under Wine check synthetic caption/SCTE muxing,
progressive YouTube encoding and loopback UDP integrity. Wine does not validate
Blackmagic hardware or YouTube live acceptance. A reported multicast capture
with transport/continuity errors remains under investigation; see
[UDP troubleshooting](docs/UDP.md) and [test results](docs/TEST_RESULTS.md).

## Development

```bash
python3 -m unittest discover -s tests -v
cmake -S native -B build/native
cmake --build build/native
ctest --test-dir build/native --output-on-failure
```

Media tests need FFmpeg/ffprobe, g++, pkg-config and FFmpeg development libraries.
Browser checks use Playwright. See [contributing](CONTRIBUTING.md),
[change history](CHANGELOG.md), [architecture](docs/DESIGN.md),
[build instructions](docs/WINDOWS_EXTENDED_BUILD.md) and [source references](docs/SOURCES.md).

Saved routes may contain stream keys. Keep `runtime/`, `settings.json`,
recordings and diagnostics out of commits/issues. The server binds only to
loopback; do not expose it directly to the Internet. See [security](SECURITY.md).
