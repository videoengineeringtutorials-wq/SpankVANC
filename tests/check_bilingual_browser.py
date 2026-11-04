"""Optional per-output Spanish CC2 selection, save/reload and disabled state."""
from pathlib import Path
import copy
import tempfile
import threading
from http.server import ThreadingHTTPServer
from unittest.mock import patch,Mock
from playwright.sync_api import sync_playwright,expect
from spankvanc.engine import Engine
from spankvanc.server import make_handler
from test_whisper import WhisperTests

cfg,cap=WhisperTests().route()
cap.update(caption_formats_decklink=True,bilingual_decklink=True)
cfg['outputs']=[dict(cfg['outputs'][0],name='Spanish optional',caption_format='708'),dict(cfg['outputs'][0],name='English only',address='english.ts')]
with tempfile.TemporaryDirectory() as folder,patch('spankvanc.engine.doctor',return_value=cap):
    engine=Engine(Path(folder));engine.config=cfg
    engine.capabilities['translation_available']=True
    server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(engine,'test',0))
    server.RequestHandlerClass=make_handler(engine,'test',server.server_port)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True);page=browser.new_page();errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(f'http://127.0.0.1:{server.server_port}')
            choices=page.locator('[data-field="spanish_cc2"]')
            expect(choices).to_have_count(2)
            expect(choices.nth(0)).not_to_be_checked()
            choices.nth(0).check()
            expect(page.locator('[data-field="caption_format"]').nth(0)).to_have_value('both')
            page.locator('#save').click()
            expect(page.locator('#notice')).to_have_text('Route saved locally.')
            page.reload()
            expect(choices.nth(0)).to_be_checked();expect(choices.nth(1)).not_to_be_checked()
            expect(page.locator('#ready-tag')).to_have_text('READY')
            engine.process=Mock();engine.process.poll.return_value=None
            expect(choices.nth(0)).to_be_disabled(timeout=5000)
            expect(page.locator('#translation-input')).to_be_enabled()
            engine.process=None
            expect(choices.nth(0)).to_be_enabled(timeout=5000)
            page.locator('[data-field="caption_format"]').nth(0).select_option('708')
            expect(choices.nth(0)).not_to_be_checked()
            page.locator('[data-field="captions"]').nth(0).select_option('pass')
            expect(choices).to_have_count(1)
            assert not errors,errors
            browser.close()
        print('PASS: CC2 defaults off, selected output only, 708 compatibility, save/reload, live locking, pass excludes CC2')
    finally:server.shutdown();server.server_close()
