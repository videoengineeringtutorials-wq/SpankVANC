"""Use the real engine and web UI without activation or licensing network calls."""
import tempfile
import threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from playwright.sync_api import sync_playwright, expect
from spankvanc.engine import Engine
from spankvanc.server import make_handler
from test_core import CAP, route

with tempfile.TemporaryDirectory() as folder, patch('spankvanc.engine.doctor', return_value=CAP), patch('urllib.request.urlopen', side_effect=OSError('Offline')) as network:
    engine = Engine(Path(folder)); engine.config = route()
    server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(engine, 'test', 0))
    port = server.server_port; server.RequestHandlerClass = make_handler(engine, 'test', port)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(); errors = []; requests = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.on('request', lambda r: requests.append(r.url))
            page.goto(f'http://127.0.0.1:{port}')
            expect(page.locator('#license-panel')).to_have_count(0)
            expect(page.locator('main')).to_be_visible()
            expect(page.locator('#route-status')).to_have_text('Engine idle')
            expect(page.locator('#start')).to_be_enabled()
            expect(page.locator('#ready-tag')).to_have_text('READY')
            page.locator('#save').click()
            expect(page.locator('#notice')).to_have_text('Route saved locally.')
            page.reload()
            expect(page.locator('#ready-tag')).to_have_text('READY')
            assert not errors, errors
            assert all(url.startswith(f'http://127.0.0.1:{port}/') for url in requests), requests
            network.assert_not_called()
            browser.close()
        print('Activation-free startup, visible controls, offline save/reload and no external requests: PASS')
    finally:
        server.shutdown(); server.server_close()
