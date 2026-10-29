"""Loopback-only Python control service. No PHP or cloud dependency."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading

from .engine import ConfigError, Engine, plan, scrub


WEB = Path(__file__).parent / "web"


def make_handler(engine, token, port):
    class Handler(BaseHTTPRequestHandler):
        server_version = "SpankVANC/0.11.2"

        def authorized_host(self):
            return self.headers.get("Host") in (f"127.0.0.1:{port}", f"localhost:{port}")

        def reply(self, data, status=200, mime="application/json"):
            if mime == "application/json":
                data = json.dumps(data).encode()
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if not self.authorized_host():
                return self.reply({"error": "Invalid host"}, 403)
            if self.path in ("/api/state", "/api/monitor"):
                if not secrets.compare_digest(self.headers.get("X-SpankVANC-Token", ""), token):
                    return self.reply({"error": "Invalid control token"}, 403)
                return self.reply(engine.monitor_state() if self.path == "/api/monitor" else engine.state())
            files = {"/": ("index.html", "text/html; charset=utf-8"),
                     "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                     "/style.css": ("style.css", "text/css; charset=utf-8")}
            if self.path not in files:
                return self.reply({"error": "Not found"}, 404)
            filename, mime = files[self.path]
            data = (WEB / filename).read_bytes()
            if filename == "index.html":
                data = data.replace(b"__CONTROL_TOKEN__", token.encode())
            self.reply(data, mime=mime)

        def do_POST(self):
            if not self.authorized_host() or not secrets.compare_digest(self.headers.get("X-SpankVANC-Token", ""), token):
                return self.reply({"error": "Invalid control token"}, 403)
            if self.headers.get("Origin") not in (None, f"http://127.0.0.1:{port}", f"http://localhost:{port}"):
                return self.reply({"error": "Invalid origin"}, 403)
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 65536:
                    raise ConfigError("Request body must contain 1–65536 bytes")
                data = json.loads(self.rfile.read(length))
                if self.path == "/api/license/activate":
                    result = engine.activate_license(data["key"])
                elif self.path == "/api/license/check":
                    result = engine.check_license()
                elif self.path == "/api/monitor/start":
                    result = engine.monitor_start(data)
                elif self.path == "/api/monitor/stop":
                    result = engine.monitor_stop()
                elif self.path == "/api/devices":
                    result = engine.refresh_devices()
                elif self.path == "/api/plan":
                    engine.license.require()
                    result = plan(data, engine.capabilities)
                elif self.path == "/api/save":
                    engine.save(data)
                    result = engine.state()
                elif self.path == "/api/start":
                    result = engine.start(data)
                elif self.path == "/api/stop":
                    result = engine.stop()
                else:
                    return self.reply({"error": "Not found"}, 404)
                self.reply(result)
            except (ValueError, TypeError, KeyError, OSError) as exc:
                self.reply({"error": scrub(str(exc))}, 400)

        def log_message(self, fmt, *args):
            # Media URLs and saved configuration never enter the HTTP access log.
            pass

    return Handler


def serve(port, state_dir):
    if not 1 <= port <= 65535:
        raise ConfigError("Port must be between 1 and 65535")
    engine = Engine(state_dir)
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(engine, secrets.token_urlsafe(32), port))
    print(f"SpankVANC control panel: http://127.0.0.1:{port}", flush=True)
    print("Development preview. SCTE-104 program-splice conversion is available with the private build. SDI playout and live Whisper captions require the matching local engine.", flush=True)
    closing = threading.Event()
    def watch_license():
        while not closing.wait(1):
            engine.license_tick()
    watcher = threading.Thread(target=watch_license, daemon=True)
    watcher.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        closing.set()
        watcher.join(timeout=10)
        engine.stop()
        engine.monitor_stop()
        server.server_close()
