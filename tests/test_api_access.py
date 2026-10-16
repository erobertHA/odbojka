"""Run with backend dependencies + httpx. Uses only a temporary SQLite database."""
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

TEMP = tempfile.TemporaryDirectory(prefix="volleyball-privacy-")
os.environ["DATABASE_URL"] = f"sqlite:///{TEMP.name}/test.db"
os.environ["SECRET_KEY"] = "isolated-test-secret-not-used-in-production"
os.environ["ADMIN_USERNAME"] = "test-admin"
os.environ["ADMIN_PASSWORD"] = "test-admin-password"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.main import app, engine, SECRET_KEY, ALGORITHM
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import inspect


class AccessTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app, base_url="https://testserver")

    def tearDown(self):
        self.client.close()

    def unlock(self):
        result = self.client.post("/auth/unlock", json={"password": "RobiJeCar"})
        self.assertEqual(result.status_code, 200)
        return result

    def test_all_private_routes_blocked(self):
        for route in app.routes:
            if route.path in {"/health", "/auth/unlock"}:
                continue
            for method in route.methods or []:
                path = route.path.replace("{event_id}", "1").replace("{response_id}", "1")
                with self.subTest(method=method, path=path):
                    result = self.client.request(method, path)
                    self.assertEqual(result.status_code, 401)
                    if method != "HEAD":
                        self.assertTrue(result.json()["locked"])
        self.assertEqual(self.client.get("/health").json(), {"ok": True})

    def test_wrong_password_and_cookie_attributes(self):
        self.assertEqual(self.client.post("/auth/unlock", json={"password": "wrong"}).status_code, 401)
        self.assertEqual(self.client.get("/events/current").status_code, 401)
        result = self.unlock()
        cookie = result.headers["set-cookie"].lower()
        for attribute in ["httponly", "secure", "samesite=strict", "max-age=43200"]:
            self.assertIn(attribute, cookie)
        self.assertNotIn("RobiJeCar", cookie)
        self.assertEqual(self.client.get("/auth/access").status_code, 200)
        self.assertEqual(self.client.get("/admin/events").status_code, 401)

    def test_invalid_expired_and_wrong_scope_cookies(self):
        for token in ["invalid", jwt.encode({"scope": "site_access", "exp": datetime.now(timezone.utc) - timedelta(seconds=1)}, SECRET_KEY, algorithm=ALGORITHM), jwt.encode({"sub": "test-admin"}, SECRET_KEY, algorithm=ALGORITHM)]:
            self.client.cookies.set("site_access", token)
            self.assertEqual(self.client.get("/events/current").status_code, 401)
        self.client.cookies.clear()

    def test_rsvp_and_admin_workflow(self):
        self.unlock()
        result = self.client.post("/auth/login", json={"username": "test-admin", "password": "test-admin-password"})
        self.assertEqual(result.status_code, 200)
        headers = {"Authorization": f"Bearer {result.json()['token']}"}
        event = self.client.post("/admin/events", headers=headers, json={"date": "2026-10-20", "start_time": "19:00", "location": "Testna dvorana"})
        self.assertEqual(event.status_code, 200)
        event_id = event.json()["id"]
        answer = {"name": "Testni vzdevek", "response": "playing", "note": "Testna opomba"}
        created = self.client.post(f"/events/{event_id}/rsvp", json=answer)
        self.assertEqual(created.status_code, 200)
        self.assertTrue(created.json()["created"])
        updated = self.client.post(f"/events/{event_id}/rsvp", json={**answer, "response": "drinks", "client_token": created.json()["client_token"]})
        self.assertFalse(updated.json()["created"])
        public = self.client.get("/events/current").json()["responses"]
        self.assertEqual(len(public), 1)
        self.assertEqual(public[0]["response"], "drinks")
        self.assertNotIn("client_token", public[0])
        response_id = public[0]["id"]
        self.assertEqual(self.client.put(f"/admin/responses/{response_id}", headers=headers, json={**answer, "name": "Popravljeno ime"}).status_code, 200)
        self.assertEqual(self.client.delete(f"/admin/responses/{response_id}", headers=headers).status_code, 200)
        self.assertEqual(self.client.post(f"/admin/events/{event_id}/close", headers=headers).status_code, 200)
        self.assertIsNone(self.client.get("/events/current").json())

    def test_schema_contains_only_existing_tables(self):
        self.assertEqual(set(inspect(engine).get_table_names()), {"events", "responses"})
        self.assertEqual({c["name"] for c in inspect(engine).get_columns("responses")}, {"id", "event_id", "name", "response", "note", "client_token", "created_at", "updated_at"})


if __name__ == "__main__":
    unittest.main()
