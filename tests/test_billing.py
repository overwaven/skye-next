from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from aiogram.types import RefundedPayment, SuccessfulPayment

from skye.access import AccessService
from skye.billing import (
    AccountPanel,
    BillingError,
    BillingService,
    decode_payload,
    encode_payload,
)
from skye.db import Database
from skye.models import RequestContext, Scope
from skye.pricing import PricingService
from skye.quota import QuotaService
from skye.sparks import PACKAGES, SPARK_SCALE, SparkService


@pytest.fixture
async def database(tmp_path: Path):
    value = Database(tmp_path / "skye.db", "gpt-5.6-luna", "medium")
    await value.open()
    try:
        yield value
    finally:
        await value.close()


def sparks(database: Database) -> SparkService:
    return SparkService(database, PricingService(sparks_per_rub=1.0))


def service(database: Database) -> BillingService:
    return BillingService(database, sparks(database), "secret")


def payment(
    billing: BillingService,
    package_id: str,
    user_id: int,
    *,
    charge_id: str = "tg_charge_1",
    stars: int | None = None,
) -> SuccessfulPayment:
    package = PACKAGES[package_id]
    return SuccessfulPayment(
        currency="XTR",
        total_amount=stars if stars is not None else package.stars,
        invoice_payload=billing.payload(package, user_id),
        telegram_payment_charge_id=charge_id,
        provider_payment_charge_id="",
        subscription_expiration_date=None,
        is_recurring=None,
        is_first_recurring=None,
    )


def test_package_catalog_rewards_bigger_packages() -> None:
    rates = [package.rate for package in PACKAGES.values()]
    assert rates == sorted(rates)
    assert PACKAGES["spark_100"].bonus_percent == 0
    assert PACKAGES["spark_2000"].bonus_percent > 0
    assert all(len(package.invoice_title) <= 32 for package in PACKAGES.values())
    assert all(len(package.invoice_description) <= 255 for package in PACKAGES.values())
    assert all(package.milli == package.sparks * SPARK_SCALE for package in PACKAGES.values())


def test_invoice_payload_is_signed_and_bound_to_the_user() -> None:
    payload = encode_payload("spark_100", 42, "secret")
    package, user_id = decode_payload(payload, "secret")
    assert package.id == "spark_100"
    assert user_id == 42

    with pytest.raises(BillingError):
        decode_payload("spark_100:42:deadbeefdeadbeef", "secret")
    with pytest.raises(BillingError):
        decode_payload("missing:42:" + payload.rsplit(":", 1)[1], "secret")


def test_validate_topup_checks_currency_amount_and_user(database: Database) -> None:
    billing = service(database)
    package = PACKAGES["spark_350"]
    payload = billing.payload(package, 42)

    assert billing.validate_topup(
        user_id=42, currency="XTR", total_amount=package.stars, invoice_payload=payload
    ).id == "spark_350"

    with pytest.raises(BillingError):
        billing.validate_topup(
            user_id=42, currency="USD", total_amount=package.stars, invoice_payload=payload
        )
    with pytest.raises(BillingError):
        billing.validate_topup(
            user_id=42, currency="XTR", total_amount=1, invoice_payload=payload
        )
    with pytest.raises(BillingError):
        billing.validate_topup(
            user_id=7, currency="XTR", total_amount=package.stars, invoice_payload=payload
        )


async def test_topup_credits_the_wallet_once(database: Database) -> None:
    billing = service(database)
    wallet = sparks(database)

    first = await billing.apply_topup(42, payment(billing, "spark_100", 42))
    assert first.id == "spark_100"
    assert await wallet.balance(42) == PACKAGES["spark_100"].milli

    # A duplicate charge id is idempotent.
    await billing.apply_topup(42, payment(billing, "spark_100", 42))
    assert await wallet.balance(42) == PACKAGES["spark_100"].milli

    entries = await wallet.ledger(42)
    assert [entry.kind for entry in entries] == ["topup"]
    assert entries[0].reference == "tg_charge_1"


async def test_refund_reverses_a_topup(database: Database) -> None:
    billing = service(database)
    wallet = sparks(database)
    await billing.apply_topup(42, payment(billing, "spark_100", 42))

    await billing.apply_refund(
        42,
        RefundedPayment(
            currency="XTR",
            total_amount=PACKAGES["spark_100"].stars,
            invoice_payload=billing.payload(PACKAGES["spark_100"], 42),
            telegram_payment_charge_id="tg_charge_1",
            provider_payment_charge_id="",
        ),
    )

    assert await wallet.balance(42) == 0


class RichStub:
    def __init__(self) -> None:
        self.sent: list[str] = []
        self.edits: list[Any] = []

    async def send(self, message: Any, content: Any, reply_markup: Any = None) -> None:
        self.sent.append(str(content))

    async def edit(self, message: Any, content: Any, reply_markup: Any = None) -> None:
        self.edits.append(content)

    def prompt(self, title: str, body: Any) -> str:
        return f"{title}: {body}"

    def sparks_account(self, **kwargs: Any) -> dict[str, Any]:
        return {"kind": "private", **kwargs}

    def sparks_group(self, **kwargs: Any) -> dict[str, Any]:
        return {"kind": "group", **kwargs}

    def topup_checkout(self, **kwargs: Any) -> dict[str, Any]:
        return {"kind": "checkout", **kwargs}


async def test_sponsor_callback_sets_and_clears(database: Database) -> None:
    rich = RichStub()
    wallet = sparks(database)
    access = AccessService(database, frozenset({1}))
    panel = AccountPanel(
        service(database), wallet, access,
        cast(Any, rich), cast(Any, AsyncMock()), QuotaService(database, access),
    )
    await database.set_access(Scope("chat", -100), "allow", created_by=1)
    context = RequestContext(-100, "supergroup", user_id=42)
    message = cast(Any, object())

    await panel.handle_callback(message, context, ["sponsor", "on"])
    assert await wallet.sponsor(-100) == 42

    await panel.handle_callback(message, context, ["sponsor", "off"])
    assert await wallet.sponsor(-100) is None
