# Installation and first test

## Choose your media engine

SpankVANC is the control app. FFmpeg is a separate executable. A normal FFmpeg
can handle file/network routes and its supported caption pass/strip. SDI input
needs an FFmpeg built with DeckLink support and compatible Desktop Video.
The live caption source monitor and SCTE conversion additionally need this
project's patches, built locally; a stock DeckLink build is not enough.

Required media encoders: libx264, MPEG-2 video (for TS if desired), native AAC.
Protocols depend on route: UDP, SRT, RTMP/RTMPS. YouTube also needs the filters
listed in [its profile](YOUTUBE.md). The app probes capabilities and blocks a
route with missing requirements. Do not bypass the checks.

## Windows 11 x64

1. Obtain the **Windows x64 App** ZIP and matching `.sha256` from the personal
   repository's release page. Verify with PowerShell `Get-FileHash <zip> -Algorithm SHA256`.
2. Extract the entire ZIP into a new writable folder. Keep the old folder for
   rollback; stop its running instance before opening the new one.
3. Install a Desktop Video version compatible with your card from
   [Blackmagic support](https://www.blackmagicdesign.com/support/family/capture-and-playback).
   Original Duo and Duo 2 are different products; preserve a known working driver.
   The original Duo test system used Desktop Video 12.8.
4. Supply your separately obtained/built `ffmpeg.exe`. Keep any required DLLs
   alongside it. Use **Configure FFmpeg.cmd** or enter the path when prompted by
   **Start SpankVANC.cmd**. No GPU setup is needed.
5. Open **http://127.0.0.1:8877** if the browser does not open. Keep the console
   running. Ctrl+C stops the application.
6. Choose the detected SDI device and input mode. `Hi59` means 1080i59.94 fields/s
   (29.97 frames/s); `Hi50` means 1080i50. Select the mode matching the source.
7. Start with a new local TS file, Captions Pass, SCTE Strip and GPO disabled.
   Check route readiness, record briefly, stop and inspect the recording.

For a locally built extended capture executable, edit `settings.json` alongside
the launcher. Keep the existing general FFmpeg path and add:

```json
{
  "ffmpeg_path": "C:\\FFmpeg\\ffmpeg.exe",
  "decklink_ffmpeg_path": "C:\\SpankVANC-capture\\ffmpeg.exe"
}
```

Do not paste this example over other settings without preserving your paths.
An explicit capture path overrides automatic selection. The environment variable
`SPANKVANC_DECKLINK_FFMPEG` is also supported. See the
[local Windows cross-build guide](WINDOWS_EXTENDED_BUILD.md).

To upgrade, extract into a fresh folder and configure your media-engine paths.
You can copy `settings.json` and `runtime/route.json` from the stopped older
version locally; these can contain credentials and must not be uploaded.
Older YouTube destinations migrate to server/key fields automatically.
YouTube on older minimal extended FFmpeg builds needs a local rebuild with the
new deinterlace/scale filters; preflight explains when this is missing.

## Linux / source installation

Python 3.11+ is sufficient for the app; it has no third-party Python runtime
dependencies. On Ubuntu, install Python and FFmpeg using your package manager,
then from this checkout run:

```bash
python3 -m spankvanc doctor
python3 -m spankvanc serve
```

Open **http://127.0.0.1:8877** on that machine (RDP/browser on the workstation is
fine). Distribution FFmpeg packages commonly lack DeckLink input; see
[Ubuntu DeckLink build](UBUNTU_DECKLINK.md). SDK and drivers are separate downloads.

To set the general engine or select an isolated state folder:

```bash
export SPANKVANC_FFMPEG=/absolute/path/to/ffmpeg
export SPANKVANC_DECKLINK_FFMPEG=/absolute/path/to/local-capture-ffmpeg
python3 -m spankvanc serve --state-dir runtime --port 8877
```

From source on Windows, install Python 3.11+ and use `py -3 -m spankvanc serve`.
The portable package includes its own Python and does not need pip or system
Python. Mac hardware integration is not a supported target.

## Captions and SCTE

Use a known SDI caption/cue source. At the bottom of the page, Start source
monitor can display incoming captions without transmitting an output. A route
uses the same capture session; another app cannot capture the same port at once.

For UDP/SRT/TS select **Convert 104 → 35** only with a locally patched engine.
Use **Continue A/V** while testing: unsupported messages are discarded, counted,
and retained under **Rejected SCTE-104 messages**. Strict mode stops the route
instead. Continuing does not preserve a rejected cue. Inspect downstream PMT,
section CRCs, event IDs and timing. Source SpliceNull requests are distinct from
the internal cadence packets, which are not emitted as constant null cues.

## Logs and troubleshooting

Scroll below route controls to **Activity → Engine log** (a page section).
The caption source monitor is below it. Rejected cue details are saved in
`runtime/scte-rejections.ndjson` and one bounded backup. Saved routes are in
`runtime/route.json`. Windows **Diagnostics.cmd** writes capability/build reports
in `diagnostics/`; inspect reports before sharing and never attach saved routes
with real stream keys. Logs redact media URLs.

If a device is missing, check Desktop Video Setup, SDI input selection, driver
support and whether another application holds the port. If a mode is missing,
use the actual discovered mode list. If features are unavailable, run diagnostics
and verify the selected executable rather than replacing drivers blindly.

For multicast packet errors, see [UDP diagnosis](UDP.md). For interlace warnings,
choose the **YouTube** output type to apply the progressive preset; generic
RTMP intentionally retains its generic settings.
