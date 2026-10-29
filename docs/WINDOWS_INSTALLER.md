# Guided Windows setup (0.11.2)

For public testers, download **SpankVANC-0.11.2-Windows11-x64-Setup.exe** from
[Releases](https://github.com/videoengineeringtutorials-wq/SpankVANC/releases).
This is one entry point for installation, downloads and the local engine build.
It is an **online installer**, not an offline bundle of every dependency.

## What the tester does

1. Download the Setup EXE and matching `.sha256`. Verify its SHA-256 using
   PowerShell `Get-FileHash`, or have the operator verify the download for you.
   The installer is not code-signed; Windows may show an unknown-publisher
   warning. Check its origin before running it.
2. Run the EXE, choose a writable folder and finish installation. Keep
   **Open guided setup** selected. The wizard opens in your browser on this PC.
3. If your Blackmagic card already works, keep its existing Desktop Video
   driver. Otherwise use **Open Blackmagic downloads** and install a compatible
   driver. Follow the vendor's restart instructions. Setup does not choose or
   upgrade your card driver automatically.
4. Use the wizard’s **Open SDK downloads** button for Blackmagic’s specific
   **Desktop Video 12.8 SDK** registration/download page and review its terms. Use
   **Choose SDK ZIP** to select that download. Setup extracts it and locates
   Win/include automatically; you do not have to find individual header files.
   Already have it? Choose **Use existing SDK folder…** or paste its folder path
   and click **Use this folder**. Opening the download page does not prevent this.
   If that vendor page later becomes unavailable, obtain 12.8 through Blackmagic
   support. This tested build does not accept newer SDKs.
5. Keep **CPU** selected for the first test. Review the download/build actions,
   check the consent box and click **Set up this PC**.
6. Approve Windows' administrator prompt for its Linux build support. If setup
   requests a restart, save your work and restart Windows yourself. Open the
   desktop **Finish SpankVANC Setup 0.11.2** shortcut afterward and click
   **Set up this PC** again. SDK selection and completed work are remembered.
7. If Microsoft C++ runtime setup opens, complete its vendor installer and
   return to the wizard. No commands or Linux account creation are required.
8. Leave setup open while it installs speech recognition and compiles your
   media engine. The progress panel reports the current stage; **Setup details**
   shows the build log. Allow at least **12 GB of free space** and potentially
   an hour or more. Downloads/builds can be reused after a failed attempt.
9. When ready, click **Open SpankVANC**. Enter the tester key in **Application
   license → Activate key**, then make a short local recording before trying
   SDI/network outputs. Installation does not start the 30-day license timer.

An operator or IT administrator may need to help with Blackmagic's downloads,
managed-PC permissions or a driver/card compatibility problem. The wizard does
not bypass vendor agreements or Windows administrator controls.

## What setup installs

- The EXE contains the app, its verified CPython control runtime, build support,
  license notices and browser wizard. It creates per-user desktop/Start menu
  shortcuts and an uninstaller. Recognized app folders can be repaired; replaced
  files and settings are backed up privately under the setup cache. Unrelated
  nonempty folders are rejected. Reinstalling after uninstall preserves settings
  and local engines. Close the app first; idle setup closes automatically, while
  a running setup task must finish before removal.
- A separate official **Python 3.13.12** distribution is downloaded into
  `%LOCALAPPDATA%\SpankVANC-Setup\speech-python`. Existing Python installations
  and legacy audioWhisper scripts are not modified.
- It installs **Torch 2.7.1**, **openai-whisper 20250625** and their pip
  dependencies there, and downloads **small.en** into a separate model cache.
  The app is pointed at that Python and model directory after success.
- CPU is the default. The optional CUDA 11.8 profile targets compatible NVIDIA
  GPUs. It is not a universal NVIDIA setup and has not been validated on a
  fresh GPU PC with this new wizard. A CUDA failure asks you to choose CPU.
  Video encoding stays on CPU; the CUDA selection affects recognition only.
- Microsoft C++ runtime setup is obtained from Microsoft's pinned official
  download when needed. Python, Ubuntu Base and runtime downloads are checked
  against recorded SHA-256 values. Pip uses the official PyTorch/PyPI indexes;
  Whisper verifies its model checksum. Top-level versions are pinned, but all
  transitive pip/APT package versions are not frozen.
- Windows WSL 1 support may be enabled. A separate Ubuntu Base 24.04 environment
  called **SpankVANC-Build** is imported. This avoids requiring firmware
  virtualization or a manually created Linux user. Setup never unregisters or
  changes the default of an existing Linux distribution.
- The patched FFmpeg engine is compiled on this PC and saved under the app's
  `capture-ffmpeg-local` directory. A working configured engine can be reused.
  Saved routes and unrelated settings are preserved. It is not redistributed.

The installer does **not** contain FFmpeg binaries, SDK files, driver installers,
Whisper/Torch binaries or model weights. It does not install the old standalone
`breakit.py` application, change GPU drivers, start a media route, or activate a
license. See [redistribution details](REDISTRIBUTION.md).

## Help, retries and removal

If a step fails, fix its reported problem and click **Retry setup**. Keep the
same app folder and the per-user setup data. Do not rerun the EXE into that
existing folder; use its Finish setup shortcut. Setup will not mark failed
steps successful or replace saved engine paths with an unverified build.

Logs and resumable state are under `%LOCALAPPDATA%\SpankVANC-Setup`. Review logs
before sharing them. Do not share license.json, saved settings/routes, SDK files,
recordings or keys intended to remain private.

Uninstall removes packaged app files and its versioned shortcuts. It preserves
settings, recordings, license state, speech/model downloads, local engine builds
and the Linux environment. Their removal is a separate operator decision.

The portable App ZIP and [manual beginner guide](WINDOWS_BEGINNER.md) remain
available for users who already have suitable engines/Python environments.

## Build and verification for maintainers

Build the portable ZIP with `python3 tools/package_windows.py`, then run
`python3 tools/package_setup.py` with NSIS 3 installed (or supply `--makensis`).
The builder audits the app-only ZIP before compiling and writes installer
checksums plus a public `.exe.json` payload-origin report. Native CI installs
into a fresh temporary folder using `/S /NOINTEGRATION` and runs
`tools/verify_setup_install.py`; no drivers, WSL changes, media or activation are
started by that smoke test. The regular setup flow is interactive, not silent.
