# Windows setup: start with a PC and a Blackmagic card

**For the guided 0.11.0 setup EXE, start with [the installer guide](WINDOWS_INSTALLER.md).**
The instructions below retain the manual portable ZIP path.

This guide assumes **Windows 11 x64**, a supported Blackmagic capture card,
an SDI source and Internet access. You do not need Python, Git, Visual Studio,
an NVIDIA GPU or a compiler for the first setup path. The app includes Python.
Use a spare/test route first. This project is experimental.

## What to download

| Item | Where | Why |
| --- | --- | --- |
| Blackmagic Desktop Video for Windows | [Blackmagic support → Capture and Playback](https://www.blackmagicdesign.com/support/family/capture-and-playback) | Driver and device setup utility; required for the card |
| SpankVANC Windows x64 App ZIP | [SpankVANC Releases](https://github.com/videoengineeringtutorials-wq/SpankVANC/releases) | Browser control app and bundled Python |
| A separately supplied DeckLink-enabled FFmpeg | [AnimMouse release page](https://github.com/AnimMouse/ffmpeg-stable-autobuild/releases) | Basic capture and encoding; see limitations below |
| 7-Zip x64, if needed to open `.7z` | [Official 7-Zip site](https://www.7-zip.org/) | Extract the FFmpeg archive |
| DeckLink SDK **12.8** | Blackmagic SDK download/support archive | Only needed for the local extended build in Part B |
| Ubuntu 24.04 in WSL | Installed with Windows' `wsl` command | Only needed for the local extended build in Part B |

Desktop Video (driver) and Desktop Video/DeckLink SDK (developer files) are
**different downloads**. Installing the SDK does not install the card driver.
An original Duo is not a Duo 2. Choose Desktop Video that supports your exact
card; do not upgrade a working legacy-card driver simply because a newer one
exists. The original Duo development/test system used Desktop Video 12.8.

## Choose a path

| You want | Path |
| --- | --- |
| Get video/audio into a recording, UDP/SRT or YouTube quickly | **Part A:** separately downloaded FFmpeg, no compilation |
| Also display incoming caption text live and convert SCTE-104 to SCTE-35 | **Part A, then Part B:** local SpankVANC extended build |
| SDI output with captions, SDI SCTE-104 pass, or TS SCTE-35 → SDI SCTE-104 | **Part A, then Part B**; select the output connector in Desktop Video Setup |
| Generate new CC1 captions from program audio | **Part A, Part B, then [Whisper setup](WHISPER.md#windows-installation-from-scratch)** |

The AnimMouse project says its static Windows builds include DeckLink and FDK
AAC. Downloading a stock build **does not add SpankVANC's extensions**. Basic
caption pass/strip depends on that build and your source; verify at a receiver.
The live source monitor/SCTE conversion will be unavailable until Part B is done.

AnimMouse describes these as **nonfree** builds. The link is an optional third-party source, not a redistribution clearance. Review that project's notices
and applicable terms yourself. We do not mirror, bundle or automatically
redistribute its archives. See [our license audit](REDISTRIBUTION.md).

## Part A — no compilation

### 1. Install and check the card

1. Install the Blackmagic card according to its hardware instructions. If it is
   already working in this PC, keep that setup.
2. Install compatible **Desktop Video for Windows** from Blackmagic. Restart
   Windows if the installer asks.
3. Open **Blackmagic Desktop Video Setup** from the Start menu. Confirm the
   card appears and select SDI input if the model has input-selection controls.
4. Connect a known SDI source. Use Blackmagic Media Express, if included with
   your driver installation, to confirm a picture with the matching video mode.
5. Close Media Express and other capture programs before starting a SpankVANC
   route. Two applications cannot necessarily open the same input at once.

If Desktop Video Setup cannot see the card, resolve that before FFmpeg/app
setup. Record the actual card model and driver version for support.

### 2. Download and extract FFmpeg

1. Open [AnimMouse releases](https://github.com/AnimMouse/ffmpeg-stable-autobuild/releases).
   Expand a release's **Assets** list.
2. On Windows 11 x64, choose the asset whose name includes **win64**, not win32.
   Names vary by release; for example the inspected page offered
   `ffmpeg-8.0-ae69ef0-win64-nonfree.7z`. This is an example, not a claim that
   every current build/driver combination has been tested by SpankVANC.
3. Extract the entire `.7z` with 7-Zip or Windows' archive support. Do not try
   to run the executable from inside the archive. Keep all supplied files.
4. Put the extracted folder somewhere permanent and writable, such as
   `Documents\SpankVANC-tools\FFmpeg`. Locate **ffmpeg.exe** inside it (sometimes
   in a `bin` subfolder). Do not select `ffplay.exe` or `ffprobe.exe` in the app.

You do not need to change the Windows PATH. The app can remember the full
executable path. The earlier user-tested third-party build was FFmpeg 7.0.2;
newer builds still need a capability/driver check. If a newer FFmpeg reports
that the driver is too old, preserve your working legacy-card driver and use a
compatible engine or the pinned local build below; do not force an upgrade. The local extension build
below is pinned separately to 7.0.2 and SDK 12.8.

### 3. Download and open SpankVANC

1. From [SpankVANC Releases](https://github.com/videoengineeringtutorials-wq/SpankVANC/releases),
   download **SpankVANC-<version>-Windows11-x64-App.zip**. You do not need the
   source ZIP or GitHub's automatically generated source downloads for Part A.
2. The adjacent `.sha256` file records its checksum. To compare in PowerShell,
   run `Get-FileHash` followed by the downloaded ZIP path and
   `-Algorithm SHA256`. Compare the resulting hash with that file.
3. Right-click the ZIP → **Extract All** into a new writable folder, for example
   `Documents\SpankVANC`. Enter the extracted `SpankVANC-Windows` folder.
4. **START HERE.html** opens the included quick-start page in your browser.
   **Setup Guide.url** opens the full online guide. Double-click
   **Start SpankVANC.cmd** to launch the app. If Windows warns about downloaded
   software, verify the release origin/checksum before choosing to run it.
5. For this manual path, run **Configure FFmpeg.cmd**, drag the actual
   **ffmpeg.exe** from Explorer into its console and press Enter. Then run
   **Start SpankVANC.cmd** again. An unconfigured 0.11.0 app otherwise opens
   guided setup automatically.
6. A browser opens at **http://127.0.0.1:8877**. If it does not, enter that exact
   address in Edge/Chrome on this PC. Keep the console window open.

7. No activation is required. Continue to the local recording test below.

Python is already included. No pip, Python install, Git or GPU configuration
is needed. Stop another SpankVANC session if the port is already in use.

### 4. Record your first test

1. Choose **DeckLink / SDI** input and the actual device name. An original Duo
   may list `DeckLink SDI (1)` and `(2)`; names vary. Do not assume Duo 2 profiles.
2. Choose the input mode matching the source. `Hi59` is 1920×1080 interlaced at
   29.97 frames / 59.94 fields per second; `Hi50` is 25 frames / 50 fields.
3. Use a **local TS file** output with a new filename. The initial Windows route
   already points to a local recording under `runtime\captures`.
4. Leave GPO disabled and choose **SCTE: Strip**. Choose Captions Pass if supported;
   if the readiness check says that encoder cannot pass captions, choose Strip
   for the basic video/audio test and revisit captions after Part B.
5. Click **Check route / Validate**, resolve its listed requirements, then
   **Start**. Record briefly and **Stop**.
6. Play the resulting file with a TS-capable player. AnimMouse includes ffplay;
   from its extracted folder you can run `ffplay.exe "C:\path\to\capture.ts"`.
   Video/audio playback alone does not verify captions or cue timing.

### 5. Try UDP or YouTube

For UDP, enter a destination such as `udp://239.225.0.1:59000`. SpankVANC 0.6+
automatically adds TS-aligned `pkt_size=1316`. Windows Firewall/network routing
may require configuration for your receiver; first confirm a local recording.
See [UDP checks](UDP.md) before trusting a stream with continuity errors.

For YouTube, choose **YouTube · RTMPS**, retain the prefilled server, and paste
only your stream key into the masked field. Use SCTE Strip. The profile outputs
1080p30 progressive SDR with two-second keyframes. For embedded captions, set
YouTube Studio to the matching embedded caption option and verify reception.
Start with an unlisted/private test and inspect stream health, CPU and A/V sync.
See [the complete YouTube profile](YOUTUBE.md).

## Part B — add live caption monitoring and SCTE conversion

This builds FFmpeg **on your own PC** with our patches and the SDK interfaces.
It does not compile a new card driver or modify firmware. Blackmagic does not
need to be installed inside Ubuntu; the result runs on Windows. No GitHub fork,
GitHub account, GitHub Actions runner or cloud build is required.

You need administrator access for WSL installation, Internet access, several GB
of free storage and time for compilation (potentially an hour or more on a slow
PC). The engine has been built on a Windows 11 workstation using Ubuntu 24.04
under WSL 1. The helper and prerequisite checks have automated coverage; a
complete beginner walkthrough on a fresh PC remains to be verified.

### 1. Install Ubuntu 24.04 in WSL

1. Right-click Start → **Terminal (Admin)** or **Windows PowerShell (Admin)**.
2. Enter:

   ```powershell
   wsl --install -d Ubuntu-24.04
   ```

3. Restart Windows if requested. Open **Ubuntu 24.04** from the Start menu once.
4. Create a Linux username and password when prompted. This password is used
   for Ubuntu build-package installation; typing it may show no characters.
5. Close Ubuntu when initialization finishes. If WSL reports virtualization is
   unavailable, follow [Microsoft's WSL installation/troubleshooting guidance](https://learn.microsoft.com/en-us/windows/wsl/install).

The normal install uses WSL 2. WSL 1 also completed the local engine build on
the test workstation. If firmware virtualization is unavailable, consult
[Microsoft’s WSL manual installation guide](https://learn.microsoft.com/en-us/windows/wsl/install-manual)
to enable Windows Subsystem for Linux, restart, then run `wsl --set-default-version 1`
before installing Ubuntu. For an existing initialized distro,
`wsl --set-version Ubuntu-24.04 1` converts it; back up its files first.
`wsl --list --verbose` shows the installed distro and version.

WSL/Ubuntu must be installed before launching the helper. An unsupported ARM PC
or managed Windows policy may need separate setup; this guide targets x64.

### 2. Obtain SDK 12.8

1. Use Blackmagic's support/SDK download pages to obtain **Desktop Video SDK /
   DeckLink SDK 12.8**. Review and accept the SDK terms yourself.
2. Extract it completely. Find its **Win\include** folder, containing
   `DeckLinkAPI.idl` and `DeckLinkAPIVersion.h`.
3. Keep that folder available. If 12.8 is not offered in the archive, ask
   Blackmagic support for it. Do not assume the latest SDK is interchangeable:
   the helper checks the version and stops on other versions before building.

The SDK is never automatically downloaded, uploaded to the repo or accepted on
your behalf. The tested original Duo configuration used Desktop Video 12.8;
newer cards requiring newer drivers/SDKs need separate compatibility work.

### 3. Double-click Build Extended Capture.cmd

1. Use the **0.10.0 Windows App ZIP**, which includes the build helper
   and source support files. You do not need system Python, Git or Visual Studio.
2. Double-click **Build Extended Capture.cmd** in the extracted app folder.
3. Drag the SDK's **Win\include** folder into the console and press Enter.
4. After reviewing the displayed actions and accepting the SDK terms yourself,
   type **BUILD** to install Ubuntu build tools and compile locally.
5. Enter your **Ubuntu password** if sudo asks. The helper installs compiler
   packages in Ubuntu, downloads pinned FFmpeg/x264/OpenSSL/SRT source, checks
   archive SHA-256 values, extracts Wine development IDL imports (without installing the Wine runtime),
   generates SDK interface headers and builds the engine.
6. Leave the window open. Downloads/compilation can take a while; the current
   commands and build output remain visible. It reuses completed dependencies
   if you rerun after an interruption. A failed source hash check stops the build.
7. At success, the helper copies a new, timestamped executable into
   `capture-ffmpeg-local`, checks its Windows extension/filter capabilities and
   updates only the appropriate paths in your local `settings.json`. Existing
   general FFmpeg settings are preserved. It never replaces the old executable.
8. Close an older SpankVANC session, then run **Start SpankVANC.cmd** again.
   The console should list the new SDI capture FFmpeg path.

Builds and `bootstrap.log` live inside Ubuntu under
`~/.cache/spankvanc/windows-sdk12.8-ffmpeg7.0.2`. Windows launch/support files stay
in your extracted app folder. A failed build leaves the saved paths unchanged.
If no general FFmpeg was configured, the new local engine is used for both roles.

For source/Linux developers the equivalent is:

```bash
python3 tools/bootstrap_windows_capture.py \
  --sdk-include '/path/to/SDK12.8/Win/include' \
  --build-dir "$HOME/.cache/spankvanc/windows-sdk12.8-ffmpeg7.0.2" --install-deps
```

Use `--check-only` to validate SDK/tool prerequisites without installing or
building. See [advanced build details](WINDOWS_EXTENDED_BUILD.md).

### 4. Test the added features

- With a known caption source, click **Start source monitor** at the bottom of
  the page. CC1–CC4 text should appear. Native 708 text is not decoded; 708 packets
  are counted. A source without captions will not produce text.
- For TS/UDP/SRT, select **Convert 104 → 35** and **Continue A/V**. Unsupported
  cues are discarded and retained as diagnostics; they are not silently preserved.
- Use a known SCTE source and downstream analyzer to verify PMT references,
  section CRC, event IDs and cue timing. YouTube has no SCTE carriage here.
- For SDI output, build with the current 0.9.1 support files, choose **DeckLink · SDI**,
  select the detected output port, choose caption **Pass through** or **Strip**,
  and set SCTE to **Strip**. Configure that connector for output in Desktop Video
  Setup first. Output follows the source video mode; use a separate input port.
  Verify captions and audio with a downstream SDI analyzer before live use.
- For SDI SCTE-104 pass and TS → SDI conversion, follow [SDI SCTE](SDI_SCTE.md).
- For generated captions, follow [Whisper installation](WHISPER.md#windows-installation-from-scratch).
  Serial GPO dispatch remains unavailable.

## If something goes wrong

| Symptom | Check |
| --- | --- |
| Card missing from Desktop Video Setup | Driver/card compatibility, physical install and Blackmagic support |
| Card seen by Desktop Video but absent in SpankVANC | Actual selected FFmpeg must include DeckLink; run Diagnostics.cmd |
| No picture / wrong format | SDI cable/source, correct detected input port/mode, other apps holding the port |
| Caption source monitor says unavailable | Stock FFmpeg is selected; complete Part B and restart the app |
| SCTE says not ready | Extended build/path required; unsupported output types still cannot carry cues |
| YouTube missing filters | Use a capable stock build or rebuild the extended engine with current scripts |
| Cannot open `.7z` | Extract using 7-Zip from its official site |
| SDK version rejected | Select SDK 12.8 Win/include; a driver folder or newer SDK is not the same input |
| Build fails | Read Ubuntu bootstrap.log; fix the reported download/compiler problem and rerun; old engine path remains |
| No Ubuntu / WSL distro error | Restart Windows and open Ubuntu 24.04 once to finish creating the Linux account |
| Console closes / app won't start | Run the .cmd again; preserve its message; use Configure FFmpeg.cmd / Diagnostics.cmd |

The page's **Activity → Engine log** is below route controls, just above the
caption source monitor. Rejected SCTE details are below the caption monitor and
also in `runtime\scte-rejections.ndjson`. Diagnostics.cmd creates reports in
`diagnostics`. Do not upload `settings.json`, `runtime\route.json`, stream keys,
SDK files, build binaries or private broadcast recordings in a support issue.

The locally built capture engine is nonfree/unredistributable under the pinned
FFmpeg configuration. It stays on your systems. Neither the new helper nor
public Actions publishes it; release ZIPs remain source/app-only. A public repo
being able to run a build does not establish permission to distribute its result.
