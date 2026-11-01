from datetime import datetime, timedelta, timezone

import pytest
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError

from app.utils import jwt_handler
from app.utils.jwt_handler import create_access_token, verify_token


def test_key_comes_from_environment():
    assert jwt_handler.SECRET_KEY == "test-signing-key"


def test_round_trip_keeps_claims():
    token = create_access_token({"user_id": 7, "username": "alice", "role": "user"})
    payload = verify_token(token)
    assert payload["user_id"] == 7
    assert payload["username"] == "alice"
    assert payload["role"] == "user"


def test_token_expires_after_twelve_hours():
    token = create_access_token({"username": "alice"})
    exp = datetime.fromtimestamp(verify_token(token)["exp"], tz=timezone.utc)
    remaining = exp - datetime.now(timezone.utc)
    assert timedelta(hours=11, minutes=59) < remaining <= timedelta(hours=12)


def test_create_does_not_mutate_input():
    claims = {"username": "alice"}
    create_access_token(claims)
    assert claims == {"username": "alice"}


def test_expired_token_is_rejected():
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    token = jwt.encode({"username": "alice", "exp": past}, "test-signing-key", algorithm="HS256")
    with pytest.raises(ExpiredSignatureError):
        verify_token(token)


def test_token_signed_with_another_key_is_rejected():
    token = jwt.encode({"username": "mallory", "role": "admin"}, "guessed-key", algorithm="HS256")
    with pytest.raises(JWTError):
        verify_token(token)


def test_tampered_payload_is_rejected():
    header, _, signature = create_access_token({"role": "user"}).split(".")
    forged = jwt.encode({"role": "admin"}, "irrelevant", algorithm="HS256").split(".")[1]
    with pytest.raises(JWTError):
        verify_token(f"{header}.{forged}.{signature}")


def test_unsigned_token_is_rejected():
    header = "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0"  # {"alg":"none","typ":"JWT"}
    body = create_access_token({"role": "admin"}).split(".")[1]
    with pytest.raises(JWTError):
        verify_token(f"{header}.{body}.")
