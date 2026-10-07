"""Telegram Stars top-ups for Sparks and the account panel.

Stars are only a payment rail here: a one-time payment credits the user's
Sparks wallet. There is no subscription. Spending is metered per request through
:mod:`skye.sparks`.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
    RefundedPayment,
    SuccessfulPayment,
)

from .access import AccessService
from .db import Database
from .models import RequestContext, WalletEntry
from .rich import RichMessages
from .sparks import (
    PACKAGES,
    SPARKS_NAME,
    SPARKS_SYMBOL,
    STARS_CURRENCY,
    SparkPackage,
    SparkService,
    format_amount,
    package_by_id,
)

log = structlog.get_logger()

LEDGER_LIMIT = 6


class BillingError(ValueError):
    """User-facing Stars billing failure."""


def encode_payload(package_id: str, user_id: int, secret: str) -> str:
    body = f"{package_id}:{user_id}"
    signature = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{body}:{signature}"


def decode_payload(payload: str, secret: str) -> tuple[SparkPackage, int]:
    parts = payload.split(":")
    if len(parts) != 3:
        raise BillingError("This invoice is not valid.")
    package_id, raw_user, signature = parts
    body = f"{package_id}:{raw_user}"
    expected = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()[:16]
    if not hmac.compare_digest(expected, signature):
        raise BillingError("This invoice is not valid.")
    try:
        user_id = int(raw_user)
    except ValueError as error:
        raise BillingError("This invoice is not valid.") from error
    return package_by_id(package_id), user_id


class BillingService:
    def __init__(self, database: Database, sparks: SparkService, secret: str) -> None:
        self.database = database
        self.sparks = sparks
        self.secret = secret

    def payload(self, package: SparkPackage, user_id: int) -> str:
        return encode_payload(package.id, user_id, self.secret)

    def validate_topup(
        self,
        *,
        user_id: int,
        currency: str,
        total_amount: int,
        invoice_payload: str,
    ) -> SparkPackage:
        if currency != STARS_CURRENCY:
            raise BillingError(f"{SPARKS_NAME} are paid in Telegram Stars.")
        package, payload_user = decode_payload(invoice_payload, self.secret)
        if payload_user != user_id:
            raise BillingError("This invoice is for a different Telegram account.")
        if total_amount != package.stars:
            raise BillingError("This invoice no longer matches the package.")
        return package

    async def apply_topup(self, user_id: int, payment: SuccessfulPayment) -> SparkPackage:
        package = self.validate_topup(
            user_id=user_id,
            currency=payment.currency,
            total_amount=payment.total_amount,
            invoice_payload=payment.invoice_payload,
        )
        if await self.database.spark_topup(payment.telegram_payment_charge_id):
            return package
        recorded = await self.database.record_spark_topup(
            telegram_payment_charge_id=payment.telegram_payment_charge_id,
            user_id=user_id,
            package_id=package.id,
            stars=payment.total_amount,
            sparks_milli=package.milli,
        )
        if not recorded:
            return package
        await self.sparks.credit(
            user_id,
            package.milli,
            kind="topup",
            reason="stars",
            reference=payment.telegram_payment_charge_id,
        )
        log.info("sparks_topup", user_id=user_id, package=package.id, stars=payment.total_amount)
        return package

    async def apply_refund(self, user_id: int, payment: RefundedPayment) -> None:
        if not await self.database.spark_topup(payment.telegram_payment_charge_id):
            return
        paid = await self.database.wallet_balance(user_id)
        # Reverse what we can without letting a wallet go negative.
        for entry in await self.sparks.ledger(user_id, limit=1):
            if entry.reference == payment.telegram_payment_charge_id and entry.kind == "topup":
                amount = min(entry.delta_milli, paid)
                if amount > 0:
                    await self.sparks.charge(
                        user_id,
                        amount,
                        reason="refund",
                        reference=payment.telegram_payment_charge_id,
                    )
                return


class AccountPanel:
    def __init__(
        self,
        billing: BillingService,
        sparks: SparkService,
        access: AccessService,
        rich: RichMessages,
        bot: Bot,
    ) -> None:
        self.billing = billing
        self.sparks = sparks
        self.access = access
        self.rich = rich
        self.bot = bot

    async def show(
        self,
        message: Message,
        context: RequestContext,
        *,
        edit: bool = False,
        notice: str | None = None,
    ) -> None:
        if await self._banned(context):
            banned = self.rich.prompt("Account", "This account is banned.")
            await self._render(message, context, banned, None, edit)
            return
        owner = self.access.is_owner(context.user_id)
        if context.chat_type != "private":
            await self._show_group(message, context, owner=owner, notice=notice, edit=edit)
            return
        balance = await self.sparks.balance(context.user_id)
        ledger = await self.sparks.ledger(context.user_id, limit=LEDGER_LIMIT)
        settings = await self.database_settings(context)
        rows = [(entry, _ledger_label(entry)) for entry in ledger]
        content = self.rich.sparks_account(
            balance=balance,
            entries=rows,
            show_spend=settings,
            owner=owner,
            notice=notice,
        )
        await self._render(message, context, content, self._private_keyboard(settings), edit)

    async def show_checkout(
        self, message: Message, context: RequestContext, package_id: str
    ) -> None:
        package = package_by_id(package_id)
        link = await self._invoice_link(package, context.user_id)
        await self.rich.edit(
            message,
            self.rich.topup_checkout(
                name=package.name,
                sparks=package.sparks,
                stars=package.stars,
                bonus=package.bonus_percent,
            ),
            reply_markup=self._checkout_keyboard(link),
        )

    async def handle_callback(
        self, message: Message, context: RequestContext, action: list[str]
    ) -> None:
        if await self._banned(context):
            raise BillingError("This account is banned.")
        if action == ["home"]:
            await self.show(message, context, edit=True)
        elif len(action) == 2 and action[0] == "pack":
            await self.show_checkout(message, context, action[1])
        elif action == ["spend", "toggle"]:
            scope = context.scope
            current = await self.database_settings(context)
            await self.billing.database.set_sparks_display(scope, not current)
            state = "off" if current else "on"
            await self.show(message, context, edit=True, notice=f"Spend display is {state}.")
        elif action == ["sponsor", "on"]:
            if context.chat_type == "private":
                raise BillingError("Sponsorship is a group feature.")
            await self.sparks.set_sponsor(context.chat_id, context.user_id)
            await self.show(
                message,
                context,
                edit=True,
                notice="You now pay for every request in this chat.",
            )
        elif action == ["sponsor", "off"]:
            sponsor = await self.sparks.sponsor(context.chat_id)
            if sponsor != context.user_id:
                raise BillingError("Only the current sponsor can stop.")
            await self.sparks.clear_sponsor(context.chat_id)
            await self.show(message, context, edit=True, notice="You are no longer the sponsor.")
        else:
            raise BillingError("Unknown account action.")

    async def pre_checkout(self, query: PreCheckoutQuery) -> None:
        try:
            self.billing.validate_topup(
                user_id=query.from_user.id,
                currency=query.currency,
                total_amount=query.total_amount,
                invoice_payload=query.invoice_payload,
            )
        except BillingError as error:
            await query.answer(ok=False, error_message=str(error)[:200])
            return
        await query.answer(ok=True)

    async def successful_payment(self, message: Message, context: RequestContext) -> None:
        payment = message.successful_payment
        if payment is None:
            return
        try:
            package = await self.billing.apply_topup(context.user_id, payment)
        except BillingError as error:
            log.warning("topup_rejected", user_id=context.user_id, error=str(error)[:200])
            await self.rich.send(message, str(error))
            return
        balance = await self.sparks.balance(context.user_id)
        await self.rich.send(
            message,
            self.rich.prompt(
                f"{SPARKS_SYMBOL} {SPARKS_NAME}",
                f"Added {package.sparks} {SPARKS_SYMBOL}. Balance: {format_amount(balance)}.",
            ),
        )

    async def refunded_payment(self, message: Message, context: RequestContext) -> None:
        payment = message.refunded_payment
        if payment is None:
            return
        await self.billing.apply_refund(context.user_id, payment)
        await self.rich.send(
            message,
            f"That Stars payment was refunded. Your {SPARKS_NAME} balance was adjusted.",
        )

    async def paysupport(self, message: Message) -> None:
        await self.rich.send(
            message,
            self.rich.prompt(
                "Payment support",
                "Skye handles Telegram Stars billing here. Telegram support cannot help "
                "with these purchases. Describe the issue in this private chat.",
            ),
        )

    async def terms(self, message: Message) -> None:
        await self.rich.send(message, self.rich.sparks_terms())

    # -- helpers -----------------------------------------------------------

    async def database_settings(self, context: RequestContext) -> bool:
        current = await self.billing.database.get_settings(context.scope)
        return current.sparks_display

    async def _show_group(
        self,
        message: Message,
        context: RequestContext,
        *,
        owner: bool,
        notice: str | None,
        edit: bool,
    ) -> None:
        if not await self.access.allowed(context):
            raise BillingError("Skye is not enabled in this chat.")
        balance = await self.sparks.balance(context.user_id)
        sponsor = await self.sparks.sponsor(context.chat_id)
        content = self.rich.sparks_group(
            balance=balance,
            sponsor_id=sponsor,
            user_id=context.user_id,
            owner=owner,
            notice=notice,
        )
        keyboard = self._group_keyboard(sponsor, context.user_id)
        await self._render(message, context, content, keyboard, edit)

    async def _render(
        self,
        message: Message,
        context: RequestContext,
        content: Any,
        markup: InlineKeyboardMarkup | None,
        edit: bool,
    ) -> None:
        if edit:
            await self.rich.edit(message, content, reply_markup=markup)
        else:
            await self.rich.send(message, content, reply_markup=markup)

    async def _banned(self, context: RequestContext) -> bool:
        if self.access.is_owner(context.user_id):
            return False
        return await self.billing.database.access_effect(context.scope) == "ban"

    async def _invoice_link(self, package: SparkPackage, user_id: int) -> str:
        prices = [LabeledPrice(label=package.name, amount=package.stars)]
        payload = self.billing.payload(package, user_id)
        try:
            return await self.bot.create_invoice_link(
                title=package.invoice_title,
                description=package.invoice_description,
                payload=payload,
                currency=STARS_CURRENCY,
                prices=prices,
            )
        except TelegramBadRequest as error:
            raise BillingError("Stars payments are not available on this bot yet.") from error

    @staticmethod
    def _private_keyboard(show_spend: bool) -> InlineKeyboardMarkup:
        rows: list[list[InlineKeyboardButton]] = [
            [
                InlineKeyboardButton(
                    text=package.button_label, callback_data=f"acct:pack:{package.id}"
                )
            ]
            for package in PACKAGES.values()
        ]
        rows.append(
            [
                InlineKeyboardButton(
                    text="Hide spend" if show_spend else "Show spend",
                    callback_data="acct:spend:toggle",
                )
            ]
        )
        return InlineKeyboardMarkup(inline_keyboard=rows)

    @staticmethod
    def _group_keyboard(sponsor: int | None, user_id: int) -> InlineKeyboardMarkup:
        if sponsor == user_id:
            button = InlineKeyboardButton(text="Stop sponsoring", callback_data="acct:sponsor:off")
        else:
            button = InlineKeyboardButton(text="Sponsor this chat", callback_data="acct:sponsor:on")
        return InlineKeyboardMarkup(inline_keyboard=[[button]])

    @staticmethod
    def _checkout_keyboard(link: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Pay with Stars", url=link)],
                [InlineKeyboardButton(text="‹ Back", callback_data="acct:home")],
            ]
        )


def _ledger_label(entry: WalletEntry) -> str:
    if entry.kind == "topup":
        return "Top-up"
    if entry.kind == "bonus":
        return "Bonus"
    if entry.kind == "refund":
        return "Refund"
    if entry.reason:
        return entry.reason.replace("_", " ")
    return entry.kind
