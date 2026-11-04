"""Output-only format controls, independent choices, migration and save/reload."""
from pathlib import Path
import tempfile
import threading
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from playwright.sync_api import sync_playwright,expect
from spankvanc.engine import Engine
from spankvanc.server import make_handler
from test_decklink import DeckLinkOutputTests

fixture=DeckLinkOutputTests();fixture.setUp()
fixture.cap.update(caption_formats_decklink=True,recaption_decklink=True,recaption_runtime=True,whisper={'available':True,'cuda':True,'models':['small.en']})
fixture.cfg['outputs']=[dict(fixture.cfg['outputs'][0],name=mode,address='DeckLink Test '+str(i),captions='recaption',caption_format=mode) for i,mode in enumerate(('608','708','both'))]
fixture.cap['decklink_outputs']=[dict(name=out['address'],output=True,duplex='full') for out in fixture.cfg['outputs']]
with tempfile.TemporaryDirectory() as folder,patch('spankvanc.engine.doctor',return_value=fixture.cap):
    engine=Engine(Path(folder));engine.config=fixture.cfg
    server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(engine,'test',0))
    server.RequestHandlerClass=make_handler(engine,'test',server.server_port)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True);page=browser.new_page();errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(f'http://127.0.0.1:{server.server_port}')
            choices=page.locator('[data-field="caption_format"]')
            expect(choices).to_have_count(3)
            for index,mode in enumerate(('608','708','both')):expect(choices.nth(index)).to_have_value(mode)
            expect(page.locator('.source [data-field="caption_format"]')).to_have_count(0)
            choices.nth(0).select_option('both');choices.nth(1).select_option('608');choices.nth(2).select_option('708')
            page.locator('#save').click();expect(page.locator('#notice')).to_have_text('Route saved locally.')
            page.reload()
            for index,mode in enumerate(('both','608','708')):expect(choices.nth(index)).to_have_value(mode)
            expect(page.locator('#ready-tag')).to_have_text('READY')
            page.locator('[data-field="captions"]').nth(0).select_option('strip')
            expect(choices).to_have_count(2)
            fixture.cap['caption_formats_decklink']=False
            page.locator('#validate').click();expect(page.locator('#blockers')).to_contain_text('native 708 output engine update')
            assert not errors,errors
            browser.close()
        print('PASS: per-output 608/708/both, save/reload, strip hides formats, old-engine gate, no input control')
    finally:server.shutdown();server.server_close()
