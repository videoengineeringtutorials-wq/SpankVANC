# Changelog

## 0.11.0 — guided public Windows setup

- Add a single online Setup EXE with per-user app installation, shortcuts,
  safe uninstall, and a browser wizard for dependencies and local compilation.
- Select/extract a user-downloaded SDK ZIP, install an isolated Python/Torch/
  Whisper runtime and model cache, provision a dedicated WSL 1 build environment,
  and save only verified engine/runtime paths. Remember completed work for retry.
- Keep compiled FFmpeg, SDK, drivers and speech/model binaries out of public
  payloads. Vendor downloads/agreements, administrator approval and reboot may
  still be required. CPU is default; the optional CUDA path is experimental.
- Add native Windows installer verification in CI and setup failure/preservation
  checks. Existing media/caption behavior and licensing contracts are retained.

## Server update — shared tester keys (0.10.0-compatible)

- Add an explicit shared-key type with separate 30-day activation windows per
  installation. Existing private keys retain their one-installation binding.
- Preserve each activation’s expiry on retries and allow revocation of a shared
  key for all testers. Existing 0.10.0 clients need no update.

## 0.10.0 — online 30-day activation

- Add masked license entry and online checks at startup, before media starts,
  and every minute while running. Expiry, revocation or verification failure
  stops routes and source monitoring; activation remains accessible.
- Start a fixed 30-day window on first activation using SQL Server time.
  Re-entry never extends it; keys bind to one installation identifier.
- Add a standalone ASP.NET endpoint and isolated SQL Server table, with
  operator-only key issuance. No keys or database credentials are bundled.
- Preserve the 0.9.1 media engine and prior caption/SCTE behavior.

## 0.9.1 — generated-caption framing and receiver initialization

- Publish the 0.7–0.9 SDI playout, SCTE and Whisper updates together with a
  first-time Windows installation guide and browser-readable START HERE.html
  in the portable package. Clarify basic versus extended engine requirements,
  WSL 1 fallback, fresh Whisper setup and safe upgrade steps.
- Record the user's Leader SDI caption confirmation; YouTube generated-caption
  reception and physical SCTE receiver checks remain pending.

- Fix sparse replacement payloads: emit continuous frame-rate-specific A/53
  field slots and padding for encoded video and the SDI CDP/VANC builder.
- Reassert CC1 roll-up, explicit row-15 indent zero and row clearing for each
  generated line, including late-joining receivers.
- Wrap ordinary words intact at 32 columns; split only a token longer than a
  full row, preserving every character.
- Keep the YouTube FPS filter as the sole frame-rate conversion for replacement
  mode, preventing a later CFR sync stage from duplicating caption-bearing frames.
- Leave caption passthrough and its output synchronization unchanged.
- Gate replacement against the corrected local engine. Receiver detection alone
  and software text decoding were insufficient tests of the 0.9.0 framing.

## 0.9.0 — local Whisper caption replacement

- Select audioWhisper replacement independently on SDI and TS outputs.
- Read the selected embedded audio channel from the single routed capture;
  OBS, Windows microphone selection and serial encoders are not required.
- Run an isolated worker using an existing Whisper/PyTorch Python, with
  Auto/CPU/CUDA selection. Legacy audioWhisper projects remain untouched.
- Insert paced odd-parity CC1 two-row roll-up data through A/53 and SDI CDPs.
  Replace source 608/708 only on selected outputs; retain SCTE policies.
- Caption recognition adds latency; no program A/V delay is implemented.
  Remove the misleading delay control, retaining the old field for migration.
- Require a rebuilt local engine with the replacement filter and raw PCM tap.

## 0.8.0 — SDI SCTE output

- Pass SCTE-104 primary-stream ANC bytes, original frame/line and ST 2010 fragments from SDI input to selected SDI outputs independently of captions.
- Convert TS SCTE-35 program splice start/end/cancel, time_signal, splice_null and descriptors into SCTE-104 VANC.
- Preserve the TS clock and PTS adjustment/wrap, calculate per-frame pre-roll, suppress repeated sections, and report unsupported/late cues with Continue/Stop controls.
- Add optional SCTE-35 PID selection and enable SCTE policies only when the selected engine supports them.
- Keep prior engines and saved routes when installing the local update.
- Verification: 64 Python tests, browser control/persistence checks and native Windows codec/VANC checks passed; physical SCTE receiver acceptance is pending.

## 0.7.0 — SDI caption output

- Select detected DeckLink output ports and play uncompressed V210/PCM SDI.
- Pass decoded 608/708 captions into regenerated SDI VANC CDPs, or strip captions per output.
- Local Windows build now includes pinned libklvanc and caption-preserving V210 encoding.
- Requires a rebuilt local engine; Windows/Duo hardware validation remains pending.
- Fix DeckLink context layout, prefer decoder-free output discovery, and harden the Windows WSL launcher and playout verification.
- Verified native Windows engine execution, device discovery and pass/strip preflight with Ubuntu 24.04 under WSL 1.

## 0.6.1 — guided Windows setup and local build

- Full PC-and-Blackmagic-card beginner guide with the user-suggested AnimMouse
  download option, x64 extraction, driver setup, first recording and troubleshooting.
- Build Extended Capture.cmd guides a local Ubuntu/WSL build using user-supplied
  SDK 12.8 files, then verifies the new engine and saves its path.
- Automated prerequisite installation, pinned/source-hash-checked downloads,
  SDK interface generation and static Windows FFmpeg build; resumable dependencies.
- App ZIP includes build helper/support source, not SDKs or capture binaries.
  Existing engines/settings are preserved and build products stay local.

## 0.6.0 — first public experimental release

- Dedicated YouTube progressive SDR 1080p30 profile: deinterlacing, square-pixel
  scaling/padding, H.264 High CBR 14 Mbit/s, 2-second GOP, 2 B-frames / 1 reference,
  AAC-LC stereo 44.1 kHz / 128 kbit/s. TS output settings remain independent.
- Probe required YouTube filters and RTMPS in the selected FFmpeg.
- Default UDP datagrams to 1316 bytes; reject unaligned or oversized TS packet
  sizes. A live multicast report remains open for receiver-side validation.
- Separate prefilled YouTube server and masked stream key; migrate older routes.
- Multiple SCTE commands in one MOM, descriptor scoping and atomic validation.
- Continue A/V on rejected SCTE messages by default; retained, bounded diagnostics
  and optional strict stop. Supported cues become proper TS sections with CRC,
  PMT signaling and output-clock adjustment; internal heartbeat nulls stay internal.
- Live CC1–CC4 source monitor and compatibility discovery for original Duo.
- Public source and Windows app-only distribution, setup/build documentation,
  licensing audit, checksums and automated checks. No FFmpeg/SDK/driver binaries.

## Earlier local development trials (0.1–0.5)

These were workstation trials, not public releases. Extended packages contained
an FFmpeg build configured nonfree and are not eligible as public assets.
The source history here begins with the reviewed 0.6.0 snapshot.
