import logging
import os
import secrets

from jose import jwt
from datetime import datetime, timedelta


# The signing key must never live in source code: anyone who can read it can mint an admin
# token. Set JWT_SECRET_KEY in .env (local) or the Render dashboard (deployed). Without it, a
# random key is generated per process, so logins work but reset whenever the gateway restarts.
SECRET_KEY = os.environ.get("JWT_SECRET_KEY") or secrets.token_urlsafe(32)
if not os.environ.get("JWT_SECRET_KEY"):
    logging.getLogger(__name__).warning(
        "JWT_SECRET_KEY is not set; using a random key, so tokens will not survive a restart."
    )

ALGORITHM = "HS256"


def create_access_token(data: dict):

    to_encode = data.copy()

    expire = datetime.utcnow() + timedelta(hours=12)

    to_encode.update({
        "exp": expire
    })

    return jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM
    )


def verify_token(token: str):

    payload = jwt.decode(
        token,
        SECRET_KEY,
        algorithms=[ALGORITHM]
    )

    return payload