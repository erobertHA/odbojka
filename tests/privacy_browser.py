"""Browser checks against built frontend and an isolated in-process API.
Requires httpx, playwright and installed Chrome. No production data is read.
"""
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from test_api_access import app, engine
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright, expect

DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def handle_request(self):
        if self.path.startswith("/api/"):
            # A new client per request ensures no test-side cookie leakage.
            with TestClient(app) as client:
                result = client.request(self.command, self.path[4:], headers={k: v for k, v in self.headers.items() if k.lower() != 'host'}, content=self.rfile.read(int(self.headers.get('Content-Length', 0))))
            self.send_response(result.status_code)
            for key, value in result.headers.multi_items():
                if key not in {"content-length", "transfer-encoding"}:
                    self.send_header(key, value)
            self.end_headers()
            self.wfile.write(result.content)
        else:
            file = DIST / self.path.split("?", 1)[0].lstrip("/")
            if not file.is_file():
                file = DIST / "index.html"
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(file.name)[0] or "application/octet-stream")
            self.end_headers()
            self.wfile.write(file.read_bytes())

    do_GET = handle_request
    do_POST = handle_request
    do_PUT = handle_request
    do_DELETE = handle_request


def check_modal(page):
    trigger = page.get_by_role("button", name="Zasebnost", exact=True)
    trigger.click()
    modal = page.get_by_role("dialog", name="Zasebnost", exact=True)
    expect(modal).to_be_visible()
    expect(modal.get_by_role("button", name="Zapri")).to_be_focused()
    content = page.locator(".privacy-content")
    page.keyboard.press("Tab")
    expect(content).to_be_focused()
    page.keyboard.press("Tab")
    expect(modal.get_by_role("button", name="Zapri")).to_be_focused()
    page.keyboard.press("Shift+Tab")
    expect(content).to_be_focused()
    assert content.evaluate("e => e.scrollHeight > e.clientHeight")
    content.evaluate("e => e.scrollTop = e.scrollHeight")
    assert content.evaluate("e => e.scrollTop > 0")
    rect = modal.bounding_box()
    assert rect and rect['x'] >= 0 and rect['width'] <= page.viewport_size['width']
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.keyboard.press("Escape")
    expect(modal).not_to_be_visible()
    expect(trigger).to_be_focused()
    trigger.click()
    modal.get_by_role("button", name="Zapri").click()
    expect(modal).not_to_be_visible()
    expect(trigger).to_be_focused()
    assert page.evaluate("document.body.style.overflow") == ''


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="chrome", headless=True)
            for viewport in [{"width": 1280, "height": 800}, {"width": 390, "height": 844}, {"width": 320, "height": 568}]:
                context = browser.new_context(viewport=viewport, is_mobile=viewport['width'] < 600, has_touch=viewport['width'] < 600)
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(base)
                expect(page.get_by_role("heading", name="Vstop na stran")).to_be_visible()
                check_modal(page)
                page.get_by_label("Geslo", exact=True).fill("RobiJeCar")
                page.get_by_role("button", name="Vstopi", exact=True).click()
                expect(page.get_by_role("heading", name="Trenutno ni odprtega termina.")).to_be_visible()
                check_modal(page)
                page.goto(base + '/admin')
                expect(page.get_by_role("heading", name="Prijava", exact=True)).to_be_visible()
                check_modal(page)
                page.get_by_label("Uporabniško ime").fill("test-admin")
                page.get_by_label("Geslo", exact=True).fill("test-admin-password")
                page.get_by_role("button", name="Prijava", exact=True).click()
                expect(page.get_by_role("heading", name="Upravljanje terminov")).to_be_visible()
                page.get_by_label("Datum", exact=True).fill("2026-10-20")
                page.get_by_label("Lokacija", exact=True).fill("Testna dvorana")
                page.get_by_role("button", name="Objavi termin").click()
                expect(page.get_by_role("heading", name="Aktivni termin")).to_be_visible()
                page.goto(base)
                expect(page.get_by_role("heading", name="Tvoj odgovor")).to_be_visible()
                check_modal(page)
                page.get_by_label("Ime", exact=True).fill("Testni udeleženec")
                page.get_by_label("Opomba", exact=False).fill("Testna opomba")
                page.get_by_role("button", name="Shrani odgovor").click()
                expect(page.get_by_text("Testni udeleženec", exact=True)).to_be_visible()
                page.get_by_label("Ime", exact=True).fill("Testni udeleženec")
                page.get_by_role("button", name="Samo na pijačo").click()
                page.get_by_role("button", name="Shrani odgovor").click()
                expect(page.get_by_text("Sprememba je uspešno shranjena.", exact=True)).to_be_visible()
                assert page.evaluate("Object.keys(localStorage).some(k => k.startsWith('volleyball_token_'))")
                # Closing this isolated event prepares the next viewport's empty state.
                with TestClient(app) as client:
                    client.post('/auth/unlock', json={'password': 'RobiJeCar'})
                    login = client.post('/auth/login', json={'username': 'test-admin', 'password': 'test-admin-password'})
                    headers = {'Authorization': 'Bearer ' + login.json()['token']}
                    event = client.get('/events/current').json()
                    client.post(f"/admin/events/{event['id']}/close", headers=headers)
                assert not errors, errors
                print(f"PASS {viewport['width']}x{viewport['height']}: modal, focus, ESC, scroll, locked/empty/admin/event pages, RSVP create/update")
                context.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        engine.dispose()
