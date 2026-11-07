"""One admission/settlement boundary for transport adapters.

The payer lock spans admission, execution and settlement. Unknown/crashed runs are
never automatically replayed: side effects may already have happened.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

import structlog

from .access import AccessService
from .db import Database
from .models import ChatSettings, RequestContext
from .quota import AllowanceError, QuotaService
from .runtime import RunOutput
from .sparks import SparkService
from .threads import Thread


class DuplicateRun(ValueError):
    """A durable request already exists; fetch its state instead of executing again."""


class BusyTurn(ValueError):
    pass


@dataclass(frozen=True)
class Admission:
    payer_id: int
    paid: bool
    complimentary: bool


class TurnService:
    def __init__(
        self, database: Database, access: AccessService, quota: QuotaService, sparks: SparkService
    ) -> None:
        self.database, self.access, self.quota, self.sparks = database, access, quota, sparks
        self._payer_locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._thread_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._tasks: dict[str, asyncio.Task[object]] = {}

    async def execute(
        self,
        thread: Thread,
        context: RequestContext,
        request_key: str,
        operation: Callable[[Admission, str], Awaitable[RunOutput]],
        *,
        settings: ChatSettings | None = None,
    ) -> tuple[RunOutput, Admission, str]:
        if thread.scope != context.scope or not await self.access.allowed(context):
            raise PermissionError("This conversation is unavailable")
        if thread.record.archived:
            raise ValueError("Unarchive this thread before sending")
        lock = self._thread_locks[thread.record.id]
        if lock.locked():
            raise BusyTurn("This thread already has an active request")
        payer = await self.sparks.payer(context)
        async with lock, self._payer_locks[payer]:
            complimentary = await self.quota.complimentary(context, billed_user_id=payer)
            paid = not complimentary and await self.quota.exhausted(context, billed_user_id=payer)
            if paid and not await self.sparks.can_afford(payer):
                raise AllowanceError("Your allowance is used and your Sparks balance is empty")
            admission = Admission(payer, paid, complimentary)
            run_id = uuid4().hex
            # Hash adapter keys so no accidental message body is retained as metadata.
            key = hashlib.sha256(request_key.encode()).hexdigest()
            async with self.database.transaction() as conn:
                previous = await (
                    await conn.execute(
                        "SELECT id FROM canonical_runs WHERE requester_id=? AND request_key=?",
                        (context.user_id, key),
                    )
                ).fetchone()
                if previous:
                    raise DuplicateRun(str(previous[0]))
                await conn.execute(
                    """INSERT INTO canonical_runs
                       (id,thread_id,requester_id,payer_id,request_key,state,funding,settings_snapshot)
                       VALUES(?,?,?,?,?,'running',?,?)""",
                    (
                        run_id,
                        thread.record.id,
                        context.user_id,
                        payer,
                        key,
                        "wallet" if paid else "complimentary" if complimentary else "free",
                        json.dumps(asdict(settings) if settings else {}, separators=(",", ":")),
                    ),
                )
            task = asyncio.current_task()
            assert task is not None
            self._tasks[run_id] = task
            try:
                output = await operation(admission, run_id)
                await self.settle(run_id, admission, output)
                await self._state(run_id, "completed")
                return output, admission, run_id
            except asyncio.CancelledError:
                await self._state(run_id, "cancelled")
                raise
            except BaseException:
                await self._state(run_id, "failed")
                raise
            finally:
                self._tasks.pop(run_id, None)

    async def cancel(self, requester: int, run_id: str) -> bool:
        row = await self.database.fetch_one(
            "SELECT id FROM canonical_runs WHERE id=? AND requester_id=?", (run_id, requester)
        )
        if row is None:
            raise LookupError("Run not found")
        task = self._tasks.get(run_id)
        if task is None:
            return False
        await self._state(run_id, "cancelling")
        task.cancel()
        return True

    async def _state(self, run_id: str, state: str) -> None:
        await self.database.execute_write(
            "UPDATE canonical_runs SET state=?, cost_state=CASE WHEN EXISTS "
            "(SELECT 1 FROM run_settlements WHERE run_id=canonical_runs.id) THEN 'settled' "
            "WHEN ?='completed' THEN cost_state ELSE 'unknown' END WHERE id=?",
            (state, state, run_id),
        )

    async def settle(self, run_id: str, admission: Admission, output: RunOutput) -> None:
        """Usage, wallet ledger and settlement marker commit together exactly once."""
        usage = output.usage
        cost = self.sparks.cost_milli(usage, provider_cost_rub=usage.provider_cost_rub)
        funding: Literal["wallet", "free", "complimentary"] = (
            "wallet" if admission.paid else "complimentary" if admission.complimentary else "free"
        )
        charged_cost = cost if admission.paid else 0
        async with self.database.transaction() as conn:
            previous = await (
                await conn.execute("SELECT 1 FROM run_settlements WHERE run_id=?", (run_id,))
            ).fetchone()
            if previous:
                return
            run = await (
                await conn.execute(
                    "SELECT payer_id,funding FROM canonical_runs WHERE id=?", (run_id,)
                )
            ).fetchone()
            if run is None or run[0] != admission.payer_id or run[1] != funding:
                raise ValueError("Settlement payer does not match the run")
            if admission.paid and cost > 0:
                cursor = await conn.execute(
                    "UPDATE wallets SET balance_milli=balance_milli-? WHERE user_id=? "
                    "AND balance_milli>=?",
                    (cost, admission.payer_id, cost),
                )
                if cursor.rowcount != 1:
                    # Retain unknown cost state for operator reconciliation; never
                    # claim that an executed, unaffordable request was settled.
                    raise AllowanceError("Request cost exceeded the available balance")
                await conn.execute(
                    """INSERT INTO wallet_ledger
                       (user_id,delta_milli,kind,reason,reference,provider_cost_rub,detail)
                       VALUES(?,?,'spend','request',?,?,?)""",
                    (
                        admission.payer_id,
                        -cost,
                        f"run:{run_id}",
                        usage.provider_cost_rub,
                        json.dumps(
                            {
                                "model": usage.model,
                                "in": usage.input_tokens,
                                "out": usage.output_tokens,
                                "cached": usage.cached_tokens,
                                "images": usage.images,
                            },
                            separators=(",", ":"),
                        ),
                    ),
                )
            elif not admission.paid:
                now = datetime.now(UTC)
                day, month = now.strftime("%Y-%m-%d"), now.strftime("%Y-%m")
                await conn.execute(
                    """INSERT INTO usage_counters
                       (user_id,day_utc,month_utc,daily_tokens,monthly_tokens) VALUES(?,?,?,?,?)
                       ON CONFLICT(user_id) DO UPDATE SET
                       daily_tokens=CASE WHEN day_utc=excluded.day_utc THEN daily_tokens ELSE 0 END
                         + excluded.daily_tokens,
                       monthly_tokens=CASE WHEN month_utc=excluded.month_utc
                         THEN monthly_tokens ELSE 0 END + excluded.monthly_tokens,
                       day_utc=excluded.day_utc,month_utc=excluded.month_utc,
                       updated_at=CURRENT_TIMESTAMP""",
                    (admission.payer_id, day, month, output.usage_tokens, output.usage_tokens),
                )
            await conn.execute(
                "INSERT INTO run_settlements VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)",
                (run_id, admission.payer_id, output.usage_tokens, charged_cost, funding),
            )
            await conn.execute(
                "UPDATE canonical_runs SET cost_milli=?,cost_state='settled' WHERE id=?",
                (charged_cost, run_id),
            )
        structlog.get_logger().info(
            "turn_settled",
            kind="billing",
            run_id=run_id,
            user_id=admission.payer_id,
            funding=funding,
            cost_milli=charged_cost,
            tokens=output.usage_tokens,
            model=usage.model,
            images=usage.images,
        )
