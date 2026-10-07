"""Sparks: the in-app currency users top up and spend per request.

Sparks are stored as integer **milli-Sparks** (``milli = sparks * 1000``) so a
single request never needs floating-point money. A wallet is per user; a group
can additionally name one volunteer **sponsor** whose wallet pays for every
request in that chat.
"""

from __future__ import annotations

from dataclasses import dataclass

from .db import Database
from .models import RequestContext, WalletEntry
from .pricing import SPARK_SCALE, PricingService, TurnUsage

SPARKS_NAME = "Sparks"
SPARKS_SYMBOL = "✦"

# Telegram Stars are ~1 Star ≈ 1.2 ₽; Spark prices are retail, the provider cost
# of a run is what the pricing layer reports, and the margin is the difference.
STARS_CURRENCY = "XTR"


@dataclass(frozen=True, slots=True)
class SparkPackage:
    id: str
    name: str
    stars: int
    sparks: int

    @property
    def milli(self) -> int:
        return self.sparks * SPARK_SCALE

    @property
    def rate(self) -> float:
        """Sparks per Star. Larger packages carry a better rate."""

        return self.sparks / self.stars

    @property
    def bonus_percent(self) -> int:
        best = min(package.rate for package in PACKAGES.values())
        return round((self.rate / best - 1) * 100)

    @property
    def button_label(self) -> str:
        bonus = f"  +{self.bonus_percent}%" if self.bonus_percent else ""
        return f"{self.sparks} {SPARKS_SYMBOL} · {self.stars} ⭐{bonus}"

    @property
    def invoice_title(self) -> str:
        return f"{self.sparks} {SPARKS_NAME}"

    @property
    def invoice_description(self) -> str:
        return (
            f"{self.sparks} {SPARKS_NAME} for Skye. Spent on model requests and "
            "pictures. Paid once in Telegram Stars."
        )


PACKAGES: dict[str, SparkPackage] = {
    package.id: package
    for package in (
        SparkPackage(id="spark_100", name="Starter", stars=79, sparks=100),
        SparkPackage(id="spark_350", name="Regular", stars=249, sparks=350),
        SparkPackage(id="spark_800", name="Plus", stars=499, sparks=800),
        SparkPackage(id="spark_2000", name="Pro", stars=1099, sparks=2000),
    )
}


def package_by_id(package_id: str) -> SparkPackage:
    if package_id not in PACKAGES:
        raise SparkError("Unknown top-up package.")
    return PACKAGES[package_id]


def format_milli(milli: int) -> str:
    """Human-readable Sparks without binary-float surprises."""

    sign = "-" if milli < 0 else ""
    milli = abs(milli)
    if milli % SPARK_SCALE == 0:
        return f"{sign}{milli // SPARK_SCALE}"
    sparks = milli / SPARK_SCALE
    text = f"{sparks:.2f}" if sparks >= 1 else f"{sparks:.3f}"
    return sign + text.rstrip("0").rstrip(".")


def format_amount(milli: int) -> str:
    return f"{format_milli(milli)} {SPARKS_SYMBOL}"


class SparkError(ValueError):
    """User-facing Sparks failure."""


class SparkService:
    def __init__(self, database: Database, pricing: PricingService) -> None:
        self.database = database
        self.pricing = pricing

    # -- wallet ------------------------------------------------------------

    async def balance(self, user_id: int) -> int:
        return await self.database.wallet_balance(user_id)

    async def credit(
        self,
        user_id: int,
        milli: int,
        *,
        kind: str = "topup",
        reason: str = "",
        reference: str | None = None,
        provider_cost_rub: float | None = None,
        detail: str | None = None,
    ) -> int:
        if milli <= 0:
            raise SparkError("Top-up amount must be positive.")
        return await self.database.credit_wallet(
            user_id,
            milli,
            kind=kind,
            reason=reason,
            reference=reference,
            provider_cost_rub=provider_cost_rub,
            detail=detail,
        )

    async def charge(
        self,
        user_id: int,
        milli: int,
        *,
        reason: str = "",
        reference: str | None = None,
        provider_cost_rub: float | None = None,
        detail: str | None = None,
    ) -> bool:
        """Debit a wallet atomically. Returns False when the balance is short."""

        if milli <= 0:
            return True
        return await self.database.debit_wallet(
            user_id,
            milli,
            kind="spend",
            reason=reason,
            reference=reference,
            provider_cost_rub=provider_cost_rub,
            detail=detail,
        )

    async def can_afford(self, user_id: int, milli: int = 1) -> bool:
        return await self.balance(user_id) >= milli

    async def ledger(self, user_id: int, limit: int = 10) -> list[WalletEntry]:
        return await self.database.wallet_ledger(user_id, limit=limit)

    def cost_milli(self, usage: TurnUsage, *, provider_cost_rub: float | None = None) -> int:
        return self.pricing.milli(usage, provider_cost_rub=provider_cost_rub)

    # -- sponsor -----------------------------------------------------------

    async def sponsor(self, chat_id: int) -> int | None:
        return await self.database.chat_sponsor(chat_id)

    async def set_sponsor(self, chat_id: int, user_id: int) -> None:
        await self.database.set_chat_sponsor(chat_id, user_id)

    async def clear_sponsor(self, chat_id: int) -> None:
        await self.database.clear_chat_sponsor(chat_id)

    async def payer(self, context: RequestContext) -> int:
        """The wallet that pays for this run: a chat sponsor, else the speaker."""

        if context.chat_type == "private":
            return context.user_id
        sponsor = await self.sponsor(context.chat_id)
        return context.user_id if sponsor is None else sponsor
