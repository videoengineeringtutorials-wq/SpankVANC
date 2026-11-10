# November 10, 2026 — 0.15.1 test PC installation

Built 0.15.1 app/source/Setup and installed Setup into the existing test PC
application folder after confirming no Python/FFmpeg/app processes were running.
Isolated and working payload manifests, embedded imports and setup imports pass.
Settings, saved route and both selected media engine hashes preserved.
Dashboard 0.15.1 is open with route/monitor idle; both recognition backends and
serial runtime available. Native synthetic audio-only MPEG-TS through the NULL
command produced 65,536 bytes of 16 kHz mono float PCM without video output.
NULL preflight passes with both speech backends and no video encoder/filter.
127 local unit/media tests and diff whitespace check pass.
Physical EN530 reception and Faster Whisper CUDA inference remain unverified.
Installer/checksum and testing notes are on the test PC desktop.
No physical media or serial output started. No media engine rebuild required.
Public verification: verification/null-output-0.15.1.json.
Private paths, backups and installer hash belong in WORKSTATION_HANDOFF.md.

# November 10, 2026 — NULL EN530 output (local development)

Added NULL · EN530 serial only output. It uses routed audio and the existing
Whisper/serial worker, requires a serial port/runtime, and bypasses video
encoders, caption insertion filters and output device/destination checks.
Input requirements still apply. Mixed NULL/video routes share capture and
recognition. NULL has no Spanish CC2 or SCTE carriage.
127 unit/media tests pass, including serial-only preflight/command and mixed
output regressions; diff whitespace check passes. Physical EN530 reception
and browser operation remain unverified. No deployment or packaging performed.

# November 9, 2026 — 0.15.0 remote test installation

Remote connectivity restored. Copied and hash-verified Setup/checksum on test
PC desktop. Native isolated installer payload, embedded Python/setup imports,
uninstall/reinstall/repair/state preservation pass. Updated idle working app;
settings, saved route and selected local media engine hashes preserved. Installed
managed speech dependencies; both backends/serial probe available. Dashboard
0.15.0 open with route/monitor idle and saved OpenAI backend retained. CPU/int8
small.en synthetic speech through installed Faster Whisper worker generates
captions with valid 608 parity and decoded text. Physical media and EN530 serial
were not started; CUDA inference remains unverified.125 local tests pass.

Native testing caught PyAV19 metadata_errors API removal; pin PyAV16.0.1 in
guided setup, alongside FW1.2.1/CT24.6.0/pyserial3.5/setuptools80.9.0. Public
verification summary verification/faster-whisper-0.15.0.json. Private deployment
paths/backups belong in WORKSTATION_HANDOFF.md. No public release or commit.

# November 9, 2026 — 0.15.0 test installer prepared

User requested an updated installer on the remote test PC. Version0.15.0 across
app metadata/UI; guided setup now installs pinned Faster Whisper1.2.1,
CTranslate2 4.6.0, pyserial3.5 and setuptools80.9.0 in managed speech Python.
Resume adds these packages without reinstalling Torch when its profile matches;
imports are rechecked on each run. OpenAI remains the saved-route default.
App/source ZIPs and NSIS Setup built locally; archive hash/manifests/public-asset
checks pass.124 full unit/media tests passed plus the new managed-runtime upgrade
regression (12 setup tests pass). Windows-native installation/inference and
physical EN530 tests remain pending. Recorded remote endpoints unreachable;
asked user for current address. No remote file, process, route, settings or
engine changes; no GitHub publication or commit. Installer in local releases/.

# November 9, 2026 — local Faster Whisper / EN530 integration

Added optional Faster Whisper backend with 4s/2s overlapping routed audio,
word timestamp deduplication and missing-timestamp overlap fallback, plus optional
EN530 serial mirroring at1200 7O1 with original caption/E1 commands. Existing
OpenAI backend and saved-route defaults retained. UI/config/preflight/isolated
worker updated; optional dependency instructions in WHISPER.md. Guided setup
continues to install OpenAI Whisper. No deployment, publication, model download,
physical serial operation or existing running route changes. Real Faster Whisper
inference, Windows CUDA runtime and physical EN530 reception remain unverified.
All124 unit/media tests pass, including4 new overlap/serial/preflight tests;
`git diff --check` passes. Node is unavailable for a JS syntax CLI check.

# November 3, 2026 — 0.14.0 Windows release preparation

Packages the current local translation/CC2 work and earlier unpublished native
708/manual SCTE/SRT/hidden-process changes. Version0.14.0 across metadata/UI.
Guided setup now offers an optional Spanish checkbox, downloads pinned original
Helsinki-NLP weights with eight source SHA256 checks, converts locally to CPU
INT8, and verifies actual translation before marking the model usable. Runtime
uses app translation/python; converter dependencies use a separate setup-cache
target, reusing managed speech Torch without changing its packages. Existing
manual translation/venv installations remain supported. Pin setuptools80.9.0
because newer releases remove pkg_resources required by CTranslate2 4.6.0.

120 unit/media tests,3 native CTest benches, setup/CC2 browser checks and
UDP/progressive-video checks pass. Native Windows isolated installer payload,
embedded Python, setup imports, lifecycle repair/uninstall/reinstall, optional
translation source download/conversion/inference and cached-model reuse pass.
No physical media/driver/profile/app-route operations were performed for release
testing. Complete fresh-PC driver/WSL/CUDA walkthroughs remain unverified.
See verification/windows-release-0.14.0.json and existing caption reports.

Public Setup/App/source exclude FFmpeg, SDK, drivers, model weights, private
handoff/settings/routes, credentials and local recordings. Installer remains
unsigned/experimental. Current CC2 backlog policy is unchanged. GitHub release
uses the same prerelease status as the preceding tester build. Workstation
validation paths and publication details belong in private handoff.

# November 3, 2026 — Optional per-output Spanish CC2

User requested optional on-air Spanish CC2 after the Dashboard trial. Added
spanish_cc2=false per output, shown for audioWhisper replacement. Requires en
recognition and 608/both; 708-only and Pass/Strip disable the option. Selected
outputs read a route-scoped combined phrase journal; other outputs keep the
original CC1 journal. Spanish basic/special/extended 608 glyphs include accents,
ñ, ¿ and ¡. Native 708 Service1 tracks channel selection and ignores CC2.
No Spanish native Service2 is generated. Rebuild engine for the bilingual marker;
preflight checks model/runtime and engine. Manual preview text stays off air.

Bilingual journal serializes whole phrases and bounds backlog at4 seconds for
Spanish and10 for English, estimating25 pairs/s conservatively. Skips/backlog are
reported. Initial/silence erase both channels; closed route sinks reject late
translations. Translator preloads before capture. No A/V delay or source changes.

116 unit/media tests pass. New CC2 browser persistence/format/locking checks and
existing 708/manual-SCTE browser regressions pass. Eight actual H264/MPEG2 outputs
independently decode CC1/CC2, Spanish glyphs and isolated English Service1, with
300 frames each. Existing six native708 media regressions pass. Remote synthetic
speech → Whisper → OPUS → actual locally built engine passed,3 translations,
0 skips; independent decoding verified selected/unselected/stripped outputs,
539 frames each. Physical CC2 reception and sustained program throughput remain
unverified. Workstation install/backups/engine hashes are in private handoff.
No release/version bump, commit or push. docs/WHISPER.md describes operation.

# November 3, 2026 — OPUS-MT Dashboard preview

Added asynchronous CPU INT8 OPUS-MT English-to-Spanish preview with manual text
entry and live Whisper transcript submission. Separate optional isolated runtime;
no translator dependencies in core app. Bounded queue counts skipped phrases;
recent English/Spanish/latency shown using textContent. No Spanish output encoding
or CC2 integration. Deployment and model provenance in private workstation handoff.
108 existing tests plus3 preview tests pass; actual remote browser preview tested.
Physical live-route translation throughput and Spanish quality remain unverified.

# November 2, 2026 — 0.13.1 background console fix

User reported two blank command windows at route start. FFmpeg and the Whisper
worker were created as Windows process groups without CREATE_NO_WINDOW when the
launcher runs via pythonw. Added shared hidden_process_options and kept process
groups and captured logs. A private stdin quit pipe lets hidden Windows FFmpeg
stop cleanly; the existing bounded terminate/kill fallback remains. Applied hidden options to
FFmpeg/Whisper/DeckLink capability probes and launcher queries, too. No media
engine change or native rebuild is required. Preserve the running route; install
and reload the control app only when route and monitor are confirmed idle.

Local translation research is in LOCAL_TRANSLATION.md: OPUS-MT English/Spanish
baseline and larger pair model with CPU INT8 CTranslate2, MADLAD/M2M alternatives,
license distinctions, latency/quality evaluation plan and Spanish glyph gap in
current generated captions. No model/runtime download or translation integration
was authorized or performed by this research. Deployment details and verification
belong in private WORKSTATION_HANDOFF.md.

# November 2, 2026 — 0.13.0 native 708 output

User requested native 708 generation, per-output 608 / 708 / 608 + 708 choices,
and a new version on the remote Windows workstation. Added Service 1 two-row
roll-up encoding from the paced generated CC1 journal, DTVCC packet sequencing,
per-line window refresh and SDI CDP service announcements. Output pass mode can
select existing types; no input conversion or native 708 monitor work was added.
Legacy generated routes default to 608; source pass defaults to both. Manual
SCTE and SRT mode controls from the earlier work below are included in 0.13.0.

105 unit/media tests pass. New format/browser persistence and old-engine gate
checks pass. Independent CCExtractor decodes native 708 text from H.264 and
MPEG-2 outputs; 608/708-only exclusions and combined payloads are verified,
with all 240 frames retained in each of six encoded outputs. Native Windows
tests on the workstation pass 24 format/rate cases through filter → V210 →
CDP/VANC, service-info parsing, partial journal appends and source isolation.
See `verification/native-708-0.13.0.json` and `WHISPER.md` for limits. The user subsequently confirmed the new output worked on their Leader monitor.
Treat this as user-reported physical reception; the selected format, video rate
and individual-service checks were not specified. Installer/source/app
packages exclude locally built FFmpeg, SDK, drivers and private state. Workstation
installation details and backups belong in private `WORKSTATION_HANDOFF.md`.

The new engine is compiled in the workstation's existing WSL cache and copied
to a new filename. Prior engines and the general engine path are retained;
only the selected DeckLink/extended engine path needs changing for new formats.
Do not start or stop other captioning applications, or open an SDI device as
part of deployment verification. Existing routes/settings must be preserved.

# November 2, 2026 — manual SCTE and SRT controls (local development)

Implemented per-output Manual SCTE policy with live Start/End and duration.
DeckLink emits SCTE-104; UDP/SRT/TS files emit SCTE-35. User explicitly excluded
RTMP and YouTube. Duration is signaled with auto_return=false; End is explicit.
Updated local Windows build support and package inputs; old engines fail preflight
for manual mode. Added input/output Caller/Listener/Rendezvous controls preserving
existing SRT URL options. See `SDI_SCTE.md` for behavior and verification.

101 unit/media tests pass; new and existing playout browser checks pass. Local
Windows engine cross-build succeeded. Live Wine TS test verified two exact cues,
valid CRC/PMT/PID and isolation across three outputs with full frame retention.
SCTE-35 ↔ 104 codec round trips pass; physical SDI receiver test remains pending.
No workstation connection, installation, remote process start/stop, driver/profile
change, publication or release version bump in this work. User's separate remote
DeckLink captioning job must remain untouched (user says it finishes at 4 PM;
this is not permission to stop it). Changes remain in the local working tree.
Installing the app update and rebuilding its selected local engine are still
required before these controls can be used on the workstation.

# Project handoff — October 29, 2026

## 0.12.1 — YouTube upload backpressure diagnosis

User reported poor YouTube health/disconnection on the fresh installation and
low GPU use. Actual route: SDI capture → SDI + YouTube, both Whisper recaption.
CUDA is confirmed by the worker ready marker, NVIDIA compute-process listing
and growing caption journal; small.en is lighter than prior large-model use.

14 Mbit/s YouTube-only fell to ~24 fps; SDI-only held source rate. Identical
YouTube encoding to a local FLV produced all 600 frames with no capture overruns.
8 Mbit/s RTMPS tests, alone and with SDI, also produced full frame counts without
overruns. This indicates upload/ingest backpressure, even without observed TCP
retransmissions. Initial combined route had repeated capture overruns and SDI
underruns. User explicitly authorized stop/restart isolation tests.

Added selectable per-output 6/8/10/14 Mbit/s YouTube CBR in 0.12.1, retaining
14 as the backwards-compatible default. 97 unit/media tests passed. Controlled
network probes used a static copy of the caption journal with routed PCM drained
to null. Subsequent original-route testing used live small.en/CUDA recaptions
on both SDI and YouTube: 30 fps without capture/SDI/Whisper warnings over about
134 seconds, speed converging to 0.992x. YouTube Studio health remains unconfirmed.
0.12.1 repair installation passed every payload hash and preserved settings/route
bytes before changing only the YouTube rate to 8 Mbit/s. See the sanitized
[verification record](verification/youtube-bitrate-0.12.1.json).


## 0.12.0 — activation removed; clean installer retest

User explicitly requested removing application license restrictions, uninstalling
all existing workstation copies and trying a newly packaged installer from scratch.
This supersedes the historical activation instructions below. App version is
0.12.0. Removed the licensing client, enforcement/watchdog, activation API/UI
and related operator/client tests. MIT and dependency notices remain intact.
Existing license.json state is ignored. Setup needs Internet for dependencies;
local routes/monitoring need no licensing service. Historical hosted backend
source is retained only for old clients and excluded from new source packages;
no unrelated hosted services were changed.

Windows COM duplex discovery and profile-aware route checks are included.
Local verification: 96 unit/media tests; browser checks for offline startup,
visible controls, save/reload and no external requests, DeckLink output policies
and half-duplex explanation, and setup wizard. Native Windows payload/import verification and the isolated
install → idle-wizard uninstall → same-folder reinstall → repair checks passed.
The embedded Windows runtime passed three offline/no-activation Engine tests.


## Windows duplex diagnosis — October 29, 2026 (supersedes initial correction)

User's same-subdevice capture/playout failed at EnableVideoOutput with VANC.
A read-only SDK 12.8 COM query on the actual Windows workstation reports:
DeckLink SDI (1) and (2): half duplex, profile ID 0, two subdevices; legacy
SupportsFullDuplex=false on both. DeckLink 4K Extreme: full duplex, legacy
SupportsFullDuplex=true. Separate physical sockets do not establish simultaneous
capture/playout support. Do not claim same-subdevice I/O works on this card.

Added bounded child-process Windows COM attribute discovery in
`spankvanc/decklink_windows.py`, merged by exact display name into FFmpeg
input/output discovery. No SDK/compiler needed at application runtime. UI labels
same-subdevice half-duplex conflicts; preflight blocks them. Full-duplex devices
remain permitted. No profiles or drivers are changed. Existing VANC requirement
remains enforced so caption/SCTE pass cannot silently lose metadata.

Installed Python/UI updates with backups and hash checks, preserving settings
and saved route bytes. Native Windows discovery and preflight using the actual
selected local engine verified same-subdevice rejection and SDI (1) → SDI (2)
readiness. No physical output stream was started during diagnosis. App restart
needed to load this update. Verification: 105 Python tests and browser port/policy,
collision explanation, save/reload and refresh checks passed.

## DeckLink connector correction — October 29, 2026

Removed the blanket same-name SDI input/output rejection: a device name can
represent a full-duplex subdevice with separate IN and OUT sockets. SDK discovery
now reports active duplex state. Known half/simplex/inactive profiles still block
same-subdevice capture/playout. With FFmpeg-only discovery duplex is unknown:
preflight permits the selection with a note and the driver validates it at start.
No model-name heuristics or automatic profile changes are used. Duo 2 independent
connectors remain individually selectable as discovered subdevices; paired profiles
must be configured in Desktop Video Setup.

Verification: 102 Python tests passed, including same-name full/unknown duplex,
half/simplex/inactive rejection and different-subdevice selection. Linux SDK
native diagnostic syntax check passed. Physical I/O remains untested. Installed the Python/UI correction on the Windows workstation after reconnecting
at its updated address, with backups and matching SHA-256 hashes. Settings and
route hashes were preserved; native Python compilation passed. The active SDI
route was left running. Restart SpankVANC to load the correction; physical
same-subdevice IN/OUT testing remains pending.

## Historical 0.11.4 state (superseded by 0.12.0)

The source/app version was **0.11.4**, adding a guided online Windows installer.
The working Windows workstation remains on 0.10.0 with saved settings,
route and selected 0.9.1 media engine preserved. No app or media process was
started, and the owner license was not activated during installation.

The backend now also supports explicit **shared tester keys**, each granting an
independent 30-day window per installation. Private keys retain their original
binding. Existing 0.10.0 clients need no update. Parent-key revocation stops all
shared-key activations/checks. See `verification/shared-licensing.json`.
Shared installation IDs are saved random state, not hardware fingerprints.

- Enter a key in the Application license panel. SQL Server starts a 30-day
  period at first activation; repeated activation does not extend it.
- The isolated HTTPS handler/table are deployed on the existing TV-Watermark
  host. Existing DLL, config, assets and health were preserved.
- Startup/media starts require online validation. The server watchdog rechecks
  every minute and stops routes/monitoring after expiry, revocation or failure.
- Full application suite before shared server update: 84 tests; licensing and media browser checks passed.
  Hosted verification includes the actual client stopping a local test process
  after server-side revocation.
- Public source remains MIT. Modified builds and earlier versions can bypass
  the gate; this is not tamper-proof DRM. See `LICENSING.md` and
  `../licensing/README.md` for implementation and operator steps.
- Issued keys, operator SQL, database credentials and deployment scripts remain
  private, outside the checkout. Never include license.json in packages.

## 0.11.1 installer repair

- Existing SDK folders and pasted paths are accepted, including after visiting the download page.
- Recognized installs support repair and same-folder reinstall; private backups preserve overwritten files.
- Idle setup closes before uninstall; running app/media and busy setup block removal.
- 99 unit/media tests, browser SDK selection and native Windows install → idle-wizard uninstall → same-folder reinstall → repair passed. Settings and a local engine sentinel survived.

## 0.11.0 guided setup

- `tools/package_setup.py` wraps the audited app-only ZIP in a per-user NSIS
  EXE. It installs into a new versioned folder, adds shortcuts/uninstaller, and
  opens `setup/setup.py` with a local browser wizard.
- The wizard automates isolated speech dependencies/model caching and a local
  engine build under a dedicated WSL 1 Ubuntu Base environment. SDK selection
  uses a native file dialog and safe ZIP extraction. No Linux user account or
  typed build commands are required. Windows UAC/reboot and vendor downloads
  remain visible user steps; no vendor license is accepted automatically.
- Managed speech uses Python 3.13.12, Torch 2.7.1, Whisper 20250625 and small.en.
  `whisper_model_cache` in settings points the worker at its isolated models.
  Existing Python/legacy Whisper installations and saved routes are preserved.
- Installer is experimental and unsigned. Windows-native extraction, CPU speech
  setup/recognition and browser/unit checks are recorded separately from clean-PC
  driver/UAC/reboot coverage and the optional GPU profile. See `WINDOWS_INSTALLER.md`.
- No media engine, SDK, driver, Torch/Whisper binary or model is bundled.
  Public artifacts remain subject to `REDISTRIBUTION.md`.

## Prior deployed media state

SpankVANC is at **0.9.1** and installed on the Windows workstation for the next
launch. The saved route, general FFmpeg path and earlier engines were preserved.
The new Whisper integration supersedes the earlier
placeholder blocker; see `WHISPER.md`. The preceding 0.8.0 deployment record
below is retained as context.

Before this update, SpankVANC was at **0.8.0**. The Windows workstation received the application,
updated local FFmpeg engine and build support. The existing general FFmpeg path,
saved route and running processes were preserved. The user was asked to close
and reopen SpankVANC to load 0.8.0; that restart and physical SCTE reception have
not yet been confirmed in this conversation.

The user confirmed that the preceding caption SDI output update worked well on
the Windows PC. Treat this as a user report, not a controlled test of every
card, format or 608/708 service. The newer SCTE features have codec, application
and native Windows verification, but still need a downstream SCTE receiver test.

Private machine paths, SSH connection details, installed engine filenames and
backups are in `WORKSTATION_HANDOFF.md` when present. That file is excluded from
Git and public packages. Public release documentation must not contain it.

## 0.9.1: generated caption receiver repair

The user tested 0.9.0 on a Leader SDI scope and YouTube. Both detected captions,
but the Leader did not display text and YouTube rendered isolated characters.
Caption passthrough still worked on both. Treat this as a failed 0.9.0 receiver
test; the earlier software text-decoding results did not establish valid framing.

- The filter now emits a full frame-rate-specific A/53 budget on every frame,
  with field-1 CC1, null field-2 slots and invalid 708 padding. Encoded video
  carries A/53 in SEI/user data; SDI wraps it separately into CDP/VANC via V210.
- Per-line duplicated RU2, CR, explicit row-15 indent-zero PAC and row clearing
  initialize late-joining receivers and reset the cursor after a full row.
- Ordinary words wrap intact at 32 columns. Only a token longer than a complete
  row is split; all characters are retained.
- YouTube replacement uses the existing fps=30 filter as the only conversion.
  A later CFR sync duplicated a startup caption frame in testing; it is bypassed
  only for replacement. Caption passthrough behavior remains unchanged.
- Actual H.264 TS, MPEG-2 TS and YouTube-profile local FLV each carried 210/210
  generated pairs, exactly once, in continuous 20-tuple frames. Independent
  decoders verified text, row boundaries and late joining. Strip remained empty.
- New native checks cover eight broadcast rates, V210 packet retention, CDP/VANC
  checksums, field slots, parity, partial append/EOF and source isolation.
- Latest suite: 73 tests. See `verification/whisper-framing-0.9.1.json`.
- Restart the app to load the corrected engine and worker. The user subsequently confirmed captions on the Leader SDI receiver.
  YouTube-service reception of generated 0.9.1 captions remains pending. Recognition lag
  remains intentionally uncompensated. Leave `breakit.py` and its process alone.

## Prior 0.9.0: live audioWhisper replacement

- One FFmpeg capture opens DeckLink and taps the selected audio channel as mono
  16 kHz float PCM. No OBS, microphone selection or serial encoder is needed.
- A separate existing Whisper/PyTorch Python runs the worker by absolute path.
  Auto/CPU/CUDA selection affects transcription, not video encoding.
- Each selected output replaces source A/53 with paced odd-parity CC1 two-row
  roll-up data; SDI uses the existing V210 → CDP/VANC path. Other outputs and
  SCTE policies remain independent.
- Recognition has latency; A/V is not delayed. The former program-delay control
  was a placeholder and has been removed. Old `delay_ms` values are ignored.
- New files: `spankvanc/whisper_worker.py`, `spankvanc/whisper_runtime.py`,
  `native/vf_spankvanc_cc.c`, `tools/patch_ffmpeg_whisper.py`,
  `native/check_whisper_filter.c`, `tests/test_whisper.py`, `docs/WHISPER.md`.
- Build adds the filter, channel mapping and raw float PCM encoder/muxer.
  Replacement routes select the locally built capture engine, including TS → TS.
- Never modify the existing audioWhisper project or `breakit.py`. An existing
  Python environment is reused unchanged; no legacy script is executed.

## Changes made in the preceding conversation

### 0.7.0: selectable SDI output and captions

- Replace the unconditional SDI output blocker with capability-checked playout.
- Select actual detected DeckLink output ports; reject unavailable ports and
  using the same named input/output port. Do not assume Duo 2 connector profiles.
- Output uncompressed V210 video and embedded stereo 48 kHz PCM.
- Preserve decoded A/53 608/708 data through V210 encoding into regenerated
  VANC CDPs, or strip captions independently for each output.
- Add pinned libklvanc to the local Windows build, enable DeckLink output,
  and probe the custom caption playout option before allowing passthrough.
- Keep FFmpeg's AVClass pointer first in its private context; a regression
  check protects this layout. Discover output ports with `-sinks decklink`,
  falling back to a decoder-free legacy query.
- Prefer the installed WSL executable over the failing System32 launcher,
  use `--exec` and normalize Windows paths for WSL invocation.
- Verify extended playout capabilities before saving a newly built engine path.

### 0.8.0: SCTE-104 pass and SCTE-35 to 104

- SDI → SDI: preserve primary-stream DID 0x41 / SDID 0x07 payloads, source-frame
  association, VANC lines, ST 2010 fragments and repeat flags without decoding
  the cue commands. Caption pass/strip remains independent.
- TS → SDI: convert program splice_insert start/end/cancel (normal/immediate),
  time_signal, splice_null and opaque descriptor carriage into SCTE-104 MOMs.
- Retain the TS clock, apply pts_adjustment and 33-bit wrap, and compute pre-roll
  from the containing output video frame. Round pre-roll to milliseconds;
  require representable duration/pre-roll and reject late targets.
- Preserve SCTE-104 packet order when several packets share a VANC line.
  Converted fragments start on line 13 and continue on subsequent lines.
- Add optional decimal/hex SCTE-35 PID selection. Auto mode uses the first data
  stream. Use a single-program TS or the cue PID for the selected A/V program.
- Expose Continue A/V / Stop on rejected cue for TS conversion. Save rejection
  diagnostics under `runtime/scte-rejections.ndjson` and show them in the UI.
- Gate features against both capture and output engine capabilities. An older
  app-only/FFmpeg installation does not gain these features just from a UI update.

See [SDI SCTE operation and limits](SDI_SCTE.md) for precise supported behavior.
Encrypted sections, component splices, unspecified splice times, non-default
tiers, unsupported commands, late cues and unrepresentable timing are not converted.
General ANC passthrough, TS → TS SCTE-35 preservation and live serial dispatch remain outside the implemented paths.

## Implementation map

| Area | Files |
| --- | --- |
| Validation, capability gates, input/output commands, rejection retention | `spankvanc/engine.py` |
| DeckLink input/mode and output-port discovery | `spankvanc/ffmpeg_compat.py` |
| Port/policy/PID controls and capability display | `spankvanc/web/app.js`, `spankvanc/web/index.html` |
| Existing SCTE-104 → 35 decoder | `native/scte104.hpp` |
| Opaque SCTE-104 frame data, ST 2010 fragmentation, SCTE-35 → 104 conversion | `native/scte35_to104.hpp` |
| Ordered SCTE-104 VANC packet insertion | `native/scte_vanc.hpp` |
| Caption/V210 playout patch | `tools/patch_ffmpeg_playout.py` |
| SCTE capture, frame/packet side data, SDI output/conversion patch | `tools/patch_ffmpeg_scte_output.py` |
| Local Windows bootstrap/build | `tools/bootstrap_windows_capture.py`, `tools/build_windows_capture.sh`, `windows/build_capture.py` |
| Tests | `tests/test_decklink.py`, `tests/test_windows_build.py`, `tests/test_playout_patch.py`, `tests/test_scte_output.py`, `tests/check_playout_browser.py`, `native/check_scte_frame.cpp` |

The SCTE output patch adds private packet/frame side-data types and copies them
through decode/filter/V210 encode into the SDI muxer. Build the complete static
engine against its matching patched headers. Do not mix libraries/headers from
the earlier caption-only build when compiling the native frame test.

## Build and troubleshooting decisions

- Windows build: FFmpeg 7.0.2, user-supplied **DeckLink SDK 12.8 Win/include**,
  pinned x264/OpenSSL/SRT and libklvanc. SDK 14.4 was found on the Desktop but
  is not accepted by the current helper. Ubuntu hosts a Windows cross-compiler;
  it still needs the Windows SDK headers.
- The workstation initially lacked WSL and Virtual Machine Platform. Both were
  enabled and the user rebooted. WSL/kernel installation then succeeded.
- WSL 2 could not start because firmware virtualization was disabled. Ubuntu
  24.04 under **WSL 1** successfully completed this build without a BIOS change.
- The installed `C:\Program Files\WSL\wsl.exe` worked over SSH when the System32
  launcher returned “The file cannot be accessed by the system.” The helper now
  prefers the installed executable and avoids shell interpretation of paths.
- The minimal engine lacks a wrapped-frame decoder. Do not make discovery
  depend on decoding a synthetic lavfi source: use `-sinks decklink` or copy
  packets for the legacy list command.
- Do not rebuild every dependency unnecessarily. The WSL build directory caches
  dependencies; patching and rebuilding FFmpeg can reuse them.
- Follow the existing redistribution policy: public assets contain application
  source/runtime/build support, not the nonfree FFmpeg engine, SDK or drivers.

## Verification and artifacts

The earlier 0.9.0 Python suite passed **70 tests**, including six Whisper checks.
The latest 0.9.1 suite passed **73 tests**.
The earlier 0.8.0 suite passed 64 tests. Browser checks covered output-port
selection, independent policies, SCTE pass/conversion controls, PID entry,
Continue/Stop, save/reload and refresh persistence without JavaScript errors.

Native Windows checks verified V210 decode/encode side-data retention, opaque
SCTE-104 payloads/fragments/lines, VANC parity/checksum construction and packet
order, independent caption stripping, and a timed SCTE-35 → 104 roundtrip.
Real device discovery returned three inputs and outputs. All four SDI caption /
SCTE pass-strip combinations and both TS conversion error policies passed preflight.

Evidence: [caption playout record](verification/decklink-playout-0.7.0.json),
[SCTE output record](verification/scte-output-0.8.0.json), and
[test history](TEST_RESULTS.md). Physical SCTE receiver acceptance is still pending.

Current local assets are `releases/SpankVANC-0.9.1-source.zip` and
`releases/SpankVANC-0.9.1-Windows11-x64-App.zip`, each with a `.sha256` file.
Documentation edits require regenerating these files/checksums if distributing
an updated bundle. The 0.9.1 publication includes these implementation changes, updated beginner
installation docs and a browser-readable Windows START HERE.html. The private
workstation handoff remains excluded from Git and both release packages.

The 0.9.0 Windows tests additionally verified actual speech recognition on both
P6000/CUDA (`turbo`) and CPU (`small`), native filter pacing/isolation/EOF append,
and complete H.264/MPEG-2 TS replacement with an independent Strip output. Both
codecs were independently decoded to readable captions. Each replacement output
carried 91 captioned frames; Strip carried zero. SDI replacement with SCTE-104
pass passed device preflight; physical reception of generated CC1 is pending.
See `verification/whisper-0.9.0.json`.

The user will check generated SDI captions on a Leader scope. After discussing
the available Evertz delay card, the user explicitly chose to leave recognition
lag in place. Keep program A/V live; do not add automatic delay compensation.

## Resume here

1. Read this handoff and, when available, the private workstation handoff.
2. Check Git status and actual workstation settings/processes before editing.
3. The user reports that the Leader saw captions on SDI after 0.9.1. Continue
   receiver compatibility and YouTube-service testing as needed; keep reported
   receiver evidence separate from software checks.
4. With an appropriate known cue source and receiving analyzer, verify SDI
   SCTE-104 pass, caption/SCTE independence, then TS → SDI conversion and timing.
5. Record receiver evidence separately from native/preflight results. Remaining
   useful coverage includes receiver compatibility, source/port/card modes,
   long-run clocks, reconnects and dense cue/fragment traffic.
