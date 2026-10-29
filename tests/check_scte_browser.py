"""Isolated UI test: never changes the dashboard's live saved route."""
from http.server import ThreadingHTTPServer
import os
from pathlib import Path
import sys
import tempfile
import threading
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from license_fixture import LicensedEngine as Engine
from spankvanc.server import make_handler

with tempfile.TemporaryDirectory() as temporary:
    engine = Engine(Path(temporary))
    server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(engine, 'browser-test', 0))
    port = server.server_port
    server.RequestHandlerClass = make_handler(engine, 'browser-test', port)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=os.environ.get('SPANKVANC_TEST_BROWSER'), headless=True)
            page = browser.new_page(viewport={'width':1480, 'height':1100})
            errors = []
            page.on('pageerror', lambda error:errors.append(str(error)))
            page.goto(f'http://127.0.0.1:{port}')
            page.get_by_text('Engine idle', exact=True).wait_for()
            def options(index=0):
                return page.locator('.output').nth(index).locator('select[data-field="scte"] option').evaluate_all('(items) => Object.fromEntries(items.map(item => [item.value, item.textContent]))')
            def output(kind, index=0):
                page.locator('.output').nth(index).locator('select[data-field="kind"]').select_option(kind)
            def codecs(index=0):
                return page.locator('.output').nth(index).locator('select[data-field="video_codec"] option').evaluate_all('(items) => items.map(item => item.value)')
            assert options() == {'convert':'Convert 104 → 35','strip':'Strip SCTE-104'}
            assert codecs() == ['h264', 'mpeg2video']
            page.locator('select[data-field="video_codec"]').select_option('mpeg2video')
            page.locator('#save').click()
            page.get_by_text('Route saved locally.', exact=True).wait_for()
            page.reload()
            page.get_by_text('Engine idle', exact=True).wait_for()
            assert page.locator('select[data-field="video_codec"]').input_value() == 'mpeg2video'
            assert page.get_by_label('Audio codec', exact=True).input_value() == 'AAC-LC · ADTS'
            page.screenshot(path=str(ROOT / 'docs/control-panel.png'), full_page=True)
            output('decklink')
            assert codecs() == ['uncompressed']
            assert page.get_by_label('Audio codec', exact=True).input_value() == 'Embedded PCM'
            assert options() == {'pass':'Pass SCTE-104','strip':'Strip SCTE-104'}
            page.locator('#input-kind').select_option('udp')
            assert options() == {'convert':'Convert 35 → 104','strip':'Strip SCTE-35'}
            output('srt')
            assert options() == {'pass':'Pass SCTE-35','strip':'Strip SCTE-35'}
            page.locator('#add-output').click()
            output('decklink', 1)
            assert set(options()) == {'pass','strip'}
            assert set(options(1)) == {'convert','strip'}
            page.locator('#input-kind').select_option('decklink')
            assert options()['convert'] == 'Convert 104 → 35'
            assert options(1)['pass'] == 'Pass SCTE-104'
            page.locator('#input-kind').select_option('rtmp')
            assert set(options()) == set(options(1)) == {'strip'}
            output('youtube')
            assert set(options()) == {'strip'}
            assert codecs() == ['h264']
            assert page.locator('.output').first.get_by_label('Audio codec', exact=True).input_value() == 'AAC-LC · FLV'
            assert not errors, errors
            browser.close()
            print('SCTE routing rules, per-output codec choices, save/reload, audio framing labels and RTMP/SDI exclusions passed')
    finally:
        server.shutdown(); server.server_close(); thread.join()
