"""Optional browser integration test. Start `python -m spankvanc serve` first.
Run with a Python environment containing playwright. No browser is downloaded.
"""
import os
from pathlib import Path
import tempfile
import sys
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from spankvanc.engine import DEFAULT
ARTIFACTS = ROOT / "build/verification"
ARTIFACTS.mkdir(parents=True, exist_ok=True)
URL = os.environ.get('SPANKVANC_TEST_URL', 'http://127.0.0.1:8877')

with tempfile.TemporaryDirectory() as temporary, sync_playwright() as playwright:
    executable = os.environ.get("SPANKVANC_TEST_BROWSER")
    browser = playwright.chromium.launch(executable_path=executable, headless=True)
    page = browser.new_page(viewport={"width":1480,"height":1100}, device_scale_factor=1)
    errors = []
    page.on("pageerror", lambda error:errors.append(str(error)))
    page.goto(URL)
    token = page.locator('meta[name="control-token"]').get_attribute('content')
    response = page.request.post(URL + '/api/save', data=DEFAULT,
                                 headers={'X-SpankVANC-Token':token})
    assert response.ok
    page.reload()
    page.get_by_text("Engine idle", exact=True).wait_for()
    page.screenshot(path=str(ARTIFACTS / "spankvanc-desktop.png"), full_page=True)
    page.set_viewport_size({"width":390,"height":844})
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.screenshot(path=str(ARTIFACTS / "spankvanc-mobile.png"), full_page=True)
    page.set_viewport_size({"width":1480,"height":1100})
    page.locator("#input-kind").select_option("file")
    page.locator("#input-address").fill(str(ARTIFACTS / "source.ts"))
    page.locator("#input-realtime").uncheck()
    first = page.locator(".output").first
    first.locator('select[data-field="kind"]').select_option("file")
    first.locator("input").nth(2).fill(str(Path(temporary) / "passed.ts"))
    first.locator('select[data-field="scte"]').select_option("strip")
    page.locator("#add-output").click()
    second = page.locator(".output").nth(1)
    second.locator('select[data-field="kind"]').select_option("file")
    second.locator("input").nth(2).fill(str(Path(temporary) / "stripped.ts"))
    second.locator('select[data-field="captions"]').select_option("strip")
    second.locator('select[data-field="video_codec"]').select_option("mpeg2video")
    page.locator("#save").click()
    page.get_by_text("Route saved locally.", exact=True).wait_for()
    page.locator("#validate").click()
    page.get_by_text("Preflight passed. You can start the route.", exact=True).wait_for()
    page.locator("#start").click()
    page.get_by_text("Route started. Monitor the log and receiving output.", exact=True).wait_for()
    expect(page.locator('#exit-code')).to_have_text('EXIT 0', timeout=15000)
    assert (Path(temporary) / "passed.ts").stat().st_size > 0
    assert (Path(temporary) / "stripped.ts").stat().st_size > 0
    assert not errors, errors
    response = page.request.post(URL + '/api/save', data=DEFAULT,
                                 headers={'X-SpankVANC-Token':token})
    assert response.ok
    print("Desktop/mobile layout, two independent output policies, save/check/start, and real encode passed")
    browser.close()
