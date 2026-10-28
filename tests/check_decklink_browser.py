"""Hardware UI bench test. Run ONLY against an isolated test-state server."""
import os
from pathlib import Path
import time
from playwright.sync_api import sync_playwright, expect

url = os.environ.get('SPANKVANC_TEST_URL', 'http://127.0.0.1:8878')
output = os.environ['SPANKVANC_TEST_OUTPUT']
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width':1480, 'height':1100})
    errors=[]
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(url)
    expect(page.locator('#decklink-device')).to_be_visible()
    expect(page.locator('#input-address')).to_be_hidden()
    page.locator('#decklink-device').select_option(label='DeckLink Mini Recorder')
    page.locator('#decklink-mode').select_option('Hi59')
    output_card=page.locator('.output').first
    output_card.locator('[data-field="kind"]').select_option('file')
    output_card.locator('input').nth(2).fill(output)
    page.locator('#validate').click()
    expect(page.locator('#ready-tag')).to_have_text('READY')
    output_card.locator('[data-field="scte"]').select_option('strip')
    page.locator('#validate').click()
    expect(page.locator('#ready-tag')).to_have_text('READY')
    page.locator('#save').click()
    expect(page.locator('#notice')).to_have_text('Route saved locally.')
    page.reload()
    expect(page.locator('#decklink-device')).to_have_value('DeckLink Mini Recorder')
    expect(page.locator('#decklink-mode')).to_have_value('Hi59')
    page.locator('#start').click()
    expect(page.locator('#route-status')).to_have_text('Route running')
    expect(page.locator('#decklink-device')).to_be_disabled()
    page.wait_for_timeout(5000)
    page.locator('#stop').click()
    expect(page.locator('#start')).to_be_enabled()
    expect(page.locator('#decklink-device')).to_be_enabled()
    page.locator('#refresh-devices').click()
    expect(page.locator('#notice')).to_have_text('Device list refreshed.')
    page.set_viewport_size({'width':390, 'height':844})
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    assert not errors, errors
    print('DeckLink selection, mode persistence, SCTE gate, start/stop, device refresh, mobile layout: PASS')
    browser.close()
