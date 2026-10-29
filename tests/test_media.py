"""Actual encode/decode validation, with a synthetic caption-bearing source."""
import copy
import json
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import unittest

from spankvanc.engine import DEFAULT
from spankvanc.engine import Engine


ROOT = Path(__file__).resolve().parent.parent


def run(args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise AssertionError(result.stderr[-5000:])
    return result.stdout


def assert_adts(test, path, audio_pid):
    """Inspect the first AAC PES payload in the actual TS packets, without remuxing."""
    data = path.read_bytes()
    for offset in range(0, len(data), 188):
        packet = data[offset:offset + 188]
        if len(packet) != 188 or packet[0] != 0x47: continue
        pid = ((packet[1] & 0x1f) << 8) | packet[2]
        if pid != audio_pid or not packet[1] & 0x40: continue
        flags = (packet[3] >> 4) & 3
        if not flags & 1: continue
        start = 4 + (1 + packet[4] if flags & 2 else 0)
        pes = packet[start:]
        if len(pes) < 12 or pes[:3] != b'\x00\x00\x01': continue
        payload = pes[9 + pes[8]:]
        if len(payload) < 3: continue
        test.assertEqual((payload[0], payload[1] & 0xf6), (0xff, 0xf0), 'AAC must have ADTS framing')
        test.assertEqual(payload[2] >> 6, 1, 'ADTS profile must indicate AAC-LC')
        test.assertEqual((payload[2] >> 2) & 15, 3, '48 kHz sampling frequency index')
        return
    test.fail('No AAC ADTS PES payload found')


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe") and shutil.which("g++"), "FFmpeg and C++ compiler needed")
class MediaTests(unittest.TestCase):
    def test_embedded_caption_pass_and_strip(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            flags = run(["pkg-config", "--cflags", "--libs", "libavformat", "libavcodec", "libavutil"]).split()
            binary = root / "fixture"
            run(["g++", "-std=c++17", str(ROOT / "tests/caption_fixture.cpp"), *flags, "-o", str(binary)])
            raw = root / "raw.ts"
            run([str(binary), str(raw)])
            source = root / "input.ts"
            run(["ffmpeg", "-v", "error", "-i", str(raw), "-f", "lavfi", "-i", "sine=sample_rate=48000",
                 "-t", "3", "-c:v", "copy", "-c:a", "aac", str(source)])
            cfg = copy.deepcopy(DEFAULT)
            cfg["input"] = {"kind":"file", "address":str(source), "realtime":False}
            cases = [(name + '_' + codec, policy, codec) for codec in ('h264', 'mpeg2video')
                     for name,policy in (("captioned","pass"),("clean","strip"))]
            cfg["outputs"] = [dict(name=name, kind="file", address=str(root / (name + ".ts")),
                                   captions=policy, scte="strip", video_codec=codec, enabled=True)
                              for name,policy,codec in cases]
            engine = Engine(root / "state")
            self.assertTrue(engine.start(cfg)["running"])
            limit = time.monotonic() + 30
            while engine.state()["running"] and time.monotonic() < limit:
                time.sleep(.05)
            engine.stop()
            self.assertEqual(engine.process.returncode, 0, "\n".join(engine.state()["logs"]))
            counts = {}
            for name in ("input", *(case[0] for case in cases)):
                data = json.loads(run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_frames", "-of", "json", str(root / (name + ".ts"))]))
                counts[name] = sum(any("Closed Captions" in item.get("side_data_type", "") for item in frame.get("side_data_list", [])) for frame in data["frames"])
                self.assertEqual(len(data["frames"]), 75)
            self.assertGreater(counts["input"], 0)
            # Independent caption decoder must recover the actual words, not
            # merely see an empty or malformed side-data container.
            for name,policy,codec in cases:
                path = root / (name + '.ts')
                self.assertGreater(counts[name], 0) if policy == 'pass' else self.assertEqual(counts[name], 0)
                streams = json.loads(run(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(path)]))['streams']
                self.assertEqual([s['codec_name'] for s in streams], [codec, 'aac'])
                assert_adts(self, path, int(streams[1]['id'], 16))
                if policy == 'pass':
                    decoded = run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                                   f"movie={path}[out0+subcc]", "-map", "0:s:0", "-f", "srt", "-"])
                    self.assertIn("SPANKVANC CAPTION TEST", decoded)
            print("Synthetic source / passed / stripped caption frame counts:", counts)

    def test_loopback_udp_srt_rtmp_outputs(self):
        protocols = run(["ffmpeg", "-hide_banner", "-protocols"]).split()
        if "srt" not in protocols:
            self.skipTest("FFmpeg needs SRT for loopback transport test")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            # Include real video and audio; this test validates transport and
            # muxing. The separate fixture test validates actual caption words.
            source = root / "source.ts"
            run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=25",
                 "-f", "lavfi", "-i", "sine=sample_rate=48000", "-t", "4", "-threads:v", "2",
                 "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(source)])
            def free_port(kind):
                with socket.socket(socket.AF_INET, kind) as reservation:
                    reservation.bind(("127.0.0.1", 0))
                    return reservation.getsockname()[1]
            udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp.bind(("127.0.0.1", 0)); udp.settimeout(.1)
            udp_port = udp.getsockname()[1]
            srt_port = free_port(socket.SOCK_DGRAM)
            rtmp_port = free_port(socket.SOCK_STREAM)
            srt_listener = f"srt://127.0.0.1:{srt_port}?mode=listener&latency=100000"
            srt_caller = f"srt://127.0.0.1:{srt_port}?mode=caller&latency=100000"
            rtmp_url = f"rtmp://127.0.0.1:{rtmp_port}/live/test"
            children = []
            received = bytearray()
            done = threading.Event()
            def collect():
                while not done.is_set():
                    try: received.extend(udp.recv(65536))
                    except socket.timeout: pass
            reader = threading.Thread(target=collect, daemon=True); reader.start()
            engine = Engine(root / "state")
            try:
                for name, url, options, fmt in (("srt",srt_listener,[],"mpegts"), ("rtmp",rtmp_url,["-listen","1"],"flv")):
                    children.append(subprocess.Popen(["ffmpeg", "-v", "error", "-nostdin", "-analyzeduration", "2000000", "-probesize", "1048576",
                                                       *options, "-i", url, "-map", "0:v:0", "-map", "0:a:0", "-c", "copy", "-f", fmt,
                                                       str(root / (name + ".capture"))], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE))
                time.sleep(.3)
                cfg = copy.deepcopy(DEFAULT)
                cfg["input"] = {"kind":"file", "address":str(source), "realtime":True}
                cfg["outputs"] = [dict(name=kind,kind=kind,address=url,captions="pass",scte="strip",enabled=True)
                                  for kind,url in (("udp",f"udp://127.0.0.1:{udp_port}?pkt_size=1316"),("srt",srt_caller),("rtmp",rtmp_url))]
                cfg['outputs'][0]['video_codec'] = 'mpeg2video'
                engine.start(cfg)
                engine.process.wait(timeout=20)
                time.sleep(.3)
                done.set(); reader.join(timeout=2); udp.close()
                (root / "udp.capture").write_bytes(received)
                receiver_logs = []
                for child in children:
                    try: _, errors = child.communicate(timeout=5)
                    except subprocess.TimeoutExpired:
                        child.terminate(); _, errors = child.communicate(timeout=5)
                    receiver_logs.append(errors.decode(errors="replace"))
                messages = "\n".join(engine.state()["logs"]) + "\nRECEIVERS:\n" + "\n".join(receiver_logs)
                self.assertEqual(engine.process.returncode, 0, messages)
                for kind in ("udp", "srt", "rtmp"):
                    data = json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(root / (kind + ".capture"))]))
                    self.assertEqual([s["codec_name"] for s in data["streams"]], ["mpeg2video" if kind == 'udp' else "h264","aac"], kind)
                    run(["ffmpeg", "-v", "error", "-i", str(root / (kind + ".capture")),
                         "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "-"])
                print("UDP MPEG-2/AAC, SRT H.264/AAC and RTMP H.264/AAC loopback outputs decoded successfully")
            finally:
                engine.stop(); done.set(); reader.join(timeout=2); udp.close()
                for child in children:
                    if child.poll() is None: child.terminate()
                    child.communicate(timeout=5)


if __name__ == "__main__": unittest.main()
