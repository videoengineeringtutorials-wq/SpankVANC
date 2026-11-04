"""Dashboard manual SCTE, running button state, and SRT mode persistence."""
import tempfile
import threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from unittest.mock import Mock, patch
from playwright.sync_api import sync_playwright, expect
from spankvanc.engine import Engine
from spankvanc.manual_scte import prepare_journals
from spankvanc.server import make_handler
from test_core import CAP, route

cap=dict(CAP,manual_scte35=True,manual_scte104=True)
with tempfile.TemporaryDirectory() as folder, patch('spankvanc.engine.doctor',return_value=cap):
    engine=Engine(Path(folder));engine.config=route()
    server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(engine,'test',0))
    server.RequestHandlerClass=make_handler(engine,'test',server.server_port)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True);page=browser.new_page();errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(f'http://127.0.0.1:{server.server_port}')
            page.locator('[data-field="scte"]').select_option('manual')
            page.locator('#save').click()
            expect(page.locator('#notice')).to_have_text('Route saved locally.')
            page.reload();expect(page.locator('[data-field="scte"]')).to_have_value('manual')
            expect(page.get_by_role('button',name='Start break',exact=True)).to_be_disabled()
            engine.manual_journals=prepare_journals(Path(folder),engine.config)
            engine.process=Mock();engine.process.poll.return_value=None
            expect(page.get_by_role('button',name='Start break',exact=True)).to_be_enabled(timeout=5000)
            page.locator('[data-cue-duration]').fill('30.5')
            page.get_by_role('button',name='Start break',exact=True).click()
            expect(page.locator('#notice')).to_contain_text('Start break queued')
            expect(page.get_by_role('button',name='Start break',exact=True)).to_be_disabled()
            page.get_by_role('button',name='End break',exact=True).click()
            expect(page.locator('#notice')).to_contain_text('End break queued')
            assert engine.manual_journals[0].stat().st_size==128
            engine.process=None
            expect(page.locator('#input-kind')).to_be_enabled(timeout=5000)
            page.locator('#input-kind').select_option('srt')
            page.locator('#input-address').fill('srt://127.0.0.1:9000')
            page.locator('#input-srt-mode').select_option('listener')
            page.locator('[data-field="kind"]').select_option('srt')
            page.get_by_label('Destination · hidden for privacy',exact=True).fill('srt://127.0.0.1:9001?localport=9002')
            page.locator('[data-field="srt_mode"]').select_option('rendezvous')
            page.locator('#save').click();expect(page.locator('#notice')).to_have_text('Route saved locally.')
            page.reload();expect(page.locator('#input-srt-mode')).to_have_value('listener')
            expect(page.locator('[data-field="srt_mode"]')).to_have_value('rendezvous')
            for kind in ('rtmp','youtube'):
                page.locator('[data-field="kind"]').select_option(kind)
                expect(page.locator('[data-field="scte"] option[value="manual"]')).to_have_count(0)
            assert not errors,errors
            browser.close()
        print('PASS: manual cue controls, live output selection, SRT mode persistence and RTMP/YouTube exclusion')
    finally:server.shutdown();server.server_close()
