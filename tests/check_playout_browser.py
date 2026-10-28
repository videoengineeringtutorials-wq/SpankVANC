"""Isolated SDI port/policy UI persistence check with simulated capabilities."""
import tempfile
import threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from playwright.sync_api import sync_playwright, expect
from spankvanc.engine import Engine
from spankvanc.server import make_handler
from test_decklink import DeckLinkOutputTests

fixture = DeckLinkOutputTests(); fixture.setUp()
fixture.cap.update(decklink_scte_output=True,decklink_options=["spankvanc_scte104"],recaption_decklink=True,recaption_runtime=True,whisper={"available":True,"cuda":True,"models":["small.en","turbo"]})
with tempfile.TemporaryDirectory() as folder, patch('spankvanc.engine.doctor', return_value=fixture.cap):
    engine = Engine(Path(folder)); engine.config = fixture.cfg
    server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(engine, 'test', 0))
    port = server.server_port; server.RequestHandlerClass = make_handler(engine, 'test', port)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(); errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto(f'http://127.0.0.1:{port}')
            pick = page.locator('[data-field="decklink_output"]')
            expect(pick).to_have_value('DeckLink Duo (2)')
            expect(page.locator('#ready-tag')).to_have_text('READY')
            page.locator('[data-field="captions"]').select_option('strip')
            page.locator('#save').click()
            expect(page.locator('#notice')).to_have_text('Route saved locally.')
            page.reload()
            expect(pick).to_have_value('DeckLink Duo (2)')
            expect(page.locator('[data-field="captions"]')).to_have_value('strip')
            page.locator('#refresh-devices').click()
            expect(page.locator('#notice')).to_have_text('Device list refreshed.')
            expect(pick).to_have_value('DeckLink Duo (2)')
            page.locator('[data-field="scte"]').select_option('pass')
            page.locator('#validate').click()
            expect(page.locator('#ready-tag')).to_have_text('READY')
            page.locator('#input-kind').select_option('file')
            page.locator('#input-address').fill('source.ts')
            page.locator('#scte-pid').fill('0x1ffe')
            page.locator('[data-field="scte"]').select_option('convert')
            page.locator('#scte-error-policy').select_option('stop')
            page.locator('#save').click()
            expect(page.locator('#notice')).to_have_text('Route saved locally.')
            page.reload()
            expect(page.locator('#scte-pid')).to_have_value('8190')
            expect(page.locator('[data-field="scte"]')).to_have_value('convert')
            expect(page.locator('#scte-error-policy')).to_have_value('stop')
            expect(page.locator('#ready-tag')).to_have_text('READY')
            page.locator('[data-field="captions"]').select_option('recaption')
            page.locator('#whisper-device').select_option('cuda')
            page.locator('#whisper-model').select_option('turbo')
            page.locator('#whisper-channel').fill('2')
            page.locator('#save').click()
            expect(page.locator('#notice')).to_have_text('Route saved locally.')
            page.reload()
            expect(page.locator('[data-field="captions"]')).to_have_value('recaption')
            expect(page.locator('#whisper-device')).to_have_value('cuda')
            expect(page.locator('#whisper-model')).to_have_value('turbo')
            expect(page.locator('#whisper-channel')).to_have_value('2')
            expect(page.locator('#ready-tag')).to_have_text('READY')
            assert not errors, errors
            browser.close()
        print('DeckLink output selector, caption policy, save/reload and refresh: PASS')
    finally:
        server.shutdown(); server.server_close()
