SpankVANC 0.11.0 — Windows 11 x64 app

For an easier first install, use the Windows11-x64-Setup.exe release asset.
It opens the guided setup; see docs\WINDOWS_INSTALLER.md. It downloads speech
recognition and builds your media engine locally. It is not an offline bundle.

START HERE: double-click START HERE.html for the included quick-start page.
Setup Guide.url opens the complete online guide.
The offline text copy, docs\WINDOWS_BEGINNER.md, covers the full PC-and-card setup.
It includes the AnimMouse FFmpeg download link and explains basic vs extended features.

A license key and Internet access are required. Enter the key in Application
license after opening the browser. It lasts 30 days from first activation;
failed verification or expiry stops media processing. See docs\LICENSING.md.

1. Extract this entire ZIP into a NEW writable folder.
2. For manual setup, use Configure FFmpeg.cmd to select your ffmpeg.exe, then
   run Start SpankVANC.cmd. An unconfigured app opens guided setup instead.
3. Open http://127.0.0.1:8877 on this PC if the browser does not open.
4. Select the input/device/mode, check a local file route, and test briefly.
   Choose a new output filename; recordings are not overwritten.

Python is included, with its license at python\LICENSE.txt. No pip, administrator
or NVIDIA setup is needed to launch the app. Desktop Video must be installed
separately for DeckLink input. Keep the console open; Ctrl+C stops the app.

The YouTube output uses a prefilled RTMPS server and a separate masked stream
key. Its progressive 1080p30 SDR preset deinterlaces SDI sources, targets
14 Mbit/s CBR, and uses two-second keyframes. See docs\YOUTUBE.md.

UDP outputs now default to TS-aligned 1316-byte datagrams. See docs\UDP.md
for receiver diagnostics and the open multicast packet-integrity investigation.

FFmpeg, the DeckLink SDK and drivers are NOT included. The pinned extended
capture executable is a nonfree local build and cannot be redistributed in
this release. For source caption monitoring/SCTE conversion, build it locally
with the updated filters and configure decklink_ffmpeg_path in settings.json.
Older minimal extended builds lack some YouTube filters; preflight blocks them.
Basic DeckLink capture requires a separately supplied DeckLink-enabled FFmpeg.

Configure FFmpeg.cmd changes the general engine path. Diagnostics.cmd writes
capability reports to diagnostics\. Runtime settings can contain stream keys;
do not upload settings.json, runtime\route.json or recordings to GitHub.

Read docs\SETUP.md for installation, upgrades and troubleshooting,
docs\WINDOWS_EXTENDED_BUILD.md for the advanced local build,
and docs\REDISTRIBUTION.md plus THIRD_PARTY_NOTICES.md for dependency licenses.
SDI output supports selectable output ports and caption pass/strip after rebuilding
the local Extended engine with current 0.9.1 build support. Configure the output connector in Desktop
Video Setup, select DeckLink SDI as the output, choose its port, and set SCTE Strip.
Whisper CC1 replacement is available with a separate Whisper/PyTorch Python.
See docs\WHISPER.md for installation from scratch. Serial dispatch is not integrated.

Build Extended Capture.cmd automates a local extended engine build after
Ubuntu 24.04/WSL and user-supplied SDK 12.8 setup. Follow the beginner guide
first. It downloads build dependencies, compiles locally and saves the new path;
it does not install card drivers or upload build results.

SCTE update (0.8.0): SDI outputs can Pass SCTE-104 from SDI input, or Convert
35 → 104 from a TS input. See docs/SDI_SCTE.md for PID selection, timing and
Continue/Stop behavior. Rebuild the local engine before enabling these choices.

Whisper update (0.9.0): select audioWhisper replacement per output, then
Auto, CPU or CUDA. Set whisper_python_path in settings.json to an existing
Python with Whisper/PyTorch. Rebuild with current build support. Routed audio
is used directly; no OBS or microphone selection is needed. Caption recognition
adds lag; A/V is not delayed. See docs/WHISPER.md.

0.9.1 fixes generated 608 framing, receiver initialization and word wrapping.
Rebuild the local engine with current support and restart the app. Passthrough
is unchanged. Generated SDI captions have a user-reported Leader receiver test; detection alone
does not establish correctly rendered caption text.
