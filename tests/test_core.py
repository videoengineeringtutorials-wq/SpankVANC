import copy
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer

from spankvanc.engine import ConfigError, DEFAULT, command, plan, scrub, scte_options, validate
from license_fixture import LicensedEngine as Engine
from spankvanc.events import Cue, Deduplicator, pts_distance, serial_pulse
from spankvanc.server import make_handler


CAP = {"ffmpeg": "/usr/bin/ffmpeg", "srt": True, "rtmp": True,
       "libx264": True, "mpeg2video": True, "aac": True, "youtube_profiles": {"general": True, "decklink": True}}


def route():
    cfg = copy.deepcopy(DEFAULT)
    cfg["input"] = {"kind": "file", "address": "input.ts", "realtime": False}
    cfg["outputs"][0].update(kind="file", address="output.ts", scte="strip")
    return cfg


class RouteTests(unittest.TestCase):
    def test_no_silent_scte_or_recaption_loss(self):
        for key, value in (("scte", "pass"), ("captions", "recaption")):
            cfg = route()
            cfg["outputs"][0][key] = value
            self.assertFalse(plan(cfg, CAP)["ready"])
        cfg = route()
        cfg["gpo"]["enabled"] = True
        self.assertFalse(plan(cfg, CAP)["ready"])

    def test_scte_carriage_matrix(self):
        pairs = [("decklink", "decklink", {"pass", "strip"})]
        for ts in ("udp", "srt", "file"):
            pairs += [("decklink", ts, {"convert", "strip"}),
                      (ts, "decklink", {"convert", "strip"})]
            for other in ("udp", "srt", "file"):
                pairs.append((ts, other, {"pass", "strip"}))
        for source, destination, allowed in pairs:
            with self.subTest(source=source, destination=destination):
                self.assertEqual(set(scte_options(source, destination)), allowed)
                for policy in ("pass", "strip", "convert"):
                    cfg = route()
                    cfg["input"].update(kind=source, address="")
                    cfg["outputs"][0].update(kind=destination, address="", scte=policy)
                    cfg["outputs"][0]["video_codec"] = "uncompressed" if destination == "decklink" else "h264"
                    if policy in allowed:
                        validate(cfg)
                    else:
                        with self.assertRaises(ConfigError): validate(cfg)
        self.assertEqual(scte_options("decklink", "udp")["convert"], "Convert 104 → 35")
        self.assertEqual(scte_options("srt", "decklink")["convert"], "Convert 35 → 104")
        for source, destination in (("rtmp", "decklink"), ("udp", "rtmp"), ("decklink", "youtube")):
            self.assertEqual(set(scte_options(source, destination)), {"strip"})

    def test_video_codec_validation_and_capabilities(self):
        for kind in ("udp", "srt", "file"):
            for codec in ("h264", "mpeg2video"):
                cfg = route()
                cfg["outputs"][0].update(kind=kind, address="", video_codec=codec)
                self.assertEqual(validate(cfg)["outputs"][0]["video_codec"], codec)
        for kind in ("rtmp", "youtube"):
            cfg = route()
            cfg["outputs"][0].update(kind=kind, address="", video_codec="mpeg2video")
            with self.assertRaises(ConfigError): validate(cfg)
        cfg = route()
        cfg["outputs"][0]["video_codec"] = "mpeg2video"
        self.assertTrue(plan(cfg, dict(CAP, libx264=False))["ready"])
        self.assertFalse(plan(cfg, dict(CAP, mpeg2video=False))["ready"])
        self.assertFalse(plan(cfg, dict(CAP, aac=False))["ready"])
        args = command(validate(cfg))
        self.assertNotIn("-crf", args)
        self.assertNotIn("-preset", args)
        self.assertIn("mpeg2video", args)
        self.assertIn("aac_low", args)
        self.assertIn("-latm", args)
        self.assertEqual(plan(cfg, CAP)["outputs"][0]["audio_framing"], "ADTS")
        cfg["outputs"][0].pop("video_codec")
        self.assertEqual(validate(cfg)["outputs"][0]["video_codec"], "h264")

    def test_output_policies_are_independent(self):
        cfg = route()
        cfg["outputs"].append(dict(cfg["outputs"][0], name="Clean", address="clean.ts", captions="strip"))
        args = command(validate(cfg))
        self.assertEqual(args.count("-i"), 1)
        self.assertEqual(args.count("-a53cc"), 2)
        self.assertEqual(args[args.index("-a53cc") + 1], "1")
        self.assertIn("sidedata=mode=delete:type=A53_CC", args)
        self.assertTrue(plan(cfg, CAP)["ready"])

    def test_refuses_overwrite_and_invalid_transport(self):
        cfg = route()
        cfg["outputs"][0]["address"] = "input.ts"
        self.assertFalse(plan(cfg, CAP)["ready"])
        cfg["input"].update(kind="srt", address="rtmp://example.com/live")
        with self.assertRaises(ConfigError): validate(cfg)
        for invalid in (True, -1, 10001, 1.5):
            cfg = route(); cfg["gpo"]["pulse_ms"] = invalid
            with self.assertRaises(ConfigError): validate(cfg)

    def test_keys_are_hidden_in_logs_and_plan(self):
        cfg = route()
        cfg["outputs"][0].update(kind="youtube", address="rtmps://example.com/live/SECRET")
        self.assertNotIn("SECRET", json.dumps(plan(cfg, CAP)))
        self.assertNotIn("SECRET", scrub("Failed rtmps://example.com/live/SECRET error"))

    def test_save_round_trip(self):
        with tempfile.TemporaryDirectory() as temp:
            engine = Engine(Path(temp))
            engine.save(route())
            self.assertEqual(Engine(Path(temp)).config, validate(route()))


class CueTests(unittest.TestCase):
    def test_repeats_cancel_and_clock_wrap(self):
        now = [0]
        dedupe = Deduplicator(ttl=5, clock=lambda:now[0])
        out = Cue("input1", 123, "out", 90000)
        self.assertTrue(dedupe.accept(out))
        self.assertFalse(dedupe.accept(out))
        self.assertTrue(dedupe.accept(Cue("input1", 123, "in", 90000)))
        self.assertTrue(dedupe.accept(Cue("input2", 123, "out", 90000)))
        now[0] = 6
        self.assertTrue(dedupe.accept(out))
        self.assertEqual(pts_distance(50, (1 << 33) - 50), 100)
        self.assertEqual(pts_distance((1 << 33) - 50, 50), -100)

    def test_gpo_wire_format(self):
        self.assertEqual(serial_pulse(42, 2, 250), b"PULSE 42 2 250\n")
        with self.assertRaises(ConfigError): serial_pulse(0, 2, 250)
        with self.assertRaises(ConfigError): Cue("input", 1, "unknown", None)


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = Engine(Path(self.temp.name))
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.engine, "test-token", 0))
        self.port = self.server.server_port
        self.server.RequestHandlerClass = make_handler(self.engine, "test-token", self.port)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        self.temp.cleanup()

    def request(self, method, path, data=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port)
        connection.request(method, path, body=json.dumps(data) if data is not None else None, headers=headers or {})
        response = connection.getresponse()
        status, body = response.status, response.read()
        connection.close()
        return status, body

    def test_control_and_local_ui(self):
        status, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"SpankVANC", body)
        self.assertNotIn(b"__CONTROL_TOKEN__", body)
        self.assertEqual(self.request("GET", "/api/state")[0], 403)
        self.assertEqual(self.request("GET", "/api/monitor")[0], 403)
        self.assertEqual(self.request("POST", "/api/license/activate", {"key":"dummy"})[0], 403)
        self.assertEqual(self.request("POST", "/api/license/check", {})[0], 403)
        headers = {"X-SpankVANC-Token":"test-token"}
        status, body = self.request("GET", "/api/monitor", headers=headers)
        self.assertEqual(status, 200)
        self.engine.source_monitor.feed({"signal":True,"pts90k":0,"cc":"fc9429fcc849"})
        status, body = self.request("GET", "/api/monitor", headers=headers)
        self.assertEqual(json.loads(body)["monitor"]["services"]["CC1"], "HI")
        self.assertEqual(self.request("POST", "/api/save", route(), headers)[0], 200)
        status, body = self.request("GET", "/api/state", headers=headers)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["config"]["input"]["address"], "input.ts")
        headers["Origin"] = "https://unrelated.example"
        self.assertEqual(self.request("POST", "/api/start", route(), headers)[0], 403)
        self.assertEqual(self.request("GET", "/", headers={"Host":"unrelated.example"})[0], 403)


if __name__ == "__main__": unittest.main()
