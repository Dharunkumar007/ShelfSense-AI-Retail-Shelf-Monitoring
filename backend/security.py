import hashlib
import os
import secrets
import time
from fastapi import Depends, HTTPException, Request
from sqlalchemy import func, select
from backend.storage import engine, sessions, users


def hash_password(password):
    salt = secrets.token_hex(16)
    key = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()
    return f"{salt}:{key}"


def verify_password(password, stored):
    salt, expected = stored.split(":")
    actual = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()
    return secrets.compare_digest(actual, expected)


def current_user(request: Request):
    token = request.cookies.get("shelfsense_session", "")
    with engine.connect() as conn:
        user = conn.execute(select(users.c.id, users.c.username, users.c.role).join(
            sessions, sessions.c.user_id == users.c.id).where(
            sessions.c.token == hashlib.sha256(token.encode()).hexdigest(),
            sessions.c.expires > int(time.time()))).mappings().first()
        if user:
            return dict(user)
        if conn.scalar(select(func.count()).select_from(users)) == 0:
            local_host = request.url.hostname in ("127.0.0.1", "localhost", "::1", "testserver")
            if not os.environ.get("VERCEL") and local_host and request.client and request.client.host in ("127.0.0.1", "::1", "testclient"):
                return {"id": 0, "username": "Local operator", "role": "admin", "local": True}
            raise HTTPException(503, "Create an administrator on the server before remote access.")
    raise HTTPException(401, "Sign in to continue.")


def require(*roles):
    def dependency(user=Depends(current_user)):
        if user["role"] not in roles:
            raise HTTPException(403, "Your role cannot perform this action.")
        return user
    return dependency
