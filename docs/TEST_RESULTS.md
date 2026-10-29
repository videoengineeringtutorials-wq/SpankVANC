## Online activation checks — October 28, 2026

The full application suite passed **84 tests** after the 0.10.0 changes.
The licensing and media browser checks passed. The 0.10.0 licensing client and UI add tests for persisted activation identity,
server-controlled expiry, monotonic short leases, startup lock, direct media API
lock, outages, malformed replies, HTTPS/redirect rejection and route shutdown.
Browser checks exercise locked startup, masked key entry, activation, reload
without exposing the key, and relocking after an expired response.

The live isolated ASP.NET/SQL endpoint was checked with temporary test keys for
exact 30-day activation, unchanged expiry on re-entry, installation binding,
revocation, expiry and a race between two first activations. Existing hosted
site health passed, and protected configuration, DLL and assets were preserved.
Test rows were removed after verification; no real customer key is in these
records. The handler compiled against .NET Framework 4.6. See
[licensing verification](verification/licensing-0.10.0.json).

## Release publication checks — October 28, 2026

- Application suite rerun: **73 tests passed**, including caption policies,
  local media and network loopbacks, Whisper lifecycle and build safeguards.
- Native CMake/CTest rerun: **3 tests passed** (ANC policy, ESP32 and ESP8266
  bench helpers). These do not exercise physical serial dispatch.
- User reports that the Leader saw captions on SDI after 0.9.1. This is
  receiver evidence reported by the user, without an archived scope capture.
  Generated captions on the YouTube service and physical SCTE reception still
  require downstream tests.
- Browser persistence, progressive YouTube encoder profile, and UDP packet
  verification rerun successfully. The UDP loopback had zero transport or
  continuity errors; these are local software checks.
- First-time installation docs now distinguish the portable app, separately
  supplied media engine, local extended build and optional Whisper environment.
  A fresh-PC beginner walkthrough and the new Whisper install recipe have not
  been exercised end to end on a clean Windows installation.

## Native Windows SDI caption/SCTE output — 2026-10-28

Current version: 0.8.0. Latest regression suite: **64 tests passed**. Browser
checks passed port/policy selection, SCTE-35 PID entry, Continue/Stop and
save/reload persistence without JavaScript errors.

The user confirmed working caption SDI output after the 0.7.0 engine update.
The 0.8.0 engine was subsequently built on the Windows workstation
using Ubuntu 24.04 under WSL 1, SDK 12.8 Windows headers and cached dependencies.
No BIOS or Desktop Video driver change was required.

Native Windows tests passed opaque SCTE-104 byte/fragment/line retention, VANC
checksum and packet ordering, V210 decode/encode side-data carriage, independent
caption stripping and a timed SCTE-35 → 104 roundtrip. The C++ regression suite
also covers program cue types, descriptors, fragmentation, PTS adjustment/wrap,
dedupe and rejected cues. Real device discovery and all four SDI policy
combinations plus both TS conversion error policies passed preflight.

These checks do **not** establish physical SCTE reception or compatibility with
every receiver/card/format. The user was asked to restart into 0.8.0; restart and
downstream SCTE analyzer evidence are still pending. Earlier dated sections below
are historical and their “not implemented” statements may be superseded.

See [SCTE evidence](verification/scte-output-0.8.0.json),
[caption evidence](verification/decklink-playout-0.7.0.json),
[operating limits](SDI_SCTE.md) and [the handoff](PROJECT_HANDOFF.md).

> Historical development records follow. Earlier “private trial” packaging
> descriptions do not establish redistribution rights. Public 0.6.0 assets
> exclude all capture FFmpeg binaries; see REDISTRIBUTION.md.

# Development verification — October 26, 2026

Environment: Linux, Python 3.12.3, FFmpeg 6.1.1, g++ 13.3.0, DeckLink SDK 15.2.

## Automated checks

- Python/core/media: 12 tests covering route validation, metadata capability
  gates, per-output policy independence, configuration round-trip, URL secret
  redaction, loopback HTTP host/origin/control-token validation, cue identity
  deduplication, serial format and 33-bit PTS wrap.
- Actual caption fixture: 75 source frames with embedded A/53 captions;
  75 caption-bearing frames after pass processing and zero after Strip for
  both H.264 and MPEG-2 video. Independent caption decoding recovered
  `SPANKVANC CAPTION TEST` from each codec's pass output. Audio was confirmed
  as AAC-LC with ADTS sync/profile/48-kHz headers in actual TS PES payloads.
- Local transport receivers: UDP MPEG-TS, SRT MPEG-TS and RTMP FLV outputs
  carried MPEG-2/AAC (UDP) and H.264/AAC (SRT/RTMP). Received files were probed and fully decoded.
  These are short loopback checks, not a long-run network or interoperability test.
- Native CMake/CTest: ANC packet classification/byte retention and independent
  stripping, plus ESP32 and ESP8266 host-simulated serial/pulse logic. Three tests.
- SDK extraction diagnostic: compiled against installed Linux SDK 15.2.
  Help works; enumeration reports no matching DeckLink device on this PC.
- Chromium browser integration: desktop and mobile layout; two independent
  output policies; save/check/start through the actual Python API; real encode
  output; no browser JavaScript errors. Desktop preview is `control-panel.png`.
- SCTE policy UI/API regression: SDI→TS 104→35, TS→SDI 35→104, SDI→SDI
  104 pass/strip, TS→TS 35 pass/strip, mixed outputs, changing input types,
  and RTMP/YouTube exclusions. Invalid carriage actions cannot be saved/started.
- Codec UI/API regression: TS outputs offer H.264 and MPEG-2 independently;
  RTMP/YouTube allow H.264 only; SDI shows uncompressed video/PCM audio.
  Video codec selection survives save/reload. Missing encoder capabilities
  block only outputs that require that encoder. Old routes default to H.264.

## Physical / platform work still required

- Extracting raw ANC from the user's Duo / Duo 2 / Mini Recorder, including
  legacy-card packet-interface support and correct input-mode/connector setup.
- Native SDI A/V capture/playout integration and metadata receiver verification.
- SCTE-104 decoding, ST 2010 fragmentation, SCTE-35 conversion/insertion,
  reverse mapping, scheduling, cancellation and actual serial dispatch.
- audioWhisper source-audio integration and measured synchronized program delay.
- Full CEA-708 fixtures, broadcast interlace/HDR/color behavior, receiving
  player interoperability, private YouTube test and long-run clock/disconnect tests.
- Real ESP board/toolchain compilation, wiring/polarity and timing measurements.
- Windows execution/native SDK support and release installers.

The source package contains a development foundation and bench preparation.
UI settings for unfinished paths are saved, but preflight blocks starting them.

## Remote Mini Recorder input integration — 2026-10-27

Ubuntu 24.04.4, Desktop Video 15.3a5, DeckLink Mini Recorder, SDI 1080i59.94.
A dedicated FFmpeg build at pinned revision
`a23e094488f139522c0e175e9766212a1213e486` uses the provided legacy 608 ANC patch.
The system FFmpeg and Desktop Video packages were not replaced.

A 12-second live capture produced three simultaneous local TS outputs:

| Output | Decoded frames | Frames with caption side data | Video | Audio |
| --- | ---: | ---: | --- | --- |
| Caption pass, H.264 | 360 | 360 | 1920x1080, top field first | AAC, 48 kHz, stereo |
| Caption pass, MPEG-2 | 360 | 360 | 1920x1080, top field first | AAC, 48 kHz, stereo |
| Caption strip, H.264 | 360 | 0 | 1920x1080, top field first | AAC, 48 kHz, stereo |

The hardware test uses `tools/verify_decklink_capture.py`, isolated state and
local file destinations. No external stream was published. Caption packet carriage
was verified; this sample does not establish readable caption text for every source
or full 708 service coverage. SCTE conversion remains unsupported.

An isolated remote browser-control instance passed device/mode selection,
save/reload persistence, SCTE gating, start/stop, refresh discovery and mobile
layout with no browser JavaScript errors. The local 16-test Python suite includes
synthetic caption text decoding and UDP/SRT/RTMP loopback regression checks.

## Live caption monitor and SCTE-104 → SCTE-35 — 2026-10-27

The bottom-of-page monitor decodes CEA-608 CC1–CC4 from source A/53 triplets,
before output filtering. Pop-on, paint-on, roll-up, repeated controls, parity,
XDS exclusion, per-field/channel isolation, bounded history and stale/no-signal
states have automated coverage. Browser QA exercised standalone monitoring,
service selection while a route is active, automatic device handoff to routing,
stop/release and mobile layout. No browser JavaScript errors were observed.

The connected Mini Recorder source was recorded to two local TS outputs for
120 seconds using isolated test state. The monitor received 3,604 valid frames,
decoded live CC1 text and observed one real SCTE-104 packet. It converted one
program splice without conversion errors. Independent TS parsing verified a
valid-CRC SCTE-35 splice_insert on PID 0x0102, event 0x00287ECF (2653903), with
normal splice-out, 90-second duration, auto-return, and output pts_adjustment
126,000 ticks. TSDuck independently decoded the emitted section. The PMT had
CUEI registration, stream_type 0x86 and cue_identifier_descriptor. The parallel
Strip output had no SCTE PID or sections. No external stream was published.

Synthetic tests verify normal/immediate out/in, cancel, duration, time-signal,
raw descriptors, 33-bit wrap, fragmented and duplicated ST 2010 packets,
malformed lengths and unsupported timestamp/operation rejection. A separate
encoded TS regression uses a section packetizer independent of the modified mux:
three splice commands survive re-encoding, all CRCs validate, and their 126,000
clock adjustment exactly matches the output video PTS shift. The Strip output
has zero cues. Explicit demux encoder time base and passthrough frame timing
avoid H.264 timestamp phase rounding.

Reproduction:

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 tools/verify_scte_pipeline.py \
  --ffmpeg "$PWD/build/ffmpeg-decklink/bin/ffmpeg" \
  --output-dir "$PWD/runtime/bench/new-scte-test"
```

The cue converter supports the subset in UBUNTU_DECKLINK.md. This does not
establish support for encrypted/component/schedule messages, UTC/VITC/GPI clock
mapping, typed segmentation requests or reverse conversion. The live text
monitor renders 608 compatibility services; native 708 text is not rendered.

## Suppress generated SCTE-35 idle sections — 2026-10-27

Generated once-per-second splice_null packets are now marked as internal cadence
packets with AV_PKT_FLAG_DISPOSABLE. They still prime demux probing and advance
stream interleaving, but the SCTE TS section writer suppresses them. Source
splice_null requests retain their ordinary flags and are emitted normally.

An 8-second Mini Recorder bench capture received zero SCTE-104 packets and
emitted zero SCTE-35 sections. Video output grew continuously after startup
(7,077,888 bytes by the eighth sample), and the PMT retained its SCTE PID.
The encoded TS regression preserved three real splice commands and one explicit
source splice_null, with valid CRCs and unchanged clock alignment; its Strip
output contained zero sections. All five SCTE converter unit tests passed.

This supersedes the original externally emitted heartbeat behavior. Existing
routes pick up the new private FFmpeg binary when next started.

## Windows 11 x64 / original Duo portable trial — 2026-10-27

`tools/package_windows.py` builds a portable ZIP containing application sources,
CMD launchers, diagnostics and the official CPython 3.14.10 x64 embeddable runtime.
The Python download SHA-256 was checked against its official release page; its
PE machine header is x64. ZIP integrity and hashes for every packaged file were
validated. The package does not include or replace FFmpeg, drivers or SDK files.

The legacy compatibility layer parses FFmpeg's device/mode lists, preserving
original Duo input names and PAL trailing-space fourcc values. It omits custom
SpankVANC hooks and newer FFmpeg flags for an unpatched capture binary. Required
mode/10-bit/caption capabilities and unsupported SCTE paths are gated. Windows
FFmpeg subprocesses use a new process group and graceful Ctrl+Break shutdown,
with a termination fallback.

All 30 automated tests passed, including legacy device parsing, nonzero-success
list commands, command compatibility, caption feature gates, launch configuration
and graceful-stop contracts. A mock-capability browser test verified original
Duo selection, readiness, the SCTE gate, the unavailable monitor explanation and
mobile layout with no JavaScript errors. This browser QA ran on Linux.

Actual Windows execution and original Duo hardware capture are NOT verified.
The ZIP is a compatibility trial, not a claim of Windows parity for the custom
Ubuntu source-monitor/SCTE pipeline. Native Windows runtime testing is required.

## Windows extended capture binary — 2026-10-27

A separate MinGW x64 FFmpeg 7.0.2 capture executable was built against SDK 12.8
headers (0x0c080000). It statically links x264, SRT/OpenSSL and compiler runtimes;
PE imports are Windows system DLLs only. The original user FFmpeg and Desktop
Video installation are preserved. GPU/NVENC and SDI output are disabled.

The actual Windows executable ran under Wine. Both `spankvanc_anc` and
`spankvanc_scte35` options are present; UDP, SRT, RTMP/RTMPS and TLS protocols are
compiled in. An actual Windows decoder helper built from the shared cue parser
produced a valid-CRC splice section. The Windows FFmpeg then re-encoded a TS
fixture preserving three splice commands and one explicit source null; the
Strip output had none. CRC/PMT checks passed, and the 126,000-tick SCTE clock shift
matched the video PTS shift. The caption fixture preserved 75 captioned frames,
stripped all captions from the clean output, and independently decoded the known
caption words. All 32 Python unit/media tests passed.

The FFmpeg 7.x DeckLink options use `draw_bars` rather than the newer
`signal_loss_action`. The launcher selects `capture-ffmpeg/ffmpeg.exe` for SDI
while retaining the configured general FFmpeg for other inputs. Per-file hashes,
SDK/build notes, licenses and the binary verification report are included in the
extended package. This is a private nonfree workstation trial.

These checks exercise actual Windows machine code under Wine; physical SDI,
Blackmagic COM registration and ANC extraction on the user's original Duo with
Desktop Video 12.8 remain unverified until the workstation test.

The actual Windows executable also passed UDP loopback and continuous encrypted
SRT loopback under Wine. The SRT run observed eight real splice sections and
two explicit source nulls, all CRC-valid. This exercised the statically linked
Windows SRT/OpenSSL stack; it was a continuous-stream test, not validation of
finite-stream receiver shutdown/drain behavior.

## Windows cue recovery trial 0.3 — 2026-10-27

User reported original Duo capture, UDP output and live caption monitor working
with Desktop Video 12.8, followed by a red ANC/SCTE error and status 1. Supplied
Activity log confirms 1080i29.97 capture and SCTE data stream mapping, but lacks
the actual rejection reason. The original cause is not established by that log.

The recovery update defaults to discarding rejected messages while continuing
A/V and later supported cues, with optional strict stop. Native tests cover
unsupported operations and orphan fragments between valid cues, valid section
CRCs, strict stop, bounded monitor history, diagnostic persistence/rotation and
Activity-log retention. The full 34-test suite passed before adding the final
persistence test; all six caption/diagnostic tests then passed. Browser checks
passed for default policy, saved strict policy, retained reason/ANC payload,
literal text rendering and mobile layout.

Rebuilt Windows FFmpeg ran under Wine: extended options including strict policy
present; actual Windows decoder recovered after an unsupported message and
stopped in strict mode. Synthetic TS output retained three splice commands and
one source null with valid CRC, matched video clock adjustment (126000 ticks),
and stripped SCTE when requested. Captions: 75 pass frames, zero stripped;
independent text decoding passed. Proof is in
`build/windows-cross/verification-recovery-03/verification.json` and packaged.
No physical-card validation of the recovery change has been performed.

## Multi-command MOM trial 0.4 — 2026-10-27

The user's retained diagnostic identified the old single-command restriction:
`Multiple SCTE commands in one MOM are unsupported`. The supplied ANC packet
contains two 0x0101 normal return-to-network requests for events 0x00289A80 and
0x00289A77, both with 5055 ms preroll. SCTE 104 2013 sections 7.2.3.1/7.2.3.4
allow multiple normal requests with supplements scoped to their preceding
request. The decoder now produces separate ordered sections, scopes descriptors
correctly and validates the MOM before emitting or committing dedupe entries.

All 37 unit/media tests passed, including exact captured-payload regression,
duplicate suppression, descriptor isolation, orphan descriptor rejection and
atomic rejection without poisoning later valid cue deduplication. TSDuck
independently decoded the captured-payload output as two non-immediate network
returns with correct event IDs and target PTS 2671200 at source PTS 2216250.

Rebuilt Windows binary under Wine passed: exact captured-payload conversion,
both sections surviving actual Windows FFmpeg TS muxing, event IDs and output
clock adjustment preserved, valid CRCs, strict stop and continue recovery.
Synthetic output contains five splice sections (three baseline plus these two),
one explicit source null, none on stripped output. Caption pass/strip remained
75/0 with independently decoded text. Report:
`build/windows-cross/verification-multi-04/verification.json`.
No physical Windows-card test of 0.4 was performed here.

## YouTube destination form 0.5 — 2026-10-27

All 40 unit/media tests passed. New tests cover server/key endpoint assembly,
legacy combined-address migration, missing-key preflight, malformed server and
pasted-full-URL rejection, idempotent validation and key redaction in plans.
Isolated Playwright check passed for default server, masked key, clear empty-key
prompt, whitespace trimming, save/reload, editable backup server, migration of
saved URLs, absence of the key in page text and mobile layout. The browser test
did not start an encoder or transmit any media. This package reuses the verified
0.4 capture executable and its Wine verification report unchanged.

## Public 0.6.0 encoder / transport / packaging checks

Synthetic interlaced source encoded through the actual YouTube command to a
local FLV with both Linux FFmpeg and Windows FFmpeg under Wine: 1920x1080,
progressive 30/1, square pixels, H.264 High, Rec.709, keyframes 0/60/120,
AAC-LC stereo 44.1 kHz. Short five-second video bitrate was approximately
15.3 Mbit/s including startup VBV behavior around the 14 Mbit/s CBR target.
A caption-bearing interlaced fixture survived the complete Windows YouTube
deinterlace/scale/fps chain: 90 caption frames on pass, zero on strip; independent
caption decoding recovered the test phrase. No YouTube service was contacted.

Actual Windows UDP datagrams on local loopback were TS-aligned (188..1316 bytes),
2021 packets over six referenced PIDs including SCTE PID 0x102. Six SCTE sections
survived; no unknown PIDs, scrambling, TEI flags or continuity errors were found.
This is not the user's multicast network: its reported corruption and 34.440 s
preroll remain unconfirmed. Default UDP datagram alignment was corrected in the
app; raw capture before/after on the real network is still needed.

Machine-readable synthetic reports are in docs/verification/. These reports
do not imply physical driver/card testing or authorize binary redistribution.
Public packages include only application/source files and licensed CPython.

The user confirmed the multicast URL omitted pkt_size and TSDuck ran on the
encoder PC. A second Windows-binary UDP reproduction without pkt_size emitted
unaligned datagrams including 1472-byte packets and 64-byte tails; the same
fixture with pkt_size=1316 emitted only complete TS packets and passed all
integrity checks. Report: docs/verification/udp-default-size-0.6.json. The exact
multicast receiver trace and reported preroll still require a retest.

Final checks: 43 unit/media tests and the isolated YouTube browser check passed.
All three native/firmware CTest cases passed. Public source/Windows app ZIPs
passed archive/manifest/dependency checks; an attempted FFmpeg bundle was refused.

## Guided setup / local build 0.6.1

48 unit/media tests passed, including SDK-version rejection before installs,
source-hash rejection, configuration preservation, paths with spaces and stock
engine rejection. The isolated YouTube browser test passed. Extracted app ZIP
resources and its standalone bootstrap --help were checked from a path with
spaces. Public package checks now require all guided-build support files.

The bootstrap completed a new Windows x64 dependency build from cached pinned
source archives and pre-generated SDK 12.8 Include headers in a fresh directory:
x264, OpenSSL, SRT and patched FFmpeg all compiled. A separate live download test
verified each FFmpeg/OpenSSL/SRT source URL, SHA-256 and extraction. SDK files
were locally supplied; no SDK download/acceptance was automated. The original
12.8 SDK IDL generation path and physical Windows/WSL launcher have not been
walked through here; a real beginner-machine test remains necessary.

The fresh executable ran under Wine. Actual YouTube-profile output was
progressive 1080p30 with correct keyframes/audio; captions passed after
deinterlacing (90 frames) and stripped (0), with independent text decoding.
Raw UDP retained six SCTE sections and had zero unknown PIDs, continuity/TEI
errors or scrambling flags. JSON reports are in docs/verification/.

AnimMouse's release metadata/README were inspected for the user-suggested link:
win64 nonfree builds list DeckLink/FDK AAC. No binary was downloaded, mirrored,
bundled or certified for redistribution, and a stock build is not represented
as containing SpankVANC-specific telemetry/conversion.

An additional IDL-generation check caught missing standard COM IDL imports in
Ubuntu MinGW. The helper now obtains libwine-dev through apt-get download and
extracts it locally for unknwn.idl and related imports, without installing the
Wine runtime. WIDL generation succeeded against the locally available SDK 14.x
IDL files using these imports; this validates the import/compiler setup, not
12.8 hardware compatibility or the complete Windows launcher. The fresh media
build above still used the already-generated 12.8 include files.

## October 28, 2026 — 0.9.0 Whisper integration

- 70 Python tests passed, including odd parity, duplicated CC1 controls,
  wrapping/decoder checks, capability gates, single capture, audio selection,
  independent output policy and SCTE command retention.
- Browser checks passed for replacement mode and CUDA/model/channel selection,
  save/reload persistence and readiness without JavaScript errors.
- The existing Windows Whisper/PyTorch environment recognized generated speech
  using `turbo` on the P6000/CUDA and `small` on CPU. Both produced parity-valid
  608 caption pairs; no dependency or audioWhisper source changes were needed.
- Native Windows filter checks passed for 25/60 fps pacing, reading pairs
  appended after EOF, upstream frame isolation and unrelated frame metadata.
- Physical receiver acceptance of newly generated captions remains pending.

- The complete Windows route produced 749 frames per TS output: 91 captioned
  frames in H.264, 91 in MPEG-2 and zero in the independent Strip output.
  Both replacement files were independently decoded to readable SRT text.
- SDI replacement with SCTE-104 pass passed real-device preflight. Newly linked
  native checks passed V210 decode/encode, SCTE packet/line retention, VANC
  checksums and independent caption stripping.
- Evidence: [Whisper verification record](verification/whisper-0.9.0.json).
- Windows lifecycle checks passed: user stop cleaned up the worker, forced worker
  failure stopped the route with a clear diagnostic, and a missing audio channel
  was rejected. A regression check covers pipe failure preceding worker notification.

## October 28, 2026 — 0.9.1 receiver framing repair

The user reported failed rendering of 0.9.0 generated captions on the Leader
and YouTube, despite detected 608 and working passthrough. The original offline
software decode did not check the frame-rate-specific transport budget.

- 73 Python tests and browser checks passed. New coverage includes ordinary
  word boundaries, oversized-word preservation, explicit column-zero reset,
  late receiver initialization and YouTube frame synchronization isolation.
- The old 29.97 fps test had 91 single-tuple frames and 658 frames without A/53;
  zero frames met the continuous 20-tuple budget used by the repair.
- Actual repaired H.264 TS, MPEG-2 TS and YouTube-profile local FLV each had
  749 decoded frames with 20 tuples per frame and all 210 generated pairs
  retained in order, exactly once. Independent Strip had no A/53.
- Independent SRT decoding verified whole words, exact 32-character rows,
  shorter following rows and a late join at four seconds.
- Native Windows checks passed at 23.976/24/25/29.97/30/50/59.94/60 fps for
  tuple budgets, fields, parity, V210 retention, CDP/VANC checksums, source
  isolation and partial journal writes followed by append.
- YouTube testing used a local FLV with its actual profile; no stream was sent
  to the service. Physical Leader and YouTube-service retests remain pending.

Evidence: [0.9.1 framing checks](verification/whisper-framing-0.9.1.json).
