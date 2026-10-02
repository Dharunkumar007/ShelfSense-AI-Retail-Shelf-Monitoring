"""Verify an ordinary reload replaces cached legacy assets and never auto-opens history."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory() as temp:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        upstream = f"http://127.0.0.1:{port}"
        server = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.main:app", "--port", str(port)],
            cwd=ROOT, env={**os.environ, "DATABASE_URL": f"sqlite:///{temp}/upgrade.db"},
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proxy = None
        try:
            for _ in range(100):
                try:
                    if httpx.get(upstream+"/api/health").is_success:
                        break
                except httpx.ConnectError:
                    time.sleep(.1)
            with (ROOT / "test_1005.jpg").open("rb") as handle:
                response = httpx.post(upstream+"/api/analyze", files={"file":("test.jpg",handle,"image/jpeg")}, timeout=120)
            response.raise_for_status()

            class Proxy(BaseHTTPRequestHandler):
                legacy = True
                legacy_assets = {
                    "/static/styles.css": ("text/css", b"body{background:rgb(23,67,51)} .brand img{width:618px}"),
                    "/static/app.js": ("application/javascript", b"window.legacyAssetLoaded=true;document.querySelector('#occupancyValue').textContent='92.8%';"),
                }

                def log_message(self, *_):
                    pass

                def do_GET(self):
                    if self.legacy and self.path == "/":
                        body = b'<html><head><link rel="stylesheet" href="/static/styles.css"></head><body><strong id="occupancyValue"></strong><script src="/static/app.js"></script></body></html>'
                        self.send_response(200)
                        self.send_header("Content-Type", "text/html")
                        self.send_header("Cache-Control", "no-store")
                    elif self.legacy and self.path in self.legacy_assets:
                        content_type, body = self.legacy_assets[self.path]
                        self.send_response(200)
                        self.send_header("Content-Type", content_type)
                        self.send_header("Cache-Control", "public, max-age=31536000, immutable")
                    else:
                        r = httpx.get(upstream+self.path)
                        body = r.content
                        self.send_response(r.status_code)
                        for key in ["content-type", "cache-control"]:
                            if key in r.headers:
                                self.send_header(key, r.headers[key])
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

            proxy = ThreadingHTTPServer(("127.0.0.1", 0), Proxy)
            threading.Thread(target=proxy.serve_forever, daemon=True).start()
            address = f"http://127.0.0.1:{proxy.server_port}"
            with sync_playwright() as p:
                browser = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True, args=["--no-sandbox"])
                page = browser.new_page(viewport={"width":1920,"height":1080}, bypass_csp=True)
                page.goto(address)
                assert page.locator("#occupancyValue").inner_text() == "92.8%"
                assert page.evaluate("window.legacyAssetLoaded")
                Proxy.legacy = False
                page.reload()
                page.wait_for_function("document.querySelector('#sourceContext').textContent.includes('Connected')")
                assert page.evaluate("window.legacyAssetLoaded") is None
                assert page.locator("#occupancyValue").inner_text() == "--"
                assert page.locator("#monitorShelf img").count() == 0
                assert page.locator("#historyList [data-scan]").count() == 1
                assert page.locator(".brand img").evaluate("e => e.getBoundingClientRect().width <= 212")
                assert not page.locator(".mobile-logo").is_visible()
                dark = page.evaluate("getComputedStyle(document.body).backgroundColor")
                page.locator("#themeToggle").click()
                page.wait_for_function("!document.querySelector('#themeToggle').disabled")
                assert page.evaluate("getComputedStyle(document.body).backgroundColor") != dark
                page.wait_for_function("navigator.serviceWorker.controller?.scriptURL.endsWith('/sw.js')")
                page.reload()
                page.wait_for_function("document.querySelector('#sourceContext').textContent.includes('Connected')")
                assert page.locator("#monitorShelf img").count() == 0
                page.screenshot(path="/tmp/shelfsense-v6-cache-upgrade.png", full_page=True)
                browser.close()
            print("PASS: cached legacy assets replaced on normal reload; theme colors change; logo constrained; existing history stays unopened; root service worker controls the page.")
        finally:
            if proxy:
                proxy.shutdown()
                proxy.server_close()
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()


if __name__ == "__main__":
    main()
