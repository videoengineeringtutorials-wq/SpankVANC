"""Run only against an isolated remote test-state server with a free SDI input."""
import os,time
from playwright.sync_api import sync_playwright,expect
url=os.environ.get('SPANKVANC_TEST_URL','http://127.0.0.1:8878')
output=os.environ['SPANKVANC_TEST_OUTPUT']
with sync_playwright() as p:
 b=p.chromium.launch(headless=True);page=b.new_page(viewport={'width':1480,'height':1200});errors=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto(url)
 page.locator('#decklink-device').select_option('DeckLink Mini Recorder');page.locator('#decklink-mode').select_option('Hi59')
 card=page.locator('.output').first;card.locator('[data-field="kind"]').select_option('file');card.locator('input').nth(2).fill(output)
 card.locator('[data-field="scte"]').select_option('convert')
 page.locator('#validate').click();expect(page.locator('#ready-tag')).to_have_text('READY')
 page.locator('#monitor-start').click();expect(page.locator('#caption-status')).to_have_text('LIVE INPUT',timeout=15000)
 page.wait_for_timeout(2000)
 assert '0 frames' not in page.locator('#caption-counts').inner_text()
 page.locator('#caption-service').select_option('CC4');expect(page.locator('#caption-service')).to_be_enabled()
 page.locator('#start').click();expect(page.locator('#route-status')).to_have_text('Route running',timeout=15000)
 expect(page.locator('#monitor-stop')).to_be_disabled()
 expect(page.locator('#caption-service')).to_be_enabled()
 expect(page.locator('#caption-status')).to_have_text('LIVE INPUT',timeout=15000)
 page.wait_for_timeout(6000)
 page.locator('#stop').click();expect(page.locator('#start')).to_be_enabled()
 page.locator('#caption-service').select_option('CC1')
 page.locator('#monitor-start').click();expect(page.locator('#caption-status')).to_have_text('LIVE INPUT',timeout=15000)
 page.locator('#monitor-stop').click();expect(page.locator('#caption-status')).to_have_text('STOPPED',timeout=10000)
 page.screenshot(path='build/verification/caption-monitor-desktop.png',full_page=True)
 page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
 page.screenshot(path='build/verification/caption-monitor-mobile.png',full_page=True)
 assert not errors,errors
 b.close()
 print('Monitor-only capture, live counters, CC selection, automatic route handoff, SCTE conversion readiness, route stop/release, mobile layout: PASS')
