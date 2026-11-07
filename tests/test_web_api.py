import json
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlsplit

import pytest
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import RSAKey

from skye.access import AccessService
from skye.config import HOSTED_MODEL, Settings
from skye.db import Database
from skye.models import Scope
from skye.telegram_projects import TelegramProjectService
from skye.threads import ThreadStore
from skye.web_api import LoginLimiter, create_app
from skye.web_auth import (
    ISSUER,
    LOGIN_COOKIE,
    SESSION_COOKIE,
    AuthStore,
    Identity,
    OIDCClient,
    digest,
    verify_identity,
)


@pytest.fixture
async def database(tmp_path: Path):
    value = Database(tmp_path / "skye.db", HOSTED_MODEL, "low")
    await value.open()
    await ThreadStore(value).migrate()
    projects = TelegramProjectService(value, ThreadStore(value))
    for owner in (1, 2):
        project = await projects.create(owner, name=f"Account {owner}")
        await projects.conversation_id(project)
    try:
        yield value
    finally:
        await value.close()


def config():
    return Settings(
        _env_file=None,
        telegram_bot_token="test",
        skye_owner_ids={999},
        skye_web_origin="https://skye.test",
        skye_oidc_client_id="client",
        skye_oidc_client_secret="test-secret",
    )


def application(database, **kwargs):
    return create_app(
        config(),
        database,
        ThreadStore(database),
        AccessService(database, frozenset({999})),
        **kwargs,
    )


async def headers(database, owner=1):
    token = await AuthStore(database).issue(owner)
    session = await AuthStore(database).session(token)
    return {
        "Host": "skye.test",
        "Cookie": f"{SESSION_COOKIE}={token}",
        "Origin": "https://skye.test",
        "X-CSRF-Token": session.csrf,
    }


async def test_two_accounts_are_isolated_and_responses_are_uncacheable(database, aiohttp_client):
    client = await aiohttp_client(application(database))
    alice, bob = await headers(database, 1), await headers(database, 2)
    threads = (await (await client.get("/api/v1/threads", headers=alice)).json())["threads"]
    assert len(threads) == 2
    thread_id = next(t["id"] for t in threads if t["project_id"] is not None)
    await ThreadStore(database).append(
        Scope("user", 1),
        thread_id,
        role="assistant",
        origin="telegram",
        text="Private reply",
        receipt="tg:1:5",
    )
    path = f"/api/v1/threads/{thread_id}"
    for suffix in ("", "/messages"):
        response = await client.get(path + suffix, headers=alice)
        assert response.status == 200
        assert response.headers["Cache-Control"] == "no-store"
        assert "Cookie" in response.headers["Vary"]
        response = await client.get(path + suffix, headers=bob)
        assert response.status == 404
        assert "Private reply" not in await response.text()
    projects = await (await client.get("/api/v1/projects", headers=bob)).json()
    assert [p["name"] for p in projects["projects"]] == ["Account 2"]
    assert (await client.get("/api/v1/threads", headers={"Host": "skye.test"})).status == 401
    assert (await client.get(path, headers=alice | {"Host": "evil.test"})).status == 403
    assert (await client.get(path, headers=alice | {"Sec-Fetch-Site": "cross-site"})).status == 403
    assert (await client.get(path + "/messages?limit=999", headers=alice)).status == 400


async def test_csrf_rotation_revocation_and_banned_account(database, aiohttp_client):
    client = await aiohttp_client(application(database))
    first, second = await headers(database), await headers(database)
    assert (
        await client.post("/api/v1/auth/logout", headers=first | {"X-CSRF-Token": "bad"})
    ).status == 403
    assert (
        await client.post("/api/v1/auth/logout", headers=first | {"Origin": "https://evil.test"})
    ).status == 403
    assert (await client.post("/api/v1/auth/logout", headers=first)).status == 200
    assert (await client.get("/api/v1/session", headers=first)).status == 401
    assert (await client.get("/api/v1/session", headers=second)).status == 200
    assert (await client.post("/api/v1/auth/logout/all", headers=second)).status == 200
    assert (await client.get("/api/v1/session", headers=second)).status == 401
    third = await headers(database)
    await database.set_access(Scope("user", 1), "ban", 999)
    assert (await client.get("/api/v1/session", headers=third)).status == 403


async def test_internal_origin_requires_separate_secret_and_still_requires_user_session(
    database, aiohttp_client
):
    settings = config().model_copy(update={"skye_web_internal_token": "test-internal-secret-" * 3})
    client = await aiohttp_client(
        create_app(
            settings, database, ThreadStore(database), AccessService(database, frozenset({999}))
        )
    )
    owner = await headers(database)
    internal = owner | {"Host": "127.0.0.1:8090"}
    assert (await client.get("/api/v1/session", headers=internal)).status == 403
    internal["X-Skye-Internal-Token"] = settings.skye_web_internal_token
    assert (await client.get("/api/v1/session", headers=internal)).status == 200
    del internal["Cookie"]
    assert (await client.get("/api/v1/session", headers=internal)).status == 401


async def test_hashed_session_idle_absolute_expiry_and_login_rotation(database):
    store = AuthStore(database)
    token = await store.issue(1)
    row = await database.fetch_one("SELECT * FROM web_auth_sessions")
    assert token not in tuple(row)
    assert row["token_hash"] == digest(token)
    await database.execute_write("UPDATE web_auth_sessions SET touched=0")
    assert await store.session(token) is None
    replacement = await store.issue(1, token)
    assert await store.session(token) is None
    await database.execute_write("UPDATE web_auth_sessions SET expires=0")
    assert await store.session(replacement) is None


async def test_durable_oidc_binding_single_use_expiry_and_identity_mismatch(database):
    store = AuthStore(database)
    state, binding, verifier, nonce = await store.begin()
    assert await store.consume(state, binding) == (verifier, nonce)
    with pytest.raises(ValueError):
        await store.consume(state, binding)
    state, binding, *_ = await store.begin()
    with pytest.raises(ValueError):
        await store.consume(state, "wrong-browser")
    state, binding, *_ = await store.begin()
    await database.execute_write("UPDATE oidc_transactions SET expires=0")
    with pytest.raises(ValueError):
        await store.consume(state, binding)
    assert await store.link(Identity("subject-not-user-id", 1)) == 1
    with pytest.raises(PermissionError):
        await store.link(Identity("subject-not-user-id", 2))
    with pytest.raises(PermissionError):
        await store.link(Identity("other-subject", 1))
    with pytest.raises(PermissionError):
        await store.link(Identity("unknown", 10000))


async def test_callback_verifies_state_sets_secure_cookie_and_handles_provider_failure(
    database, aiohttp_client
):
    provider = SimpleNamespace(
        authorization_url=lambda state, nonce, verifier: (
            f"https://oauth.telegram.org/auth?state={state}"
        ),
        exchange=AsyncMock(return_value=Identity("subject", 1)),
    )
    client = await aiohttp_client(application(database, oidc=provider))
    response = await client.get(
        "/api/v1/auth/start", headers={"Host": "skye.test"}, allow_redirects=False
    )
    state = parse_qs(urlsplit(response.headers["Location"]).query)["state"][0]
    binding = response.cookies[LOGIN_COOKIE].value
    response = await client.get(
        f"/api/v1/auth/callback?state={state}&code=secret-code",
        headers={"Host": "skye.test", "Cookie": f"{LOGIN_COOKIE}={binding}"},
        allow_redirects=False,
    )
    assert response.status == 302 and response.headers["Location"] == "/chat"
    cookie = response.cookies[SESSION_COOKIE]
    assert cookie["secure"] and cookie["httponly"] and cookie["samesite"] == "Lax"
    assert cookie["path"] == "/" and not cookie["domain"]
    response = await client.get(
        f"/api/v1/auth/callback?state={state}&code=secret-code",
        headers={"Host": "skye.test", "Cookie": f"{LOGIN_COOKIE}={binding}"},
        allow_redirects=False,
    )
    assert response.headers["Location"] == "/login?error=verification"
    assert provider.exchange.await_count == 1


def test_authorization_uses_pkce_and_nonce():
    url = OIDCClient("client", "secret", "https://skye.test").authorization_url(
        "state", "nonce", "v" * 43
    )
    query = parse_qs(urlsplit(url).query)
    assert query["code_challenge_method"] == ["S256"]
    assert query["nonce"] == ["nonce"]
    assert query["scope"] == ["openid profile"]


def test_original_registered_callback_is_supported_without_weakening_pkce():
    url = OIDCClient("client", "secret", "https://skye.test", "/auth/callback").authorization_url(
        "state", "nonce", "v" * 43
    )
    query = parse_qs(urlsplit(url).query)
    assert query["redirect_uri"] == ["https://skye.test/auth/callback"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["nonce"] == ["nonce"]


@pytest.mark.parametrize(
    "override",
    [
        {"iss": "bad"},
        {"aud": "bad"},
        {"nonce": "bad"},
        {"exp": 1},
        {"iat": 9999999999},
        {"id": True},
        {"id": "01"},
        {"id": "1.0"},
        {"id": "+1"},
        {"id": 2**63},
        {"id": None},
        {"sub": ""},
        {"aud": ["client", "other"], "azp": "wrong"},
    ],
)
def test_production_identity_fails_closed(override):
    key = RSAKey.generate_key(2048, parameters={"kid": "test"})
    claims = {
        "iss": ISSUER,
        "sub": "subject",
        "id": 1,
        "aud": "client",
        "nonce": "nonce",
        "iat": int(time.time()),
        "exp": int(time.time()) + 60,
    } | override
    token = jwt.encode({"alg": "RS256", "kid": "test"}, claims, key)
    with pytest.raises((JoseError, ValueError)):
        verify_identity(token, {"keys": [key.as_dict(private=False)]}, "client", "nonce")


def test_login_limiter_is_bounded():
    limiter = LoginLimiter()
    assert all(limiter.allow("client") for _ in range(10))
    assert not limiter.allow("client")
    for i in range(2100):
        limiter.allow(str(i))
    assert len(limiter._buckets) == 2000


async def test_run_activity_and_cost_details_are_owner_scoped(database, aiohttp_client):
    from skye.models import RequestContext
    from skye.pricing import PricingService
    from skye.quota import QuotaService
    from skye.runtime import RunOutput
    from skye.sparks import SparkService
    from skye.turns import TurnService

    store = ThreadStore(database)
    thread = await store.create(1, None, "Run details")
    access = AccessService(database, frozenset({999}))
    turns = TurnService(
        database, access, QuotaService(database, access), SparkService(database, PricingService())
    )

    async def operation(admission, run_id):
        await store.record_activity(Scope("user", 1), run_id, "web", "completed")
        await turns.record_provider_receipt(run_id, "private-provider-reference")
        return RunOutput("", (), usage_tokens=1)

    output, admission, run_id = await turns.execute(
        thread, RequestContext(1, "private", 1), "run", operation
    )
    await turns.finish_delivery(run_id, complete=True)
    await turns.settle_delivered(run_id, admission, output)
    client = await aiohttp_client(application(database))
    response = await client.get(f"/api/v1/runs/{run_id}", headers=await headers(database, 1))
    assert response.status == 200
    body = await response.json()
    assert body["activities"][0]["category"] == "web"
    assert body["delivery_state"] == "complete"
    assert body["run"]["cost_state"] == "settled"
    assert "private-provider-reference" not in json.dumps(body)
    assert (
        await client.get(f"/api/v1/runs/{run_id}", headers=await headers(database, 2))
    ).status == 404


def test_verified_identity_uses_profile_id_and_rejects_wrong_signing_key():
    key = RSAKey.generate_key(2048, parameters={"kid": "current"})
    other = RSAKey.generate_key(2048, parameters={"kid": "current"})
    claims = {
        "iss": ISSUER,
        "sub": "different-from-telegram-id",
        "id": 1,
        "aud": "client",
        "nonce": "nonce",
        "iat": int(time.time()),
        "exp": int(time.time()) + 60,
    }
    token = jwt.encode({"alg": "RS256", "kid": "current"}, claims, key)
    keys = {"keys": [key.as_dict(private=False)]}
    assert verify_identity(token, keys, "client", "nonce") == Identity(
        "different-from-telegram-id", 1
    )
    string_token = jwt.encode({"alg": "RS256", "kid": "current"}, claims | {"id": "1"}, key)
    assert verify_identity(string_token, keys, "client", "nonce").user_id == 1
    with pytest.raises(JoseError):
        verify_identity(token, {"keys": [other.as_dict(private=False)]}, "client", "nonce")
    unknown = RSAKey.generate_key(2048, parameters={"kid": "unknown"})
    with pytest.raises(JoseError):
        verify_identity(token, {"keys": [unknown.as_dict(private=False)]}, "client", "nonce")
    for missing in ("exp", "iat", "nonce", "sub", "aud", "iss"):
        incomplete = {name: value for name, value in claims.items() if name != missing}
        token = jwt.encode({"alg": "RS256", "kid": "current"}, incomplete, key)
        with pytest.raises(JoseError):
            verify_identity(token, keys, "client", "nonce")
