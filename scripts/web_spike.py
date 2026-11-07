"""Isolated Stage 0 OIDC/SSE lab. No bot, database, provider key, or real chat access.

Run: uv run python scripts/web_spike.py --fixture (local transport tests), or omit
--fixture and configure SKYE_OIDC_CLIENT_ID/SECRET and SKYE_SPIKE_PUBLIC_ORIGIN.
Never mount this application in the production bootstrap.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import os
import secrets
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx
from aiohttp import web
from authlib.integrations.httpx_client import AsyncOAuth2Client
from joserfc import jwt
from joserfc.jwk import KeySet

ISSUER = "https://oauth.telegram.org"
COOKIE = "skye_spike_session"


def verify_identity(token: str, jwks: dict, client_id: str, nonce: str) -> int:
    decoded = jwt.decode(token, KeySet.import_key_set(jwks), algorithms=["RS256"])
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
    if not isinstance(claims["sub"], str) or not claims["sub"]:
        raise ValueError("Missing subject")
    if (
        isinstance(claims["aud"], list)
        and len(claims["aud"]) > 1
        and claims.get("azp") != client_id
    ):
        raise ValueError("Invalid authorized party")
    user_id = claims.get("id")
    if type(user_id) is not int or user_id <= 0:
        raise ValueError("Missing verified Telegram profile id")
    return user_id


@dataclass
class Transaction:
    verifier: str
    nonce: str
    binding: str
    expires: float


def create_app(*, fixture: bool = False, origin: str = "http://localhost:3000") -> web.Application:
    parsed = urlsplit(origin)
    if (
        parsed.scheme not in {"https", "http"}
        or not parsed.netloc
        or parsed.path
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise ValueError("Origin must be an absolute origin without a path")
    if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1"}:
        raise ValueError("Non-local origins require HTTPS")
    if fixture and parsed.hostname not in {"localhost", "127.0.0.1"}:
        raise ValueError("Fixture mode is loopback only")
    secure = parsed.scheme == "https"
    transactions: dict[str, Transaction] = {}
    sessions: dict[str, float] = {}
    client_id = os.getenv("SKYE_OIDC_CLIENT_ID", "")
    secret = os.getenv("SKYE_OIDC_CLIENT_SECRET", "")

    @web.middleware
    async def safety(request: web.Request, handler):
        peer = request.transport.get_extra_info("peername") if request.transport else None
        local_proxy = (
            peer
            and peer[0] in {"127.0.0.1", "::1"}
            and request.headers.get("Host") == "127.0.0.1:8091"
            and request.headers.get("X-Forwarded-Host") == parsed.netloc
        )
        if request.headers.get("Host") != parsed.netloc and not local_proxy:
            raise web.HTTPForbidden(text="Use the configured public origin.")
        try:
            response = await handler(request)
        except web.HTTPException as error:
            error.headers["Cache-Control"] = "no-store"
            error.headers["X-Content-Type-Options"] = "nosniff"
            raise
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    def issue_session(response: web.StreamResponse) -> None:
        value = secrets.token_urlsafe(32)
        sessions[hashlib.sha256(value.encode()).hexdigest()] = time.monotonic() + 900
        response.set_cookie(
            COOKIE, value, httponly=True, secure=secure, samesite="Lax", max_age=900, path="/"
        )

    def require_session(request: web.Request) -> None:
        digest = hashlib.sha256(request.cookies.get(COOKIE, "").encode()).hexdigest()
        if sessions.get(digest, 0) <= time.monotonic():
            raise web.HTTPUnauthorized(text="Sign in to the spike again.")

    async def fixture_session(request: web.Request) -> web.Response:
        if not fixture:
            raise web.HTTPNotFound()
        if request.headers.get("Origin") != origin:
            raise web.HTTPForbidden(text="Use the same-origin test client.")
        response = web.json_response({"mode": "synthetic", "expires_in": 900})
        issue_session(response)
        return response

    async def start(request: web.Request) -> web.Response:
        if fixture or not client_id or not secret:
            raise web.HTTPServiceUnavailable(text="Configure OIDC credentials; then try again.")
        now = time.monotonic()
        for key in list(transactions):
            if transactions[key].expires < now:
                del transactions[key]
        if len(transactions) >= 100:
            raise web.HTTPTooManyRequests(text="Wait a few minutes and try again.")
        state, binding = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        transaction = Transaction(
            secrets.token_urlsafe(48), secrets.token_urlsafe(32), binding, now + 300
        )
        transactions[state] = transaction
        async with AsyncOAuth2Client(
            client_id,
            secret,
            scope="openid profile",
            code_challenge_method="S256",
            redirect_uri=f"{origin}/api/v1/spike/auth/callback",
        ) as client:
            url, _ = client.create_authorization_url(
                f"{ISSUER}/auth",
                state=state,
                nonce=transaction.nonce,
                code_verifier=transaction.verifier,
            )
        response = web.HTTPFound(url)
        response.set_cookie(
            "skye_spike_login",
            binding,
            httponly=True,
            secure=secure,
            samesite="Lax",
            max_age=300,
            path="/api/v1/spike/auth",
        )
        raise response

    async def callback(request: web.Request) -> web.Response:
        transaction = transactions.pop(request.query.get("state", ""), None)
        if (
            transaction is None
            or transaction.expires < time.monotonic()
            or not hmac.compare_digest(
                transaction.binding, request.cookies.get("skye_spike_login", "")
            )
            or not request.query.get("code")
            or request.query.get("error")
        ):
            raise web.HTTPBadRequest(text="Login expired or was cancelled. Start login again.")
        try:
            async with AsyncOAuth2Client(
                client_id,
                secret,
                token_endpoint_auth_method="client_secret_basic",
                redirect_uri=f"{origin}/api/v1/spike/auth/callback",
                timeout=15,
            ) as client:
                tokens = await client.fetch_token(
                    f"{ISSUER}/token",
                    code=request.query["code"],
                    code_verifier=transaction.verifier,
                    grant_type="authorization_code",
                )
            async with httpx.AsyncClient(timeout=15) as client:
                keys = await client.get(f"{ISSUER}/.well-known/jwks.json")
                keys.raise_for_status()
            verified_id = verify_identity(
                tokens["id_token"], keys.json(), client_id, transaction.nonce
            )
            expected_id = os.getenv("SKYE_SPIKE_EXPECTED_USER_ID")
            if expected_id and verified_id != int(expected_id):
                raise ValueError("Unexpected account")
        except Exception:
            # Never log callback URLs, tokens, credentials or provider error bodies.
            raise web.HTTPBadRequest(text="Could not verify login. Start login again.") from None
        response = web.json_response(
            {
                "verified": True,
                "profile_id_present": True,
                "nonce_verified": True,
                "expected_account_matched": bool(expected_id),
                "note": "Lab only: no account was linked or read.",
            }
        )
        issue_session(response)
        response.del_cookie("skye_spike_login", path="/api/v1/spike/auth")
        return response

    async def events(request: web.Request) -> web.StreamResponse:
        require_session(request)
        cursor = request.headers.get("Last-Event-ID", "0")
        if cursor not in {str(n) for n in range(5)}:
            raise web.HTTPConflict(text="Cursor expired. Restart the transport test.")
        response = web.StreamResponse(
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-store, no-transform",
                "X-Accel-Buffering": "no",
                "X-Content-Type-Options": "nosniff",
            }
        )
        await response.prepare(request)
        await response.write(b"retry: 1000\n: heartbeat\n\n")
        for sequence in range(int(cursor) + 1, 5):
            await asyncio.sleep(0.15)
            require_session(request)
            await response.write(
                f'id: {sequence}\nevent: probe\ndata: {{"sequence":{sequence}}}\n\n'.encode()
            )
        await response.write(b": heartbeat\n\n")
        return response

    app = web.Application(middlewares=[safety], client_max_size=4096)
    app.router.add_post("/api/v1/spike/session", fixture_session)
    app.router.add_get("/api/v1/spike/auth/start", start)
    app.router.add_get("/api/v1/spike/auth/callback", callback)
    app.router.add_get("/api/v1/spike/events", events)
    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--port", type=int, default=8091)
    args = parser.parse_args()
    web.run_app(
        create_app(
            fixture=args.fixture,
            origin=os.getenv("SKYE_SPIKE_PUBLIC_ORIGIN", "http://localhost:3000"),
        ),
        host="127.0.0.1",
        port=args.port,
        access_log=None,
    )
