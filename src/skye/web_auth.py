"""Server-side OIDC and opaque sessions. Never logs callback URLs or tokens."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import re
import secrets
import time
from dataclasses import dataclass
from typing import Any, cast

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client
from joserfc import jwt
from joserfc.jwk import KeySet, KeySetSerialization

from .db import Database

ISSUER = "https://oauth.telegram.org"
SESSION_COOKIE = "__Host-skye_session"
LOGIN_COOKIE = "__Host-skye_login"
IDLE_TTL = 7 * 86_400
ABSOLUTE_TTL = 30 * 86_400

SCHEMA = """
CREATE TABLE IF NOT EXISTS oidc_transactions (
    state_hash TEXT PRIMARY KEY, binding_hash TEXT NOT NULL,
    verifier TEXT NOT NULL, nonce TEXT NOT NULL, expires REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS web_identities (
    issuer TEXT NOT NULL, subject TEXT NOT NULL, user_id INTEGER NOT NULL,
    PRIMARY KEY(issuer, subject), UNIQUE(issuer, user_id)
);
CREATE TABLE IF NOT EXISTS web_sessions (
    token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
    csrf TEXT NOT NULL, created REAL NOT NULL, touched REAL NOT NULL, expires REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS web_sessions_owner ON web_sessions(user_id);
"""


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


@dataclass(frozen=True)
class Identity:
    subject: str
    user_id: int


def verify_identity(token: str, jwks: dict[str, Any], client_id: str, nonce: str) -> Identity:
    decoded = jwt.decode(
        token, KeySet.import_key_set(cast(KeySetSerialization, jwks)), algorithms=["RS256"]
    )
    jwt.JWTClaimsRegistry(
        leeway=30,
        iss={"essential": True, "value": ISSUER},
        aud={"essential": True, "value": client_id},
        exp={"essential": True},
        iat={"essential": True},
        sub={"essential": True},
        nonce={"essential": True, "value": nonce},
    ).validate(decoded.claims)
    claims = decoded.claims
    subject, profile_id = claims["sub"], claims.get("id")
    if isinstance(profile_id, str) and re.fullmatch(r"[1-9][0-9]{0,18}", profile_id):
        profile_id = int(profile_id)
    if (
        not isinstance(subject, str)
        or not subject
        or type(profile_id) is not int
        or not 0 < profile_id < 2**63
    ):
        raise ValueError("Missing verified Telegram identity")
    if (
        isinstance(claims["aud"], list)
        and len(claims["aud"]) > 1
        and claims.get("azp") != client_id
    ):
        raise ValueError("Invalid authorized party")
    return Identity(subject, profile_id)


@dataclass(frozen=True)
class Session:
    token_hash: str
    user_id: int
    csrf: str


class OIDCClient:
    """Pinned endpoints; bounded JWKS cache with one refresh on rotation."""

    def __init__(
        self, client_id: str, secret: str, origin: str, callback_path: str = "/api/v1/auth/callback"
    ) -> None:
        if callback_path not in {"/api/v1/auth/callback", "/auth/callback"}:
            raise ValueError("Unsupported OIDC callback path")
        self.client_id, self.secret = client_id, secret
        self.callback = f"{origin}{callback_path}"
        self._keys: dict[str, Any] = {}
        self._fetched = 0.0
        self._lock = asyncio.Lock()

    def authorization_url(self, state: str, nonce: str, verifier: str) -> str:
        client = AsyncOAuth2Client(
            self.client_id,
            self.secret,
            scope="openid profile",
            code_challenge_method="S256",
            redirect_uri=self.callback,
        )
        url, _ = client.create_authorization_url(
            f"{ISSUER}/auth", state=state, nonce=nonce, code_verifier=verifier
        )
        return str(url)

    async def _jwks(self, *, refresh: bool = False) -> dict[str, Any]:
        async with self._lock:
            age = time.monotonic() - self._fetched
            if not self._keys or age > 300 or (refresh and age > 30):
                async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
                    response = await client.get(f"{ISSUER}/.well-known/jwks.json")
                    response.raise_for_status()
                    self._keys = response.json()
                self._fetched = time.monotonic()
        return self._keys

    async def exchange(self, code: str, verifier: str, nonce: str) -> Identity:
        async with AsyncOAuth2Client(
            self.client_id,
            self.secret,
            token_endpoint_auth_method="client_secret_basic",
            redirect_uri=self.callback,
            timeout=15,
        ) as client:
            tokens = await client.fetch_token(
                f"{ISSUER}/token",
                code=code,
                code_verifier=verifier,
                grant_type="authorization_code",
                client_id=self.client_id,
            )
        token = tokens["id_token"]
        keys = await self._jwks()
        try:
            return verify_identity(token, keys, self.client_id, nonce)
        except Exception:
            # Cache refresh is throttled even for repeated invalid signatures.
            keys = await self._jwks(refresh=True)
            return verify_identity(token, keys, self.client_id, nonce)


class AuthStore:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def begin(self) -> tuple[str, str, str, str]:
        state, binding, verifier, nonce = (secrets.token_urlsafe(32) for _ in range(4))
        now = time.time()
        async with self.database.transaction() as conn:
            await conn.execute("DELETE FROM oidc_transactions WHERE expires<=?", (now,))
            size = await (await conn.execute("SELECT COUNT(*) FROM oidc_transactions")).fetchone()
            if size is not None and size[0] >= 500:
                raise ValueError("Too many pending logins")
            await conn.execute(
                "INSERT INTO oidc_transactions VALUES(?,?,?,?,?)",
                (digest(state), digest(binding), verifier, nonce, now + 300),
            )
        return state, binding, verifier, nonce

    async def consume(self, state: str, binding: str) -> tuple[str, str]:
        async with self.database.transaction() as conn:
            row = await (
                await conn.execute(
                    "DELETE FROM oidc_transactions WHERE state_hash=? RETURNING *", (digest(state),)
                )
            ).fetchone()
        if (
            row is None
            or row["expires"] <= time.time()
            or not hmac.compare_digest(str(row["binding_hash"]), digest(binding))
        ):
            raise ValueError("Login expired or was cancelled")
        return str(row["verifier"]), str(row["nonce"])

    async def link(self, identity: Identity) -> int:
        async with self.database.transaction() as conn:
            known = await (
                await conn.execute(
                    "SELECT 1 FROM user_settings WHERE user_id=? UNION ALL "
                    "SELECT 1 FROM telegram_projects WHERE user_id=? LIMIT 1",
                    (identity.user_id, identity.user_id),
                )
            ).fetchone()
            if known is None:
                raise PermissionError("Start Skye in Telegram before signing in here")
            existing = await (
                await conn.execute(
                    "SELECT subject,user_id FROM web_identities WHERE issuer=? "
                    "AND (subject=? OR user_id=?)",
                    (ISSUER, identity.subject, identity.user_id),
                )
            ).fetchall()
            if any(
                row["subject"] != identity.subject or row["user_id"] != identity.user_id
                for row in existing
            ):
                raise PermissionError("Account identity does not match")
            await conn.execute(
                "INSERT OR IGNORE INTO web_identities VALUES(?,?,?)",
                (ISSUER, identity.subject, identity.user_id),
            )
        return identity.user_id

    async def issue(self, user_id: int, previous: str = "") -> str:
        token, csrf, now = secrets.token_urlsafe(32), secrets.token_urlsafe(32), time.time()
        async with self.database.transaction() as conn:
            await conn.execute(
                "DELETE FROM web_sessions WHERE token_hash=? OR expires<=? OR touched<=?",
                (digest(previous), now, now - IDLE_TTL),
            )
            # Bound device sessions without retaining IPs or user-agent strings.
            await conn.execute(
                "DELETE FROM web_sessions WHERE user_id=? AND token_hash NOT IN "
                "(SELECT token_hash FROM web_sessions WHERE user_id=? "
                "ORDER BY created DESC LIMIT 19)",
                (user_id, user_id),
            )
            await conn.execute(
                "INSERT INTO web_sessions VALUES(?,?,?,?,?,?)",
                (digest(token), user_id, csrf, now, now, now + ABSOLUTE_TTL),
            )
        return token

    async def session(self, token: str) -> Session | None:
        if not token or len(token) > 128:
            return None
        now = time.time()
        async with self.database.transaction() as conn:
            row = await (
                await conn.execute(
                    "SELECT * FROM web_sessions WHERE token_hash=? AND expires>? AND touched>?",
                    (digest(token), now, now - IDLE_TTL),
                )
            ).fetchone()
            if row is None:
                return None
            await conn.execute(
                "UPDATE web_sessions SET touched=? WHERE token_hash=?", (now, row["token_hash"])
            )
        return Session(str(row["token_hash"]), int(row["user_id"]), str(row["csrf"]))

    async def revoke(self, session: Session, *, all_devices: bool = False) -> None:
        if all_devices:
            await self.database.execute_write(
                "DELETE FROM web_sessions WHERE user_id=?", (session.user_id,)
            )
        else:
            await self.database.execute_write(
                "DELETE FROM web_sessions WHERE token_hash=?", (session.token_hash,)
            )
