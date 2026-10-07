from pathlib import Path

import pytest

from skye.db import Database
from skye.models import RequestContext
from skye.pricing import SPARK_SCALE, ModelPrice, PricingService, TurnUsage
from skye.sparks import SparkError, SparkService, format_milli


@pytest.fixture
async def database(tmp_path: Path):
    value = Database(tmp_path / "skye.db", "gpt-5.6-luna", "medium")
    await value.open()
    try:
        yield value
    finally:
        await value.close()


@pytest.fixture
def wallet(database: Database) -> SparkService:
    return SparkService(database, PricingService())


def test_format_milli_is_exact() -> None:
    assert format_milli(0) == "0"
    assert format_milli(1000) == "1"
    assert format_milli(3400) == "3.4"
    assert format_milli(3450) == "3.45"
    assert format_milli(500) == "0.5"
    assert format_milli(1) == "0.001"


async def test_credit_and_charge_move_the_balance(database: Database, wallet: SparkService) -> None:
    assert await wallet.balance(42) == 0

    await wallet.credit(42, 5 * SPARK_SCALE, kind="topup", reason="stars")
    assert await wallet.balance(42) == 5 * SPARK_SCALE

    assert await wallet.charge(42, 2 * SPARK_SCALE, reason="request")
    assert await wallet.balance(42) == 3 * SPARK_SCALE

    entries = await wallet.ledger(42)
    assert [entry.delta_milli for entry in entries] == [-2 * SPARK_SCALE, 5 * SPARK_SCALE]


async def test_charge_refuses_to_overdraw(database: Database, wallet: SparkService) -> None:
    await wallet.credit(42, SPARK_SCALE)

    assert not await wallet.charge(42, 2 * SPARK_SCALE)
    assert await wallet.balance(42) == SPARK_SCALE


async def test_credit_rejects_non_positive(database: Database, wallet: SparkService) -> None:
    with pytest.raises(SparkError):
        await wallet.credit(42, 0)


async def test_payer_is_speaker_unless_sponsored(database: Database, wallet: SparkService) -> None:
    private = RequestContext(42, "private", user_id=42)
    group = RequestContext(-100, "supergroup", user_id=42)

    assert await wallet.payer(private) == 42
    assert await wallet.payer(group) == 42

    await wallet.set_sponsor(-100, 7)
    assert await wallet.payer(group) == 7
    # Private chat is never sponsored by a group sponsor.
    assert await wallet.payer(private) == 42


async def test_cost_milli_uses_pricing(database: Database) -> None:
    wallet = SparkService(
        database,
        PricingService(
            model_prices={"x": ModelPrice(input_per_million=1.0, output_per_million=1.0)}
        ),
    )
    usage = TurnUsage(model="x", input_tokens=1_000_000)
    assert wallet.cost_milli(usage) == SPARK_SCALE
