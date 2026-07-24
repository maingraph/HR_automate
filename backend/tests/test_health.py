"""Health endpoint behavior without external network calls."""
import json
from types import SimpleNamespace

import app.core.db as db
import app.main as main


class FakeQuery:
    def select(self, *_args):
        return self

    def limit(self, *_args):
        return self

    def execute(self):
        return SimpleNamespace(data=[])


class FakeSupabase:
    def table(self, _name):
        return FakeQuery()


class FakeResponse:
    def raise_for_status(self):
        return None


def test_readiness_reports_all_dependencies(monkeypatch):
    monkeypatch.setattr(db, "get_redis", lambda: SimpleNamespace(ping=lambda: True))
    monkeypatch.setattr(db, "get_supabase", lambda: FakeSupabase())
    monkeypatch.setattr(main.httpx, "get", lambda *_args, **_kwargs: FakeResponse())

    response = main.readiness()
    body = json.loads(response.body)

    assert response.status_code == 200
    assert body["status"] == "ready"
    assert all(check["ok"] for check in body["checks"].values())


def test_readiness_degrades_without_database(monkeypatch):
    monkeypatch.setattr(db, "get_redis", lambda: SimpleNamespace(ping=lambda: True))
    monkeypatch.setattr(
        db,
        "get_supabase",
        lambda: (_ for _ in ()).throw(ConnectionError("offline")),
    )
    monkeypatch.setattr(main.httpx, "get", lambda *_args, **_kwargs: FakeResponse())

    response = main.readiness()
    body = json.loads(response.body)

    assert response.status_code == 503
    assert body["status"] == "degraded"
    assert body["checks"]["database"] == {
        "ok": False,
        "error": "ConnectionError",
    }
