"""Free allowance gate.

Every account gets a small free daily and monthly token allowance. Past it, runs
are paid for with Sparks (see :mod:`skye.sparks`). The billed user is the chat
sponsor when one is set, otherwise the speaker.
"""

from __future__ import annotations

from datetime import datetime

from .access import AccessService
from .db import Database
from .models import RequestContext, Scope

FREE_DAILY = 20_000
FREE_MONTHLY = 400_000

DAILY_LIMIT_COPY = "The free daily allowance is used. Top up Sparks in /account to keep going."
MONTHLY_LIMIT_COPY = (
    "The free monthly allowance is used. Top up Sparks in /account to keep going."
)


class AllowanceError(Exception):
    """The user is over the free allowance and has no Sparks to continue."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class QuotaService:
    def __init__(self, database: Database, access: AccessService) -> None:
        self.database = database
        self.access = access

    async def complimentary(
        self, context: RequestContext, *, billed_user_id: int | None = None
    ) -> bool:
        user_id = self._billed_user_id(context, billed_user_id)
        if self.access.is_owner(user_id):
            return True
        if await self.database.access_effect(Scope("user", user_id)) == "allow":
            return True
        return await self.database.access_effect(context.scope) == "allow"

    async def exhausted(
        self,
        context: RequestContext,
        *,
        billed_user_id: int | None = None,
        now: datetime | None = None,
    ) -> bool:
        user_id = self._billed_user_id(context, billed_user_id)
        daily, monthly = await self.database.usage_totals(user_id, now=now)
        return daily >= FREE_DAILY or monthly >= FREE_MONTHLY

    async def record(
        self,
        context: RequestContext,
        tokens: int,
        *,
        billed_user_id: int | None = None,
        now: datetime | None = None,
    ) -> None:
        if tokens <= 0:
            return
        await self.database.add_usage(
            self._billed_user_id(context, billed_user_id), tokens, now=now
        )

    @staticmethod
    def _billed_user_id(context: RequestContext, billed_user_id: int | None) -> int:
        return context.user_id if billed_user_id is None else billed_user_id
