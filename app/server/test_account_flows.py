"""
Integration tests: account creation, sign-in, posting, logout, and SQLite persistence
(including session survival across a process reload that simulates a server restart).

Run (no pytest required):
    cd app/server && python3 -m unittest test_account_flows -v
"""

from __future__ import annotations

import importlib
import os
import secrets
import sqlite3
import sys
import uuid
import unittest
from pathlib import Path

# Ensure sibling modules resolve when run as unittest
_SERVER_DIR = Path(__file__).resolve().parent
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))

from fastapi.testclient import TestClient


def _pk_hex() -> str:
    return secrets.token_hex(32)


def _fake_sig() -> str:
    """Server demo crypto accepts any signature of length >= 32 bytes (64 hex chars)."""
    return "ab" * 32


def _register_and_sign_in(c: TestClient) -> dict[str, str]:
    """Register + challenge/verify on one client — avoids nested TestClient and duplicate lifespan/DB close."""
    eid = f"e_{uuid.uuid4().hex[:12]}"
    pk = _pk_hex()
    reg = c.post(
        "/api/entities",
        json={
            "public_key": pk,
            "handle": f"t_{eid}",
            "profile": {"name": "Test User", "bio": "bio"},
        },
    )
    if reg.status_code != 200:
        raise AssertionError(reg.text)
    entity_id = reg.json()["id"]
    ch = c.post(
        "/api/auth/challenge",
        json={"entity_id": entity_id},
    )
    if ch.status_code != 200:
        raise AssertionError(ch.text)
    challenge = ch.json()["challenge"]
    ver = c.post(
        "/api/auth/verify",
        json={
            "entity_id": entity_id,
            "challenge": challenge,
            "signature": _fake_sig(),
        },
    )
    if ver.status_code != 200:
        raise AssertionError(ver.text)
    token = ver.json()["token"]
    return {"entity_id": entity_id, "token": token}


def _load_main_with_test_db(tmp_path: Path):
    os.environ["MESH_DB_PATH"] = str(tmp_path / "mesh_test.db")
    os.environ["MESH_NODE_ID"] = f"unittest_{os.getpid()}"
    os.environ["MESH_NODE_URL"] = "http://127.0.0.1:9"
    import importlib
    import main

    return importlib.reload(main)


class TestAccountFlows(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(os.environ.get("MESH_TEST_TMP", "/tmp")) / f"mesh_unittest_{uuid.uuid4().hex}"
        self._tmp.mkdir(parents=True, exist_ok=True)
        self.main = _load_main_with_test_db(self._tmp)
        self.db_path = self._tmp / "mesh_test.db"

    def test_create_sign_in_post_logout_sign_in_again(self):
        main = self.main
        with TestClient(main.app) as c:
            pk = _pk_hex()
            handle = f"u_{uuid.uuid4().hex[:10]}"
            r1 = c.post(
                "/api/entities",
                json={
                    "public_key": pk,
                    "handle": handle,
                    "profile": {"name": "Alice", "bio": "hello"},
                },
            )
            self.assertEqual(r1.status_code, 200, r1.text)
            body = r1.json()
            entity_id = body["id"]
            self.assertEqual(body.get("handle"), handle)
            get_e = c.get(f"/api/entities/{entity_id}")
            self.assertEqual(get_e.status_code, 200)
            self.assertEqual(get_e.json()["handle"], handle)

            ch = c.post("/api/auth/challenge", json={"entity_id": entity_id})
            self.assertEqual(ch.status_code, 200)
            challenge = ch.json()["challenge"]

            bad = c.post(
                "/api/auth/verify",
                json={
                    "entity_id": entity_id,
                    "challenge": "wrong",
                    "signature": _fake_sig(),
                },
            )
            self.assertEqual(bad.status_code, 400)

            ver = c.post(
                "/api/auth/verify",
                json={
                    "entity_id": entity_id,
                    "challenge": challenge,
                    "signature": _fake_sig(),
                },
            )
            self.assertEqual(ver.status_code, 200, ver.text)
            token = ver.json()["token"]
            self.assertIn("expires_at", ver.json())

            post1 = c.post(
                f"/api/content?token={token}",
                json={"kind": "post", "body": "first post", "access": "public"},
            )
            self.assertEqual(post1.status_code, 200, post1.text)
            pid = post1.json()["id"]
            g1 = c.get(f"/api/content/{pid}")
            self.assertEqual(g1.status_code, 200)
            self.assertEqual(g1.json()["author"], entity_id)

            feed = c.get(
                f"/api/users/{entity_id}/feed?limit=50&offset=0&view=home_timeline&labels=1"
            )
            self.assertEqual(feed.status_code, 200, feed.text)
            self.assertIn("items", feed.json())
            self.assertGreaterEqual(len(feed.json()["items"]), 1)

            out = c.post(f"/api/auth/logout?token={token}")
            self.assertEqual(out.status_code, 200, out.text)
            self.assertEqual(out.json().get("status"), "logged_out")

            denied = c.post(
                f"/api/content?token={token}",
                json={"kind": "post", "body": "should fail", "access": "public"},
            )
            self.assertEqual(denied.status_code, 401)

            ch2 = c.post("/api/auth/challenge", json={"entity_id": entity_id})
            self.assertEqual(ch2.status_code, 200)
            challenge2 = ch2.json()["challenge"]
            ver2 = c.post(
                "/api/auth/verify",
                json={
                    "entity_id": entity_id,
                    "challenge": challenge2,
                    "signature": _fake_sig(),
                },
            )
            self.assertEqual(ver2.status_code, 200)
            token2 = ver2.json()["token"]
            post2 = c.post(
                f"/api/content?token={token2}",
                json={"kind": "post", "body": "after sign-in again", "access": "public"},
            )
            self.assertEqual(post2.status_code, 200, post2.text)

            pro = c.put(
                f"/api/entities/{entity_id}?token={token2}",
                json={"name": "Alice Updated", "bio": "x", "avatar": "http://a/a.png"},
            )
            self.assertEqual(pro.status_code, 200, pro.text)

    def test_session_persists_across_simulated_restart(self):
        main = self.main
        token_holder: dict[str, str] = {}
        with TestClient(main.app) as c1:
            p = _register_and_sign_in(c1)
            token_holder["t"] = p["token"]
            token_holder["e"] = p["entity_id"]
            r = c1.post(
                f"/api/content?token={p['token']}",
                json={"kind": "post", "body": "before restart", "access": "public"},
            )
            self.assertEqual(r.status_code, 200, r.text)
            token_holder["post_id"] = r.json()["id"]

        con = sqlite3.connect(str(self.db_path))
        try:
            cur = con.execute("SELECT COUNT(*) FROM auth_sessions")
            self.assertGreaterEqual(cur.fetchone()[0], 1)
            cur = con.execute("SELECT entity_id FROM auth_sessions WHERE token = ?", (token_holder["t"],))
            row = cur.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], token_holder["e"])
        finally:
            con.close()

        import main as main_mod

        importlib.reload(main_mod)
        with TestClient(main_mod.app) as c2:
            tok = token_holder["t"]
            eid = token_holder["e"]
            g = c2.get(f"/api/entities/{eid}")
            self.assertEqual(g.status_code, 200)
            p_res = c2.post(
                f"/api/content?token={tok}",
                json={"kind": "post", "body": "after restart same token", "access": "public"},
            )
            self.assertEqual(p_res.status_code, 200, p_res.text)
            h = c2.get(f"/api/content?author={eid}")
            self.assertEqual(h.status_code, 200)
            items = h.json().get("items", [])
            self.assertGreaterEqual(len(items), 2)

    def test_unauthenticated_cannot_create_post(self):
        with TestClient(self.main.app) as c:
            r = c.post(
                "/api/content",
                json={"kind": "post", "body": "nope", "access": "public"},
            )
            self.assertIn(r.status_code, (401, 422))
            p = _register_and_sign_in(c)
            ok = c.post(
                f"/api/content?token={p['token']}",
                json={"kind": "post", "body": "yes", "access": "public"},
            )
            self.assertEqual(ok.status_code, 200)


if __name__ == "__main__":
    unittest.main()
