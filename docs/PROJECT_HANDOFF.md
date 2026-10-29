# Project handoff — October 28, 2026

## Current state

The source/app version is **0.10.0**, adding online 30-day licensing. The
Windows workstation was subsequently updated to 0.10.0 with saved settings,
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
