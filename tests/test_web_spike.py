import importlib.util
import sys
import time
from pathlib import Path

import pytest
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import RSAKey

spec = importlib.util.spec_from_file_location("web_spike", Path("scripts/web_spike.py"))
assert spec is not None and spec.loader is not None
spike = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = spike
spec.loader.exec_module(spike)


def signed_identity(**overrides):
    key = RSAKey.generate_key(2048, parameters={"kid": "test"})
    now = int(time.time())
    claims = {
        "iss": spike.ISSUER,
        "sub": "not-the-telegram-id",
        "id": 42,
        "aud": "client",
        "iat": now,
        "exp": now + 60,
        "nonce": "nonce",
    } | overrides
    token = jwt.encode({"alg": "RS256", "kid": "test"}, claims, key)
    return token, {"keys": [key.as_dict(private=False)]}


def test_oidc_links_profile_id_not_subject():
    token, keys = signed_identity()
    assert spike.verify_identity(token, keys, "client", "nonce") == 42


@pytest.mark.parametrize(
    "overrides",
    [
        {"iss": "https://attacker.invalid"},
        {"aud": "other"},
        {"nonce": "other"},
        {"id": None},
        {"id": "42"},
        {"id": True},
        {"exp": 1},
        {"iat": 9999999999},
        {"aud": ["client", "other"], "azp": "other"},
    ],
)
def test_oidc_fails_closed(overrides):
    token, keys = signed_identity(**overrides)
    with pytest.raises((JoseError, ValueError)):
        spike.verify_identity(token, keys, "client", "nonce")


async def test_spike_requires_session_origin_and_replays_cursor(aiohttp_client):
    client = await aiohttp_client(spike.create_app(fixture=True))
    headers = {"Host": "localhost:3000"}
    assert (await client.get("/api/v1/spike/events", headers=headers)).status == 401
    assert (await client.post("/api/v1/spike/session", headers=headers)).status == 403
    response = await client.post(
        "/api/v1/spike/session", headers=headers | {"Origin": "http://localhost:3000"}
    )
    cookie = response.cookies[spike.COOKIE].value
    headers["Cookie"] = f"{spike.COOKIE}={cookie}"
    response = await client.get("/api/v1/spike/events", headers=headers | {"Last-Event-ID": "2"})
    body = await response.text()
    assert response.headers["Content-Type"] == "text/event-stream"
    assert "no-transform" in response.headers["Cache-Control"]
    assert "id: 2" not in body and "id: 3" in body and "heartbeat" in body
    assert (
        await client.get("/api/v1/spike/events", headers=headers | {"Last-Event-ID": "99"})
    ).status == 409


async def test_fixture_endpoint_is_absent_in_oidc_mode(aiohttp_client):
    client = await aiohttp_client(spike.create_app())
    response = await client.post("/api/v1/spike/session", headers={"Host": "localhost:3000"})
    assert response.status == 404


def test_fixture_cannot_use_nonlocal_origin():
    with pytest.raises(ValueError):
        spike.create_app(fixture=True, origin="https://example.org")


async def test_authorization_uses_pkce_nonce_and_single_use_browser_binding(
    aiohttp_client, monkeypatch
):
    from urllib.parse import parse_qs, urlsplit

    monkeypatch.setenv("SKYE_OIDC_CLIENT_ID", "test-client")
    monkeypatch.setenv("SKYE_OIDC_CLIENT_SECRET", "test-secret")
    client = await aiohttp_client(spike.create_app())
    headers = {"Host": "localhost:3000"}
    response = await client.get("/api/v1/spike/auth/start", headers=headers, allow_redirects=False)
    assert response.status == 302
    query = parse_qs(urlsplit(response.headers["Location"]).query)
    assert query["code_challenge_method"] == ["S256"]
    assert query["scope"] == ["openid profile"]
    assert len(query["nonce"][0]) >= 32
    url = f"/api/v1/spike/auth/callback?state={query['state'][0]}&code=untrusted"
    # Wrong browser binding consumes the transaction without any provider exchange.
    wrong = headers | {"Cookie": "skye_spike_login=wrong"}
    assert (await client.get(url, headers=wrong)).status == 400
    assert (await client.get(url, headers=headers)).status == 400


def test_signature_cannot_be_replaced():
    token, _ = signed_identity()
    _, unrelated_keys = signed_identity()
    with pytest.raises(JoseError):
        spike.verify_identity(token, unrelated_keys, "client", "nonce")
