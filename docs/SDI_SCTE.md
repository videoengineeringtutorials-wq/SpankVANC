# Manual output cues — 0.13.0

Select **Manual SCTE-104** on a DeckLink output or **Manual SCTE-35** on UDP,
SRT or a TS file output. Save and start the route, enter the break duration,
and press **Start break**. Press **End break** to return to program. RTMP and
YouTube have no manual SCTE option. Controls target one output; source monitoring
and other output policies are independent. Manual mode replaces incoming SCTE
on that destination, rather than combining source and manual events.

Cues are immediate program `splice_insert` messages. Start carries a duration
in 0.1-second steps (0.1–6553.5 seconds); `auto_return` is false, so the operator
must press End even after that duration. End uses the same event ID. Duplicate
Start and unmatched End requests are rejected. The API reports **queued**, not
receiver acknowledgement. Engine logs report emission separately. A fresh private
journal is created for each manual output on each route start, so old cues are
never replayed. No cue is injected on the input or standalone source monitor.

The matching local engine must be rebuilt with `patch_ffmpeg_manual_scte.py`
(the normal Windows build script runs it). Preflight blocks manual output on an
older engine. TS uses a dedicated PID `0x1FFE`, PMT stream type `0x86`, program
CUEI registration and cue_identifier descriptor. SDI converts through the existing
checked SCTE-35 → 104 converter and emits ST 2010 on VANC line 13. No changes to
DeckLink drivers, profiles or other captioning applications are required.

Initial manual-cue verification: 101 unit/media tests; browser cue controls and SRT mode
persistence; Windows cross-compilation of both muxers; live Windows engine under
Wine with two cues emitted exactly once on one of three TS outputs, valid
section/PMT CRCs and 100 retained video frames on every output. Codec round trips
verify manual start/end conversion to 104. Physical SCTE-104 receiver confirmation
remains pending. That initial verification did not deploy or run anything on the remote workstation;
0.13.0 combines this work with native 708 output (see `PROJECT_HANDOFF.md`).

## SRT connection modes

Input and output SRT controls now expose **Caller**, **Listener**, and
**Rendezvous**. Older URLs containing `mode=` retain their setting when loaded;
an explicit selector choice overrides that URL option. Other query options,
including streamid, passphrase, latency, localip and localport, are retained.
Caller connects to a peer; Listener binds a local address such as
`srt://0.0.0.0:9000`; Rendezvous specifies the peer address plus appropriate
`localip`/`localport` URL options. Both peers need compatible configuration and
network reachability. These connection roles are independent of media direction.
See [FFmpeg's SRT options](https://ffmpeg.org/ffmpeg-protocols.html#srt).

## Caption packaging clarification

Generated speech captions are CEA-608 CC1. They occupy the 608 compatibility
slots in A/53 / CTA-708 caption transport, with field-2 nulls and invalid 708
padding. H.264 carries the A/53 data in SEI; MPEG-2 uses user data; SDI wraps
caption tuples in CDP/VANC. This compatibility carriage alone does **not** generate a separate native
CEA-708 DTVCC service. Starting with 0.13.0, replacement outputs can additionally
generate native Service 1 by choosing 708 or 608 + 708; see `WHISPER.md`. Caption pass mode retains decoded source 608/708 tuples, including
native 708 when present, subject to source decoder/receiver support.

---

# SCTE on DeckLink SDI outputs (0.8.0)

Rebuild the local Extended engine with 0.8.0 build support. Configure the selected
connector for output in Desktop Video Setup. Caption and SCTE choices are
independent on every output. The source video format must be supported by the
selected DeckLink output; conversion does not resize or change frame rate.

## SDI input: Pass SCTE-104

Choose DeckLink input/device/mode and a different DeckLink output port. Select
**Pass SCTE-104** for SCTE signaling. Original DID 0x41 / SDID 0x07 payload bytes,
frame association and VANC line are retained, including ST 2010 fragments and
repeat flags. This path does not interpret or convert cue commands. It supports
primary SDI data stream 0. Unsupported stream indices, line/packet limits or
VANC emission failures stop the route rather than silently discarding signaling.
Arbitrary non-SCTE ANC is not preserved. Captions can independently pass or strip.

## TS input: Convert SCTE-35 to SCTE-104

Choose UDP, SRT or a TS file as input, select a DeckLink output, then choose
**Convert 35 → 104**. Set the optional **SCTE-35 PID** when the cue PID is not the
first data stream. Decimal or `0x` hexadecimal notation is accepted. An explicit
PID must exist and carry SCTE-35. Auto mode maps the first data stream if present;
a transport without a cue stream carries A/V without generating triggers. Use a
single-program TS, or select the cue PID belonging to the first video/audio
program selected by the route.

Supported commands are program splice_insert start/end/cancel (normal and
immediate), time_signal with specified time, and splice_null. Raw descriptor
bytes are carried in insert_descriptor_request_data (0x0108). SCTE-104 MOMs use
time_type 0 and ST 2010 on VANC line 13, with subsequent fragments on following
lines of the same frame.

The TS PTS clock is retained. pts_adjustment and 33-bit wrap are applied before
calculating pre-roll from the actual containing output video frame. Pre-roll is
rounded to the nearest millisecond and must fit 0..65535 ms. Break duration must
fit SCTE-104's exact 0.1-second units and 16-bit field. Duplicate non-null sections
are suppressed within a five-second source-clock window.

Encrypted sections, non-default tiers, component splices, unspecified splice
times, unsupported commands, late targets, invalid lengths/CRC, oversized messages
and unrepresentable duration/pre-roll are rejected. Choose **Continue A/V** to
warn and discard rejected cues, or **Stop route** for strict rejection. Rejections
are shown in the log and saved under `runtime/scte-rejections.ndjson`. A transport
demuxer can reject corrupt TS sections before conversion receives them.

Test with a downstream SDI/SCTE analyzer before using these triggers operationally.
Native Windows codec/VANC tests and application preflight do not verify reception
by the external trigger receiver.
