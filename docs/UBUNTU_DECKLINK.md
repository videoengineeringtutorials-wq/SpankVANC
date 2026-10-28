# Ubuntu DeckLink input

The browser panel can select a detected Blackmagic capture device and its SDI
mode, then route video and embedded stereo audio to the existing IP/file outputs.
The Mini Recorder is capture-only: SDI output remains unavailable.

## Prepare

Install Blackmagic Desktop Video and the Linux SDK. Build the native diagnostic
as documented in the main README; it supplies device names and supported modes.
Python 3.11+, FFmpeg, CMake, g++, make, pkg-config, curl, tar and dpkg-deb are needed.

Build a separate DeckLink-enabled FFmpeg (no sudo, no system replacement):

```bash
bash tools/build_decklink_ffmpeg.sh "$HOME/DeckLinkSDK/Linux/include"
```

This Ubuntu-specific helper downloads development packages, extracts them only
inside `build/`, and links against already installed Ubuntu runtime libraries
(libx264, libsrt-gnutls, libssl and libcrypto). It requires working Ubuntu package
indexes and matching runtime packages. The helper pins an FFmpeg source revision
that supports the SDK 14.3+ compatibility interfaces, then applies the included
legacy 608 ANC fallback, monitor telemetry, SCTE-104 decoder and SCTE-35 section mux. This local-use binary uses `--enable-nonfree` and is unredistributable; retain it
locally and follow upstream licensing when considering any redistribution.

The build writes `build/ffmpeg-decklink/bin/ffmpeg`. Other input types continue
using the system FFmpeg. Override paths with `SPANKVANC_DECKLINK_FFMPEG`,
`SPANKVANC_DECKLINK_DIAGNOSTIC`, or `SPANKVANC_FFMPEG` as needed.

Restart the control service after building to refresh capability detection:

```bash
systemctl --user restart spankvanc
```

## In the browser

Open http://127.0.0.1:8877 on the Ubuntu desktop. For access from another computer,
forward local port 8877 to remote 127.0.0.1:8877 using SSH. The service and control
token continue to require a loopback Host; do not expose it by changing its bind.

1. Select **Blackmagic DeckLink · SDI** as the input type.
2. Choose the capture device, then its matching mode. For the tested source,
   choose **DeckLink Mini Recorder**, **1080i59.94 · Hi59**.
3. Configure a local MPEG-TS file or an authorized UDP/SRT/RTMP destination.
4. Choose **Captions: Pass through** or **Strip**. For a TS output, select
   **SCTE: Convert 104 → 35** to carry converted cues, or **Strip SCTE-104** to discard
   them. RTMP/YouTube still have no SCTE carriage.
5. Leave recaptioning and serial triggers disabled. Check the route, then start.
6. Stop before changing devices or refreshing discovery. Another capture program
   must not own the same DeckLink input.

Caption data travels with the captured frame through FFmpeg's A/53 side data.
The patch adds ST 334-1 DID 0x61 / SDID 0x02 legacy 608 packets; upstream FFmpeg
handles CDP packets from VANC lines. Caption strip removes A/53 independently for
each output. Interlaced SDI modes retain interlaced encoding. Receiver testing is
required for each source, caption format and output codec. Signal loss is logged
by FFmpeg; there is no automatic input failover or broadcast continuity guarantee.

## Incoming-caption panel

Scroll to the bottom and click **Start source monitor** to observe the selected
SDI input without sending an output. A running DeckLink route supplies the same
panel automatically, even when its outputs strip captions. Starting a route
releases monitor-only capture and transfers the device to that route.

Select CC1–CC4. The screen displays decoded CEA-608 text, with a bounded history,
packet counters and source freshness. XDS is excluded from caption text. Native
708 triplets are counted but native 708 service text is not rendered yet. Empty
text can mean the selected service is absent; packet presence alone is not proof
of readable captions. Monitor text is held in memory, not written to a transcript.

## SCTE-104 → SCTE-35

The supported subset is multiple_operation_message with protocol version 0,
SCTE35_protocol_version 0 and timestamp time_type 0 (the containing source frame):

- 0x0101 program splice start/end, normal or immediate, cancellation, unique
  program/event IDs, pre-roll in milliseconds, duration in tenths of seconds,
  auto-return, avail number and expected count.
- 0x0102 splice_null and 0x0104 time_signal.
- 0x0108 prebuilt SCTE-35 descriptors; descriptor count and lengths are checked.
- Single-operation init/alive notifications are recognized as link management.

ST 2010 version-1 packets are reassembled within 1 second / 2000 bytes, with
bounded fragment count. Identical cues are suppressed for 5 seconds. Splice
targets use source-frame PTS plus pre-roll, modulo the 33-bit MPEG clock. Encoding
keeps source presentation timestamps, and the TS mux applies its output-clock
shift to pts_adjustment and recomputes CRC. Converted outputs get CUEI program
registration, stream_type 0x86, cue_identifier_descriptor and a separately
allocated PID. An internal heartbeat primes capture/probing and advances the data-stream
clock while idle; generated heartbeats are suppressed by the TS mux and are not
emitted as SCTE-35 sections. The PMT still advertises the cue PID. Explicit
splice_null requests received from the SDI source are converted and emitted. Strip outputs do not map that stream.

Unsupported operations, absolute UTC/VITC/GPI timestamps, malformed lengths or
orphan fragments fail conversion and stop the requested conversion route with
an engine-log error. Component mode, schedules, encryption, typed segmentation
requests (0x010B) and reverse conversion are unsupported. This is one input
program; there is no multi-program DPI destination routing.

SDI playout, serial cue dispatch and Whisper recaptioning remain blocked.
Selecting Strip explicitly discards cues; it does not preserve them.

The user service is enabled at login. Persisting it across logout/reboot without
a user login requires an administrator to enable linger for the account.
