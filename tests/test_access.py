from pathlib import Path

import pytest

from skye.access import AccessService
from skye.db import Database
from skye.models import RequestContext, Scope


@pytest.fixture
async def database(tmp_path: Path):
    value = Database(tmp_path / "skye.db", "gpt-5.6-luna", "medium")
    await value.open()
    try:
        yield value
    finally:
        await value.close()


async def test_private_free_user_can_chat(database: Database) -> None:
    access = AccessService(database, frozenset({1}))
    private = RequestContext(42, "private", user_id=42)

    assert await access.allowed(private)
    assert not await access.banned(42)


async def test_ban_blocks_private_and_groups(database: Database) -> None:
    access = AccessService(database, frozenset({1}))
    await database.set_access(Scope("user", 42), "ban", created_by=1)
    await database.set_access(Scope("chat", -100), "allow", created_by=1)

    assert not await access.allowed(RequestContext(42, "private", user_id=42))
    assert not await access.allowed(RequestContext(-100, "supergroup", user_id=42))
    # The owner is above every ban.
    assert await access.allowed(RequestContext(1, "private", user_id=1))


async def test_group_needs_allowlist_or_sponsor(database: Database) -> None:
    access = AccessService(database, frozenset({1}))
    group = RequestContext(-100, "supergroup", user_id=42)

    assert not await access.allowed(group)

    await database.set_access(Scope("chat", -100), "allow", created_by=1)
    assert await access.allowed(group)


async def test_sponsor_enables_a_group(database: Database) -> None:
    access = AccessService(database, frozenset({1}))
    group = RequestContext(-100, "supergroup", user_id=42)

    assert not await access.allowed(group)
    await database.set_chat_sponsor(-100, 42)
    assert await access.allowed(group)

    await database.clear_chat_sponsor(-100)
    assert not await access.allowed(group)


async def test_owner_always_allowed(database: Database) -> None:
    access = AccessService(database, frozenset({1}))

    assert await access.allowed(RequestContext(-100, "supergroup", user_id=1))
    assert access.is_owner(1)
    assert not access.is_owner(2)
