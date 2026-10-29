"""A first-time user's setup flow, including consent and actionable errors."""
from pathlib import Path
from unittest.mock import patch
import tempfile,threading
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright,expect
from test_setup import setup

with tempfile.TemporaryDirectory() as folder:
    wizard=setup.Setup(Path(__file__).resolve().parents[1],Path(folder)/'data')
    include=Path(folder)/'SDK/Win/include';include.mkdir(parents=True)
    (include/'DeckLinkAPIVersion.h').write_text('#define BLACKMAGIC_DECKLINK_API_VERSION 0x0c080000\n')
    (include/'DeckLinkAPI.idl').touch()
    def pick():wizard.sdk='SDK/Win/include';wizard.remember(sdk=wizard.sdk)
    def install(device):
        assert device=='cpu'
        wizard.step='Setup complete';wizard.ready=True
        wizard.log('Your app is ready.')
    wizard.pick_sdk=pick;wizard.run=install
    server=ThreadingHTTPServer(('127.0.0.1',0),setup.handler(wizard,'browser-token',0))
    port=server.server_port;server.RequestHandlerClass=setup.handler(wizard,'browser-token',port)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            page=browser.new_page(viewport={'width':1100,'height':900});errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(f'http://127.0.0.1:{port}')
            expect(page.locator('h1')).to_contain_text('PC ready')
            expect(page.locator('#install')).to_be_disabled()
            with patch.object(setup.webbrowser,'open') as vendor, page.expect_response('**/api/sdk'):
                page.locator('#sdk-download').click()
            vendor.assert_called_once_with(setup.SDK_URL)
            expect(page.locator('#pick-sdk-folder')).to_be_enabled()
            page.locator('#sdk-path').fill(str(include.parent.parent))
            page.locator('#use-sdk-path').click()
            expect(page.locator('#sdk-status')).to_contain_text('SDK 12.8 selected:')
            expect(page.locator('#install')).to_be_disabled()
            page.locator('#consent').check()
            expect(page.locator('#install')).to_be_enabled()
            page.locator('#install').click()
            expect(page.locator('#step')).to_have_text('Setup complete')
            expect(page.locator('#launch')).to_be_visible()
            expect(page.locator('#ready')).to_contain_text('No activation key is required')
            assert not errors,errors
            page.screenshot(path='build/setup-preview.png',full_page=True)
            browser.close()
    finally:
        server.shutdown();server.server_close();thread.join()
print('First-time setup, SDK selection, consent and ready state: PASS')
