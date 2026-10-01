"""Real-model browser checks in a temporary database, using installed Chrome."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

import httpx
from PIL import Image, ImageStat
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory() as temp:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        base = f"http://127.0.0.1:{port}"
        env = {**os.environ, "DATABASE_URL": f"sqlite:///{temp}/browser.db"}
        server = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(100):
                try:
                    if httpx.get(base+"/api/health").status_code == 200:
                        break
                except httpx.ConnectError:
                    time.sleep(.1)
            with sync_playwright() as p:
                browser = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True,
                    args=["--no-sandbox", "--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"])
                context = browser.new_context(viewport={"width":1440,"height":1000})
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(base)
                page.wait_for_function("document.querySelector('#sourceContext').textContent.includes('Connected')")
                assert page.locator("#monitorShelf img").count() == 0
                assert page.locator("#occupancyValue").inner_text() == "--"
                assert page.locator("html").get_attribute("data-theme") == "dark"
                assert page.locator(".brand img").evaluate("img => img.complete && img.naturalWidth === 618")
                page.screenshot(path="/tmp/shelfsense-v4-empty-dark.png", full_page=True)
                page.locator("#themeToggle").click()
                page.wait_for_function("document.documentElement.dataset.theme === 'light' && !document.querySelector('#themeToggle').disabled")
                page.reload()
                page.wait_for_function("document.querySelector('#sourceContext').textContent.includes('Connected')")
                assert page.locator("html").get_attribute("data-theme") == "light"
                page.screenshot(path="/tmp/shelfsense-v4-empty-light.png", full_page=True)
                page.locator("#themeToggle").click()
                page.wait_for_function("!document.querySelector('#themeToggle').disabled")
                page.locator("#chooseImage").dispatch_event("pointerdown", {"clientX":1100,"clientY":60})
                assert page.locator(".ripple").count() == 1
                page.locator("#fileInput").set_input_files(str(ROOT / "test_1005.jpg"))
                with page.expect_response(lambda r: r.url.endswith("/api/analyze") and r.request.method == "POST", timeout=120000) as pending:
                    page.locator("#scanButton").click()
                first = pending.value.json()
                assert pending.value.status == 200, first
                page.wait_for_function("document.querySelector('#scanState').textContent==='Complete'")
                assert first["trend"] == [z["occupancy"] for z in first["zones"]]
                page.screenshot(path="/tmp/shelfsense-v3-overview.png", full_page=True)
                page.locator('[data-page="monitor"]').click()
                # Verify actual pointer hit-testing with zones still enabled.
                hit = page.locator("#analysisShelf .product-box").evaluate_all("""boxes => boxes.findIndex(b => {
                    const r = b.getBoundingClientRect();
                    return document.elementFromPoint(r.left+r.width/2,r.top+r.height/2) === b;
                })""")
                assert hit >= 0
                product = page.locator("#analysisShelf .product-box").nth(hit)
                product.hover()
                assert "% confidence" in page.locator("#productTooltip").inner_text()
                assert not page.locator("#productTooltip").is_hidden()
                product.focus()
                assert product.get_attribute("aria-describedby") == "productTooltip"
                page.screenshot(path="/tmp/shelfsense-v4-product-hover.png", full_page=True)
                page.keyboard.press("Escape")
                assert page.locator("#productTooltip").is_hidden()
                page.reload()
                page.wait_for_function("document.querySelector('#sourceContext').textContent.includes('Connected')")
                assert page.locator("#monitorShelf img").count() == 0
                assert page.locator("#analysisShelf img").count() == 0
                assert page.locator("#occupancyValue").inner_text() == "--"
                assert page.locator("#historyList [data-scan]").count() == 1
                page.locator("#refreshButton").click()
                assert page.locator("#monitorShelf img").count() == 0
                page.locator("#historyList [data-scan]").first.click()
                page.locator("#monitorShelf img").wait_for(state="attached")
                page.locator('[data-page="monitor"]').click()
                page.locator('[name="confidence"]').fill("0.9")
                page.locator("#fileInput").set_input_files(str(ROOT / "test_1008.jpg"))
                with page.expect_response(lambda r: r.url.endswith("/api/analyze") and r.request.method == "POST", timeout=120000) as pending:
                    page.locator("#scanButton").click()
                second = pending.value.json()
                assert pending.value.status == 200, second
                page.wait_for_function("document.querySelector('#scanState').textContent==='Complete'")
                assert first["trend"] != second["trend"], (first["trend"],second["trend"])
                page.locator("#showHeatmap").check()
                page.locator("#analysisShelf [data-zone]").first.click(position={"x":10,"y":10})
                assert "missing" in page.locator("#selectedZone").inner_text()
                page.screenshot(path="/tmp/shelfsense-v3-monitor.png",full_page=True)
                page.locator('[data-page="analysis"]').click()
                page.locator("#compareButton").click()
                page.wait_for_function("document.querySelector('#comparisonSummary').textContent.includes('percentage points')")
                page.locator("#zoneSearch").fill("impossible-zone")
                assert "No matching" in page.locator("#zoneTable").inner_text()
                page.locator("#zoneSearch").fill("")
                page.locator('[data-page="alerts"]').click()
                page.locator("#taskBoard [data-task]").first.click()
                page.locator('#taskForm [name="state"]').select_option("in_progress")
                page.locator('#taskForm [name="assignee"]').fill("Store operator")
                page.locator('#taskForm button[type="submit"]').click()
                page.wait_for_function("!document.querySelector('#taskDialog').open")
                page.locator("#taskBoard .task-column").nth(2).locator(".task-card").first.wait_for()
                page.screenshot(path="/tmp/shelfsense-v3-tasks.png",full_page=True)
                page.locator('[data-page="reports"]').click()
                page.locator("#historyTable [data-scan]").first.wait_for()
                assert page.locator("#historyChart .time-bar").count() == 2
                with page.expect_download() as download:
                    page.locator("#exportButton").click()
                assert download.value.suggested_filename.endswith(".csv")
                page.screenshot(path="/tmp/shelfsense-v3-reports.png",full_page=True)
                page.locator('[data-page="inventory"]').click()
                page.locator('#inventoryTable [data-field="expected_count"]').first.fill("90")
                page.locator("#saveLayout").click()
                page.wait_for_function("document.querySelector('#layoutMessage').textContent.includes('Layout saved')")
                page.locator('[data-page="monitor"]').click()
                page.locator("#startCamera").click()
                page.wait_for_function("document.querySelector('#cameraVideo').videoWidth>0")
                page.locator("#stopCamera").click()
                page.wait_for_function("document.querySelector('#cameraVideo').srcObject===null")
                # Account flow uses this disposable database only.
                page.locator('[data-page="admin"]').click()
                page.locator('#userForm [name="username"]').fill("browser-admin")
                page.locator('#userForm [name="password"]').fill("browser-check-password")
                page.locator('#userForm [name="role"]').select_option("admin")
                page.locator('#userForm button[type="submit"]').click()
                page.locator("#loginDialog").wait_for()
                page.locator('#loginForm [name="username"]').fill("browser-admin")
                page.locator('#loginForm [name="password"]').fill("browser-check-password")
                page.locator('#loginForm button').click()
                page.wait_for_function("!document.querySelector('#loginDialog').open")
                page.wait_for_function("document.querySelector('#accountLabel').textContent.includes('browser-admin')")
                for theme in ["light", "dark"]:
                    if page.locator("html").get_attribute("data-theme") != theme:
                        page.locator("#themeToggle").click()
                        page.wait_for_function("!document.querySelector('#themeToggle').disabled")
                    page.locator('[data-page="dashboard"]').click()
                    page.screenshot(path=f"/tmp/shelfsense-v4-{theme}-desktop.png",full_page=True)
                page.evaluate("window.scrollTo(0,document.documentElement.scrollHeight)")
                page.wait_for_function("document.querySelector('#scrollProgress').getAttribute('aria-valuenow') === '100'")
                for width in [390,360,768,1440]:
                    page.set_viewport_size({"width":width,"height":844 if width<800 else 1000})
                    for section in ["dashboard","monitor","analysis","alerts","inventory","reports","admin"]:
                        page.locator(f'[data-page="{section}"]').click()
                        overflow = page.evaluate("document.documentElement.scrollWidth > innerWidth + 1")
                        assert not overflow, (width,section)
                        if width < 800:
                            assert page.locator(f'[data-page="{section}"] span').first.evaluate("""el => {
                                const r=el.getBoundingClientRect(), n=el.closest('nav').getBoundingClientRect();
                                return r.top>=n.top && r.bottom<=n.bottom && r.bottom<=innerHeight;
                            }"""), (width,section,"clipped navigation label")
                    if width == 390:
                        page.locator('[data-page="dashboard"]').click()
                        page.screenshot(path="/tmp/shelfsense-v3-mobile.png",full_page=True)
                assert not errors, errors
                page.emulate_media(reduced_motion="reduce")
                page.locator("#themeToggle").click()
                assert page.locator("html").get_attribute("data-theme") == "light"
                for path in ["privacy", "terms"]:
                    page.goto(f"{base}/static/{path}.html")
                    assert page.locator("h1").inner_text() in ["Privacy Policy", "Terms of Service"]
                for name in ["overview","monitor","mobile"]:
                    with Image.open(f"/tmp/shelfsense-v3-{name}.png") as im:
                        assert max(ImageStat.Stat(im.convert("RGB")).stddev)>15
                print(json.dumps({"first_trend":first["trend"],"second_trend":second["trend"],"first_ms":first["inference_ms"],"second_ms":second["inference_ms"],"viewports":[360,390,768,1440],"js_errors":errors}))
                browser.close()
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()


if __name__ == "__main__":
    main()
