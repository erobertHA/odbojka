"""Poll UI checks using Chrome and an isolated temporary API/database."""
import threading
from http.server import HTTPServer
from privacy_browser import Handler
from test_api_access import app, engine
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright, expect


def admin_headers(client):
    client.post('/auth/unlock', json={'password': 'RobiJeCar'})
    login = client.post('/auth/login', json={'username': 'test-admin', 'password': 'test-admin-password'})
    return {'Authorization': 'Bearer ' + login.json()['token']}


if __name__ == '__main__':
    server = HTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='chrome', headless=True)
            for viewport in [{'width': 1280, 'height': 800}, {'width': 390, 'height': 844}]:
                context = browser.new_context(viewport=viewport, is_mobile=viewport['width'] < 600, has_touch=viewport['width'] < 600)
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(base + '/admin')
                expect(page.get_by_role('heading', name='Vstop na stran')).to_be_visible()
                page.get_by_label('Geslo', exact=True).fill('RobiJeCar')
                page.get_by_role('button', name='Vstopi', exact=True).click()
                expect(page.get_by_role('heading', name='Prijava', exact=True)).to_be_visible()
                page.get_by_label('Uporabniško ime').fill('test-admin')
                page.get_by_label('Geslo', exact=True).fill('test-admin-password')
                page.get_by_role('button', name='Prijava', exact=True).click()
                expect(page.get_by_role('heading', name='Ankete', exact=True)).to_be_visible()
                page.get_by_label('Naslov ankete', exact=True).fill('Naš dogovor')
                question = page.locator('.poll-editor').first
                question.get_by_label('Dovoli več odgovorov pri tem vprašanju').check()
                question.get_by_label('Besedilo vprašanja', exact=True).fill('Kateri dan?')
                question.get_by_label('Odgovor 1', exact=True).fill('Torek')
                question.get_by_label('Odgovor 2', exact=True).fill('Četrtek')
                question.get_by_role('button', name='Dodaj odgovor', exact=True).click()
                question.get_by_label('Odgovor 3', exact=True).fill('Petek')
                page.get_by_role('button', name='Dodaj vprašanje', exact=True).click()
                question = page.locator('.poll-editor').nth(1)
                question.get_by_label('Besedilo vprašanja', exact=True).fill('Katera ura?')
                question.get_by_label('Odgovor 1', exact=True).fill('19:00')
                question.get_by_label('Odgovor 2', exact=True).fill('20:00')
                page.get_by_role('button', name='Objavi anketo', exact=True).click()
                expect(page.get_by_text('Anketa je objavljena.', exact=True)).to_be_visible()
                page.goto(base)
                card = page.locator('.poll-card')
                expect(card).to_be_visible()
                assert card.bounding_box()['y'] < 100
                expect(card.get_by_text('Rezultati', exact=True)).not_to_be_visible()
                card.get_by_label('Tvoje ime za anketo', exact=True).fill('Ana')
                card.get_by_label('Torek', exact=True).check()
                card.get_by_label('Petek', exact=True).check()
                card.get_by_label('20:00', exact=True).check()
                card.get_by_role('button', name='Oddaj odgovore in prikaži rezultate').click()
                expect(card.get_by_text('Hvala za tvoj odgovor!', exact=True)).to_be_visible()
                expect(card.get_by_text('1 od 1 · 100 %', exact=True)).to_have_count(3)
                page.reload()
                expect(card.get_by_text('Rezultati', exact=True)).to_be_visible()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                # Another browser gets questions but no previous voter's results.
                other = browser.new_context(viewport=viewport)
                visitor = other.new_page()
                visitor.goto(base)
                visitor.get_by_label('Geslo', exact=True).fill('RobiJeCar')
                visitor.get_by_role('button', name='Vstopi', exact=True).click()
                expect(visitor.locator('.poll-card').get_by_text('Rezultati', exact=True)).not_to_be_visible()
                expect(visitor.get_by_label('Tvoje ime za anketo', exact=True)).to_be_visible()
                other.close()
                page.goto(base + '/admin')
                expect(page.get_by_role('heading', name='Kdo je odgovarjal')).to_be_visible()
                expect(page.get_by_text('Ana', exact=True)).to_be_visible()
                page.on('dialog', lambda dialog: dialog.accept())
                page.get_by_role('button', name='Arhiviraj anketo', exact=True).click()
                expect(page.get_by_text('Anketa je arhivirana.', exact=True)).to_be_visible()
                archive = page.locator('details').filter(has_text='Naš dogovor')
                expect(archive).to_be_visible()
                archive.locator('summary').click()
                expect(archive.get_by_text('Ana', exact=True)).to_be_visible()
                page.goto(base)
                expect(page.locator('.poll-card')).to_have_count(0)
                expect(page.locator('.polls-shell')).to_have_count(0)
                expect(page.get_by_role('heading', name='Trenutno ni odprtega termina.')).to_be_visible()
                assert not errors, errors
                print(f"PASS {viewport['width']}x{viewport['height']}: create multi-question poll, vote, gated results, reload, admin names, archive, no empty card")
                context.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        engine.dispose()
