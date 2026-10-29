"""License screen activation, key privacy and live relocking in a real browser."""
import json
from pathlib import Path
import tempfile
import threading
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from playwright.sync_api import sync_playwright, expect
from spankvanc.engine import Engine
from spankvanc.licensing import LicenseClient
from spankvanc.server import make_handler
from test_licensing import OnlineFixture, KEY
from test_decklink import DeckLinkOutputTests

fixture = DeckLinkOutputTests(); fixture.setUp()
with tempfile.TemporaryDirectory() as folder, patch('spankvanc.engine.doctor', return_value=fixture.cap):
    online = OnlineFixture()
    license_client = LicenseClient(Path(folder)/'private/license.json', opener=online)
    engine = Engine(Path(folder)/'route', license_client=license_client)
    engine.config = fixture.cfg
    server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(engine, 'browser-token', 0))
    port = server.server_port; server.RequestHandlerClass = make_handler(engine, 'browser-token', port)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(); errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto(f'http://127.0.0.1:{port}')
            expect(page.locator('main')).to_be_hidden()
            expect(page.locator('#license-status')).to_contain_text('Enter a license key')
            expect(page.locator('#license-key')).to_have_attribute('type', 'password')
            page.locator('#license-key').fill(KEY)
            page.locator('#license-activate').click()
            expect(page.locator('#license-status')).to_contain_text('License active')
            expect(page.locator('main')).to_be_visible()
            expect(page.locator('#license-key')).to_have_value('')
            assert KEY not in json.dumps(engine.state())
            page.reload()
            expect(page.locator('main')).to_be_visible()
            expect(page.locator('#license-key')).to_have_value('')
            online.allowed = False
            page.locator('#license-check').click()
            expect(page.locator('#license-status')).to_contain_text('expired')
            expect(page.locator('main')).to_be_hidden()
            assert not errors, errors
            browser.close()
    finally:
        server.shutdown();server.server_close();thread.join()
print('License activation, hidden key and expiry relocking: PASS')
