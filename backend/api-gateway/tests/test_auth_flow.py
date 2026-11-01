"""Admin seeding at startup and the login / RBAC path, against a throwaway SQLite DB."""

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from app.main import app
from shared.database import SessionLocal
from shared.models.user import User


@pytest.fixture(autouse=True)
def empty_users_table(monkeypatch):
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    db = SessionLocal()
    db.query(User).delete()
    db.commit()
    db.close()
    yield


def start_gateway():
    """Entering the client runs the lifespan hook, i.e. the admin seeding."""
    return TestClient(app)


def get_admin():
    db = SessionLocal()
    try:
        return db.query(User).filter(User.username == "admin").first()
    finally:
        db.close()


def login(client, username, password):
    return client.post("/login", json={"username": username, "password": password})


def test_no_admin_is_created_without_admin_password():
    with start_gateway():
        pass
    assert get_admin() is None


def test_admin_is_created_from_admin_password(monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "first-secret")
    with start_gateway() as client:
        admin = get_admin()
        assert admin is not None and admin.role == "admin"
        assert admin.password_hash != "first-secret"

        resp = login(client, "admin", "first-secret")
        assert resp.status_code == 200
        token = resp.json()["access_token"]

        me = client.get("/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["role"] == "admin"


def test_changing_admin_password_resets_it(monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "first-secret")
    with start_gateway():
        pass
    monkeypatch.setenv("ADMIN_PASSWORD", "second-secret")
    with start_gateway() as client:
        assert login(client, "admin", "first-secret").status_code == 401
        assert login(client, "admin", "second-secret").status_code == 200


def test_restart_with_same_password_keeps_hash(monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "first-secret")
    with start_gateway():
        pass
    first_hash = get_admin().password_hash
    with start_gateway():
        pass
    assert get_admin().password_hash == first_hash


def test_unsetting_admin_password_leaves_existing_admin(monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "first-secret")
    with start_gateway():
        pass
    monkeypatch.delenv("ADMIN_PASSWORD")
    with start_gateway() as client:
        assert login(client, "admin", "first-secret").status_code == 200


def test_wrong_password_and_unknown_user_get_same_error(monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "first-secret")
    with start_gateway() as client:
        wrong = login(client, "admin", "nope")
        unknown = login(client, "nobody", "nope")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


@pytest.mark.parametrize("header", [None, "Bearer", "Bearer ", "Token abc", "Bearer not-a-jwt"])
def test_protected_route_rejects_missing_or_bad_token(header):
    headers = {"Authorization": header} if header is not None else {}
    with start_gateway() as client:
        assert client.get("/me", headers=headers).status_code == 401


def test_only_admin_can_manage_users(monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "first-secret")
    with start_gateway() as client:
        admin_token = login(client, "admin", "first-secret").json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        created = client.post("/users", headers=admin_headers,
                              json={"username": "bob", "password": "pw", "role": "user"})
        assert created.status_code == 200

        bob_token = login(client, "bob", "pw").json()["access_token"]
        bob_headers = {"Authorization": f"Bearer {bob_token}"}
        assert client.get("/users", headers=bob_headers).status_code == 403
        assert client.post("/users", headers=bob_headers,
                           json={"username": "eve", "password": "pw"}).status_code == 403

        names = {u["username"] for u in client.get("/users", headers=admin_headers).json()}
        assert names == {"admin", "bob"}


def test_forged_admin_token_cannot_list_users():
    forged = jwt.encode({"username": "x", "role": "admin"}, "guessed-key", algorithm="HS256")
    with start_gateway() as client:
        resp = client.get("/users", headers={"Authorization": f"Bearer {forged}"})
    assert resp.status_code == 401
