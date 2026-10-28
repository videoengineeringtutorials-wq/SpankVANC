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
