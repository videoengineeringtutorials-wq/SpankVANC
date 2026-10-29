"""Isolated YouTube form check; never starts an encoder or transmits media."""
import json
from pathlib import Path
import sys
import tempfile
import threading
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from spankvanc.engine import Engine,YOUTUBE_SERVER
from spankvanc.server import make_handler
from test_core import CAP,route

with tempfile.TemporaryDirectory() as folder,patch('spankvanc.engine.doctor',return_value=CAP):
    engine=Engine(Path(folder));engine.save(route())
    server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(engine,'youtube-test',0))
    port=server.server_port;server.RequestHandlerClass=make_handler(engine,'youtube-test',port)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True);page=browser.new_page();errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(f'http://127.0.0.1:{port}')
            card=page.locator('.output').first
            card.locator('[data-field="kind"]').select_option('youtube')
            bitrate=card.get_by_label('YouTube video bitrate',exact=True)
            expect(bitrate).to_have_value('14')
            bitrate.select_option('8')
            server_field=card.get_by_label('YouTube RTMPS server',exact=True)
            key=card.get_by_label('YouTube stream key · hidden for privacy',exact=True)
            expect(server_field).to_have_value(YOUTUBE_SERVER)
            expect(key).to_have_attribute('type','password')
            page.locator('#validate').click()
            expect(page.locator('#blockers')).to_contain_text('paste a YouTube stream key')
            key.fill('  fake-browser-key  ');page.locator('#save').click()
            expect(page.locator('#notice')).to_have_text('Route saved locally.')
            page.reload();expect(bitrate).to_have_value('8');expect(key).to_have_value('fake-browser-key');expect(server_field).to_have_value(YOUTUBE_SERVER)
            assert engine.config['outputs'][0]['address']==YOUTUBE_SERVER+'/fake-browser-key'
            server_field.fill('rtmps://b.rtmps.youtube.com:443/live2/')
            page.locator('#save').click();expect(page.locator('#notice')).to_have_text('Route saved locally.')
            page.reload();expect(server_field).to_have_value('rtmps://b.rtmps.youtube.com:443/live2')
            assert 'fake-browser-key' not in page.locator('body').inner_text()
            cfg=route();cfg['outputs'][0].update(kind='youtube',address=YOUTUBE_SERVER+'/fake-legacy-key');engine.save(cfg)
            page.reload();expect(key).to_have_value('fake-legacy-key')
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
            assert not errors,errors
            browser.close()
    finally:server.shutdown();server.server_close()
print('YouTube form: defaults, missing key, masking, trimming, save/reload, custom server, legacy migration, mobile: PASS')
