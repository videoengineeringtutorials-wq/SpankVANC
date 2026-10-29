# SpankVANC

A local broadcast routing and monitoring app for DeckLink SDI, captions and
SCTE cues. Python serves a browser control panel on **127.0.0.1:8877**; media
processing runs in a separately installed FFmpeg. Media and control remain local; 0.10.0 requires an online license check.

**Version 0.10.0 — experimental.** Test on a spare route before using a live
program. CPU encoding is used; an NVIDIA GPU is not required.

## Get running

**A license key and Internet access are required in 0.10.0.** Enter your issued
key in **Application license** after launching. It unlocks 30 days from first
activation; expiry, revocation or a failed online check stops media processing.
See [licensing and renewal](docs/LICENSING.md).

**New Windows user with just a PC and a card? Start with the
[complete beginner setup guide](docs/WINDOWS_BEGINNER.md).** It covers downloads, card drivers, the first recording, the local engine build,
and optional generated captions. The Windows ZIP includes **START HERE.html**.

- **Windows 11:** download the **Windows x64 App** ZIP from
  [Releases](https://github.com/videoengineeringtutorials-wq/SpankVANC/releases),
  extract it completely, and run **Start SpankVANC.cmd**. Python is included;
  FFmpeg and Blackmagic Desktop Video are installed separately.
- **Linux / source:** install Python 3.11+ and FFmpeg, then run
  `python3 -m spankvanc serve` from this checkout. Open the local browser URL.
- For local caption monitoring/SCTE conversion, **Build Extended Capture.cmd**
  builds the engine on your own PC using Ubuntu/WSL and user-supplied SDK 12.8 files.
  See [the guided steps](docs/WINDOWS_BEGINNER.md#part-b--add-live-caption-monitoring-and-scte-conversion).
- Follow the [setup guide](docs/SETUP.md) for dependencies, device selection,
  first test, upgrades, logs and troubleshooting.

**Public downloads contain no FFmpeg binary, DeckLink SDK or driver installer.**
The pinned extended capture build uses FFmpeg's nonfree configuration and must
be built locally. See [redistribution audit](docs/REDISTRIBUTION.md) and
[third-party notices](THIRD_PARTY_NOTICES.md) before packaging dependencies.
Historical Extended trial ZIPs are not public release assets.

Choose the **Windows11-x64-App.zip** asset for normal Windows installation.
The **source.zip** is for developers; GitHub’s automatic “Source code” downloads
do not include the portable Python runtime.

For SDI output, caption monitoring, SCTE conversion or Whisper replacement,
complete the beginner guide’s **Part B** local engine build. A stock FFmpeg
download provides only the basic path. Whisper also needs its own
[Python environment](docs/WHISPER.md#windows-installation-from-scratch).

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
| DeckLink SDI output | Select detected output port; local VANC engine, V210 video and embedded PCM audio |
| SDI SCTE-104 pass / strip | Independent of captions; local 0.8.0 engine and primary SDI data stream |
| TS SCTE-35 → SDI SCTE-104 | Supported program cues, optional PID and Continue/Stop; see [SDI SCTE guide](docs/SDI_SCTE.md) |
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

SDI output supports selectable DeckLink ports, uncompressed V210 video, embedded
PCM audio and caption pass/strip with the local VANC playout build. Caption pass
regenerates 608/708 CDPs; it does not preserve arbitrary ANC packets. Configure
output connectors in Desktop Video Setup and use a different port from input.
The user confirmed working caption SDI output on Windows. Wider hardware/format
coverage and downstream SCTE receiver verification remain pending.

SCTE-104 pass is available for SDI → SDI. TS → SDI converts supported SCTE-35
program commands to SCTE-104. See [SDI SCTE output](docs/SDI_SCTE.md) for PID
selection, timing limits and rejected-cue handling.

Whisper replacement adds live CC1 captions from routed program audio with optional
CUDA processing. See [Whisper setup and limits](docs/WHISPER.md).

General ANC transport and live serial GPO dispatch are **not integrated**. Firmware/native helpers are
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

## Project continuity

Read [the current handoff](docs/PROJECT_HANDOFF.md) to resume development, including
implementation locations, build decisions, verified results and pending receiver
checks. Workstation-specific connection details are kept in a separate private
handoff excluded from public packages.

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
