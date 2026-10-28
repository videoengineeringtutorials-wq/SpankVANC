# UDP transport-stream diagnosis

UDP outputs default to **1316 bytes per datagram** (seven 188-byte TS packets).
Entering `udp://239.225.0.1:59000` now adds `?pkt_size=1316` automatically.
Explicit sizes must be a positive multiple of 188, at most 1316. Do not use
1472 for TS-over-UDP: datagram boundaries may split TS packets, and a receiver
that resynchronizes each datagram can discard or misinterpret the fragments.
The [FFmpeg UDP protocol documentation](https://ffmpeg.org/ffmpeg-protocols.html#udp)
describes the packet-size option. Existing valid query parameters are preserved.

## Interpreting the reported analysis

The user's report correctly references SCTE-35 PID 0x0102 in PMT 0x1000 alongside
video 0x0100 and audio 0x0101. It also reports 453 largely single-packet unknown
PIDs, transport-error bits and very large A/V continuity errors. Random-looking
scrambled flags and PCRs on one-packet PIDs suggest damaged/misaligned data, not
hundreds of intentional ancillary streams. The user confirmed the size option was omitted on the same-PC sender/receiver.
A Windows-binary reproduction under Wine produced unaligned datagrams up to
1472 bytes without the option; the 1316-byte run had no packet-integrity errors.
This confirms a framing defect in the omitted-option configuration, while mixed senders, loss, capture/receiver problems or a mux defect still
need to be excluded with raw samples. A report alone does not establish where
the corruption occurred. Its derived bitrate/duration and cue preroll should
not be treated as trustworthy while the packet/clock data are inconsistent.

Use one sender for the multicast group/port and select the intended NIC when
multiple adapters are present. Compare a concurrent local TS recording with a
raw receiver capture, without remuxing or filtering. If the local file is clean
and UDP is damaged, investigate datagram sizing, socket buffering, interface
selection and the network. Do not filter unknown PIDs merely to hide the errors.

The user's analyzer command is suitable:

```powershell
tsp -I ip 239.225.0.1:59000 -P splicemonitor --all-commands -P analyze -O drop
```

To save the exact received TS packets instead, start a short test and stop with
Ctrl+C after about 30 seconds (choose a new capture filename):

```powershell
tsp -I ip 239.225.0.1:59000 -O file received-test.ts
tsanalyze received-test.ts
```

Receiver files and packet captures may contain broadcast content. Inspect and
share only what is needed for diagnosis; they are excluded from Git. Include
sender destination options, OS/driver/FFmpeg version, receiver command and
whether sender/receiver run on the same machine.

For repeatable development verification on loopback:

```bash
python3 tools/verify_udp.py --output-dir build/udp-check
```

Optional `--input` accepts a SCTE-bearing TS fixture; `--ffmpeg` and `--wine`
exercise a Windows executable. The tool checks raw datagram lengths, sync,
headers, continuity, PMT references and decoded SCTE sections. A clean loopback
test is not a substitute for testing the actual multicast network.
