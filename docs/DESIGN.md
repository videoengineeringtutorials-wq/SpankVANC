# SpankVANC implementation design

## Product scope

An affordable SDI/IP ANC gateway centered on Blackmagic DeckLink. User-confirmed
targets are Linux, then Windows; no macOS deliverable is requested. The UI is
browser based with no PHP. User test hardware: original DeckLink Duo, possibly
Duo 2, and a Mini Recorder. Work on this PC is preparation for hardware testing
at work. Preserve the separate TV Watermark and audioWhisper projects.

## Intended pipeline

```text
DeckLink SDI ── SDK capture ──┐
                            ├─ timestamped A/V + owned ANC/caption/cue events
UDP/SRT TS ── demux/decode ──┤                 │
RTMP ── demux/decode ────────┘                 ├─ caption policy per output
                                              ├─ SCTE policy per output
program PCM ── audioWhisper ── caption timeline ┤
                                              ├─ SDI scheduled A/V + VANC (SDK)
                                              ├─ TS + A/53 captions + SCTE-35 → UDP/SRT
                                              ├─ H.264/FLV captions → RTMP(S)/YouTube
                                              └─ cue scheduler → serial → ESP GPO
```

The SDK is the SDI packet interface. It does not perform SCTE-104→35 conversion
or create 608/708 text encoding automatically. FFmpeg handles media codecs and
IP transports, not the contract that all ANC survives every route.

The current runtime includes DeckLink SDI input, the FFmpeg IP branches, a live
608 source monitor, and a supported SCTE-104 program-splice-to-SCTE-35 subset.
See UBUNTU_DECKLINK.md for the exact operations and timestamp constraints.
Scheduled SDI output, reverse cue conversion and recaptioning remain future work.

## Input/output carriage matrix

| Interface | A/V | Captions intended | SCTE intended |
|---|---|---|---|
| DeckLink SDI input/output | Baseband | SMPTE 334 CDP / 608 ANC | SCTE-104 in ST 2010 ANC |
| UDP MPEG-TS | Encoded | 608/708 in supported video user data | SCTE-35 sections with PMT signaling |
| SRT carrying MPEG-TS | Encoded | Same as TS | Same as TS |
| RTMP/RTMPS | H.264/AAC in FLV profile | Destination-compatible embedded 608/708 | No generic SCTE carriage promised |
| YouTube via RTMPS | H.264/AAC in FLV profile | Embedded captions; configure YouTube | No SCTE output in initial profile |

SRT is a transport protocol here, not a subtitle file format. MPEG-TS is a
container. RTMP is a distinct transport/container path, not another TS socket.
RTMP sources can have captions but may have no usable SCTE data. Metadata that
does not exist cannot be recovered by cross-conversion.

SCTE policy is constrained by both ends of each route:

| Input → output | Allowed SCTE actions |
|---|---|
| SDI → TS | Convert SCTE-104 → SCTE-35, or strip |
| TS → SDI | Convert SCTE-35 → SCTE-104, or strip |
| SDI → SDI | Pass SCTE-104, or strip |
| TS → TS | Pass SCTE-35, or strip |

UDP/SRT and the local TS test-file endpoints share the TS policy family. The
control panel gets these options from the backend, refreshes every output when
the source changes, and labels the actual standard/direction. Invalid actions
are rejected on save/start and blocked by preflight. RTMP input/output and
YouTube currently offer no SCTE carriage; they cannot synthesize missing cues.

## Output encoding

Each UDP/SRT/local TS output independently selects H.264 (`libx264`) or MPEG-2
video (`mpeg2video`). MPEG-TS is the container in both cases; MPEG-2 video is one
of the possible video codecs inside it. RTMP/YouTube use the FLV H.264 profile,
and backend validation rejects MPEG-2 video for those destinations. SDI is
uncompressed baseband, not an H.264/MPEG-2 encoder destination.

All encoded IP outputs use AAC-LC audio at 48 kHz and 192 kbit/s when source
audio is present. AAC is the codec, ADTS the AAC framing in MPEG-TS. LATM is
explicitly disabled for TS outputs. FLV uses AAC configuration/raw packet
framing instead of ADTS. SDI carries embedded PCM. The dashboard displays the
correct fixed audio format for each destination. Legacy route configurations
without a video codec default to H.264 for IP and uncompressed for SDI.

H.264 currently uses CRF 20 / veryfast; MPEG-2 uses quality scale 3 with a
15-frame GOP and two B-frames. These are prototype encoder defaults, not a CBR
broadcast profile. Bitrate/VBV, GOP, profile/level, frame conversion and
interlace controls remain future settings. Existing A/53 caption pass/strip
is exercised through both video encoders by real encode/decode tests.

For TS carrying full ancillary packets rather than dedicated SCTE-35, SMPTE
ST 2038 is a separate adapter, with explicit service/PID routing. It is not
interchangeable with SCTE-35. Unknown ANC needs a configurable DID/SDID filter
and an explicit carriage route; unsupported paths must surface a blocker.

## Native SDI implementation

1. Enumerate devices, input/output interfaces, subdevices, supported modes,
   VANC/10-bit constraints and persistent IDs using the DeckLink SDK.
2. Explicitly select SDI, mode and pixel format. Start with 10-bit YUV capture
   for legacy ANC compatibility. Do not assume Duo and Duo 2 connector mappings
   or capabilities are identical. Do not switch a live port's configuration
   as a side effect of a browser page load.
3. Query `IDeckLinkVideoFrameAncillaryPackets`; copy each packet's bytes,
   DID/SDID, line, data stream and containing frame timestamp while the frame
   is valid. Preserve frame reference lifetimes for picture/audio as well.
4. Decode caption CDPs; validate identifier, length, sequence and checksum.
   Preserve complete 708 services, including compatibility 608 data. Rebuild
   CDPs at output cadence if frame conversion requires it.
5. Reassemble fragmented ST 2010 messages before SCTE-104 parsing; reject
   incomplete or invalid messages. Do not treat every ANC payload as a whole
   SCTE-104 message. The current diagnostic intentionally records raw payloads.
6. On playout, attach correctly formatted packets to output frames and use
   scheduled video/audio output with shared clocking, bounded queues, preroll,
   underrun metrics and signal-loss handling. Unknown ANC may pass where valid,
   captions may be removed/replaced, SCTE may be removed/translated, or all VANC
   may be stripped. The policy core already handles independent removal.
7. Legacy GetAncillaryData/VANC-line handling is a fallback if a card or driver
   cannot provide the packet interface. Test rather than infer compatibility.

## SCTE conversion and serial events

Use one validated cue model containing source identity, event IDs, command type,
destination/program information, source clock epoch, target PTS, pre-roll,
duration, cancellation, immediate/normal behavior, unique program ID, avail
number/count and segmentation descriptors where present.

104→35 mapping must support a declared subset, starting with splice requests:
out/in, normal/immediate, cancel, duration and auto-return. Time-signal and
segmentation descriptors follow. Unsupported operations produce an explicit
diagnostic, not a guessed cue. Reverse mapping is only defined for supported
35 commands and descriptors; it cannot be universally lossless.

SCTE-35 must be inserted with a valid CRC, correct section length, PMT stream
signaling and PID allocation, and a PTS matching the OUTPUT program clock.
If encoding or recaptioning delays video, translate the cue timeline and
pre-roll accordingly. Preserve cue cancellation and event IDs across repeated
messages. Account for 33-bit wrap, discontinuities and output clock resets.

Serial is an event sink alongside stream conversion. Rules select source,
cue action, program/avail/segmentation filters, channel, pulse length and
whether to fire at cue receipt or the scheduled splice point. Keep those two
timing choices explicit. Normal cues need a program-clock scheduler; do not
use arrival time as a substitute for splice time. Cancel removes pending work.

Bench protocol: `HELLO` → `SPANKVANC 1 4`;
`PULSE <sequence> <channel> <duration_ms>` → `ACK <sequence>` or `DUP <sequence>`.
Retry the same sequence on an ACK timeout. The host must deduplicate repeated
cue deliveries, negotiate startup, and never replay historical events on
reconnection. Firmware retains a bounded history of 64 sequences and drives
nonblocking pulses that return to inactive automatically. GPIO is 3.3V logic;
a dry-contact GPO requires an appropriate isolated relay/interface. Board pin
mapping/polarity needs verification, especially beyond the original ESP32.

The current code provides the event contract, deduplication/clock arithmetic,
message builder and firmware only. It does not yet parse, schedule or dispatch
live cues to a serial device. Firmware is provided as source and has not been
compiled with Arduino toolchains or electrically tested.

## Caption pass, strip and recaption

Caption policy is independent for each output: pass, strip, or replace using
audioWhisper. Strip removes actual embedded caption payloads, not every H.264
SEI message. It also excludes separate subtitle streams and corresponding
signaling. It cannot remove captions already burned into picture pixels.

Preserve service/language, 608 field/channel and 708 packet sequence continuity.
When changing policies at a controlled restart, clear stale decoder state so
old captions do not remain on receivers. Test caption availability signaling,
late joins, roll-up/pop-on, multi-service input and interlaced field cadence.

audioWhisper must consume PCM extracted from the selected input program/channel,
not an unrelated system microphone or stereo mix. Reuse the existing Whisper
transcription/caption formatting knowledge through an adapter with timestamped
PCM and returned caption events. Do not modify the user's existing scripts.

The adapter must preserve sample timestamps, use overlapping chunks/VAD with
deduplication, suppress silence hallucinations, and schedule readable caption
lines. The A/V delay buffer must cover chunk completion, inference and caption
delivery, and delay both audio and video on the same timeline. Bound the buffer
and recognition queue; expose late captions and overload instead of accumulating
unbounded delay. Configured delay is a target until measured on work hardware.
Select transcribe vs translation explicitly; default to same-language captions.
Retain complete 708 support as a goal; the reused local text encoder is currently
608 CC1 with printable ASCII, not a complete multilingual 708 text encoder.

## Implementation sequence / acceptance

1. **Foundation (this checkout):** local UI, saved routes, diagnostics, capability
   gates, independent output policies, real IP caption fixture tests, raw SDK
   extraction diagnostic, ANC filtering and serial protocol/firmware source.
2. **Hardware bench:** build on work PC, enumerate Duo/Mini Recorder, prove
   raw caption/SCTE extraction with a known signal; store short ANC captures.
   Confirm actual driver/card compatibility and add fallback if required.
3. **SDI bridge:** native capture and scheduled SDI output, original A/V and
   caption/SCTE/unknown ANC pass-through, targeted strip and all-VANC strip.
   Validate line placement, A/V sync, field cadence and long-run clock behavior.
4. **Cue bridge:** supported 104↔35 conversion, TS PMT/PID insertion/removal,
   duplicate/cancel/discontinuity handling, serial handshake and scheduler.
   Verify output with an independent analyzer and GPIO with a logic analyzer.
5. **Recaption:** timestamped source audio → audioWhisper → caption encoder,
   synchronized bounded delay; test known speech and silence with output
   timing measurements and receiver caption decoding.
6. **Distribution:** full UDP/SRT/RTMP/SDI route matrix, receiving player checks,
   private YouTube test, Windows native SDK adapter/builds and packaging.

Each milestone needs receiver-side validation. A successful FFmpeg exit, SDK
compile or visible UI setting is not proof that metadata survived the chain.

## Control service and packaging

The local-only Sites workflow is appropriate here: the Python backend needs
local PCIe hardware, media sockets and serial ports. Cloud-hosting a control
panel would not provide those capabilities. This checkout is not published.
The service binds to loopback with host/origin validation and a per-process
control token. Remote access needs explicit authentication and deployment work.
Linux is tested locally; Windows Python source portability and eventual native
SDK/COM builds are separate validation steps. The source bundle excludes local
runtime configuration, keys, build products, SDK files and Python environments.
