from pathlib import Path

import pytest

from skye.access import AccessService
from skye.db import Database
from skye.models import RequestContext, Scope
from skye.quota import FREE_DAILY, FREE_MONTHLY, QuotaService


@pytest.fixture
async def database(tmp_path: Path):
    value = Database(tmp_path / "skye.db", "gpt-5.6-luna", "medium")
    await value.open()
    try:
        yield value
    finally:
        await value.close()


async def test_allowance_tracks_usage(database: Database) -> None:
    quota = QuotaService(database, AccessService(database, frozenset({1})))
    await database.add_usage(42, 3_000)

    allowance = await quota.allowance(42)

    assert allowance.daily_used == 3_000
    assert allowance.daily_left == FREE_DAILY - 3_000
    assert allowance.monthly_left == FREE_MONTHLY - 3_000
    assert not allowance.exhausted


async def test_allow_entry_grants_complimentary_use(database: Database) -> None:
    access = AccessService(database, frozenset({1}))
    quota = QuotaService(database, access)
    private = RequestContext(42, "private", user_id=42)
    group = RequestContext(-100, "supergroup", user_id=42)

    assert not await quota.complimentary(private)

    await database.set_access(Scope("user", 42), "allow", created_by=1)
    assert await quota.complimentary(private)

    await database.set_access(Scope("chat", -100), "allow", created_by=1)
    assert await quota.complimentary(group)


async def test_allowance_exhausts_at_the_daily_limit(database: Database) -> None:
    quota = QuotaService(database, AccessService(database, frozenset({1})))
    await database.add_usage(42, FREE_DAILY)

    allowance = await quota.allowance(42)

    assert allowance.daily_left == 0
    assert allowance.exhausted
    assert await quota.exhausted(RequestContext(42, "private", user_id=42))
