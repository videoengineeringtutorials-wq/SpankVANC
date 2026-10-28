SpankVANC 0.6.0 — Windows 11 x64 app

1. Extract this entire ZIP into a NEW writable folder.
2. Run Start SpankVANC.cmd and select your separately supplied ffmpeg.exe.
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
SDI output, Whisper recaptioning and serial dispatch are not integrated.
