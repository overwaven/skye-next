"""One admission/settlement boundary for transport adapters.

The payer lock spans admission, execution and settlement. Unknown/crashed runs are
never automatically replayed: side effects may already have happened.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

import structlog

from .access import AccessService
from .db import Database
from .models import ChatSettings, RequestContext, Scope
from .pricing import TurnUsage
from .quota import AllowanceError, QuotaService
from .runtime import ContextLimitError, RunOutput
from .sparks import SparkService
from .threads import Thread
from .web_events import WebEventStore, run_status


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
        self,
        database: Database,
        access: AccessService,
        quota: QuotaService,
        sparks: SparkService,
        events: WebEventStore | None = None,
    ) -> None:
        self.database, self.access, self.quota, self.sparks = database, access, quota, sparks
        self.events = events
        self._payer_locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._thread_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._tasks: dict[str, asyncio.Task[object]] = {}
        self._thread_tasks: dict[str, asyncio.Task[object]] = {}

    async def execute(
        self,
        thread: Thread,
        context: RequestContext,
        request_key: str,
        operation: Callable[[Admission, str], Awaitable[RunOutput]],
        *,
        settings: ChatSettings | None = None,
        on_admitted: Callable[[str], None] | None = None,
    ) -> tuple[RunOutput, Admission, str]:
        if thread.scope != context.scope:
            raise PermissionError("This conversation is unavailable")
        if thread.record.id in self._thread_tasks:
            raise BusyTurn("This thread already has an active request")
        task = asyncio.current_task()
        assert task is not None
        self._thread_tasks[thread.record.id] = task
        try:
            return await self._execute(
                thread,
                context,
                request_key,
                operation,
                settings=settings,
                on_admitted=on_admitted,
            )
        finally:
            self._thread_tasks.pop(thread.record.id, None)

    async def _execute(
        self,
        thread: Thread,
        context: RequestContext,
        request_key: str,
        operation: Callable[[Admission, str], Awaitable[RunOutput]],
        *,
        settings: ChatSettings | None = None,
        on_admitted: Callable[[str], None] | None = None,
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
            key = hashlib.sha256(request_key.encode()).hexdigest()
            previous = await self.database.fetch_one(
                "SELECT id FROM canonical_runs WHERE requester_id=? AND request_key=?",
                (context.user_id, key),
            )
            if previous:
                raise DuplicateRun(str(previous[0]))
            await self.retry_known_settlements(payer)
            complimentary = await self.quota.complimentary(context, billed_user_id=payer)
            pending = await self.database.fetch_one(
                "SELECT 1 FROM run_reconciliation q JOIN canonical_runs r ON r.id=q.run_id "
                "WHERE r.payer_id=? AND q.resolved=0 AND r.delivery_state!='pending' LIMIT 1",
                (payer,),
            )
            if pending and not complimentary:
                raise AllowanceError(
                    "A previous request needs billing reconciliation. "
                    "No new request was started; contact the operator."
                )
            paid = not complimentary and await self.quota.exhausted(context, billed_user_id=payer)
            if paid and not await self.sparks.can_afford(payer):
                raise AllowanceError("Your allowance is used and your Sparks balance is empty")
            admission = Admission(payer, paid, complimentary)
            run_id = uuid4().hex
            # Hash adapter keys so no accidental message body is retained as metadata.
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
            await self._publish_run(run_id)
            if on_admitted is not None:
                on_admitted(run_id)
            try:
                output = await operation(admission, run_id)
                await self.queue_reconciliation(
                    run_id,
                    "awaiting_settlement" if output.usage_complete else "usage_unknown",
                    output,
                )
                # Do not charge before confirmed delivery. The adapter finishes
                # delivery and then calls settle_delivered with the same output.
                await self._state(run_id, "completed")
                return output, admission, run_id
            except asyncio.CancelledError:
                await self.queue_reconciliation(run_id, "interrupted")
                await self._state(run_id, "cancelled", failure="interrupted")
                raise
            except BaseException as error:
                await self.queue_reconciliation(run_id, "execution_failed")
                await self._state(run_id, "failed", failure=_failure_code(error))
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

    async def cancel_thread(self, scope: Scope, thread_id: str) -> bool:
        row = await self.database.fetch_one(
            "SELECT 1 FROM threads WHERE id=? AND scope_kind=? AND scope_id=?",
            (thread_id, scope.kind, scope.id),
        )
        if row is None:
            raise LookupError("Thread not found")
        task = self._thread_tasks.get(thread_id)
        if task is None:
            return False
        active = await self.database.fetch_one(
            "SELECT id FROM canonical_runs WHERE thread_id=? AND state IN ('accepted','running') "
            "ORDER BY created_at DESC LIMIT 1",
            (thread_id,),
        )
        if active is not None:
            await self._state(str(active[0]), "cancelling")
        task.cancel()
        return True

    async def finish_delivery(self, run_id: str, *, complete: bool) -> None:
        await self.database.execute_write(
            "UPDATE canonical_runs SET delivery_state=CASE "
            "WHEN ? THEN 'complete' WHEN EXISTS(SELECT 1 FROM visible_messages m "
            "WHERE m.thread_id=canonical_runs.thread_id AND json_extract(m.payload,'$.run_id')="
            "canonical_runs.id AND json_extract(m.payload,'$.role')='assistant') "
            "THEN 'partial' ELSE 'failed' END WHERE id=?",
            (complete, run_id),
        )
        await self._publish_run(run_id)

    async def settle_delivered(self, run_id: str, admission: Admission, output: RunOutput) -> None:
        """Charge only after the adapter has confirmed its delivery boundary."""
        row = await self.database.fetch_one(
            "SELECT delivery_state FROM canonical_runs WHERE id=?", (run_id,)
        )
        if row is None:
            raise LookupError("Run not found")
        if row["delivery_state"] == "pending":
            raise ValueError("Delivery is not confirmed yet")
        if not output.usage_complete:
            return
        try:
            await self.settle(run_id, admission, output)
        except AllowanceError:
            await self.queue_reconciliation(run_id, "insufficient_funds", output)

    async def _state(self, run_id: str, state: str, *, failure: str | None = None) -> None:
        await self.database.execute_write(
            "UPDATE canonical_runs SET state=?, failure=COALESCE(?,failure), cost_state=CASE "
            "WHEN EXISTS "
            "(SELECT 1 FROM run_settlements WHERE run_id=canonical_runs.id) THEN 'settled' "
            "WHEN ?='completed' THEN cost_state WHEN cost_milli IS NOT NULL THEN 'pending' "
            "ELSE 'unknown' END WHERE id=?",
            (state, failure, state, run_id),
        )
        await self._publish_run(run_id)

    async def _publish_run(self, run_id: str) -> None:
        if self.events is None:
            return
        row = await self.database.fetch_one(
            "SELECT r.*,t.scope_kind,t.scope_id FROM canonical_runs r "
            "JOIN threads t ON t.id=r.thread_id WHERE r.id=?",
            (run_id,),
        )
        if row is None:
            return
        kind: Literal["user", "chat"] = (
            "user" if str(row["scope_kind"]) == "user" else "chat"
        )
        await self.events.publish(
            Scope(kind, int(row["scope_id"])),
            "run.changed",
            {"type": "run.changed", "run": run_status(row).model_dump()},
            thread_id=str(row["thread_id"]),
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
                    "SELECT payer_id,funding,cost_milli FROM canonical_runs WHERE id=?", (run_id,)
                )
            ).fetchone()
            if run is None or run[0] != admission.payer_id or run[1] != funding:
                raise ValueError("Settlement payer does not match the run")
            delivery = await (
                await conn.execute(
                    "SELECT delivery_state FROM canonical_runs WHERE id=?", (run_id,)
                )
            ).fetchone()
            if delivery is None or delivery[0] == "pending":
                raise ValueError("Wait for delivery confirmation before settlement")
            if not output.usage_complete:
                raise ValueError("Incomplete usage requires explicit reconciliation")
            if run[2] is not None:
                charged_cost = int(run[2])
                cost = charged_cost if admission.paid else 0
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
            await conn.execute(
                "UPDATE run_reconciliation SET resolved=1,updated=? WHERE run_id=?",
                (datetime.now(UTC).timestamp(), run_id),
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

    async def queue_reconciliation(
        self, run_id: str, reason: str, output: RunOutput | None = None
    ) -> None:
        if reason not in {
            "awaiting_settlement",
            "usage_unknown",
            "insufficient_funds",
            "execution_failed",
            "interrupted",
        }:
            raise ValueError("Invalid reconciliation reason")
        usage = (
            json.dumps(
                {
                    "usage": asdict(output.usage),
                    "tokens": output.usage_tokens,
                    "complete": output.usage_complete,
                }
            )
            if output is not None
            else None
        )
        async with self.database.transaction() as conn:
            await conn.execute(
                """INSERT INTO run_reconciliation
                (run_id,reason,usage_json,updated) SELECT ?,?,?,?
                WHERE NOT EXISTS (SELECT 1 FROM run_settlements WHERE run_id=?)
                ON CONFLICT(run_id) DO UPDATE SET reason=excluded.reason,
                usage_json=COALESCE(excluded.usage_json,run_reconciliation.usage_json),
                updated=excluded.updated WHERE run_reconciliation.resolved=0""",
                (run_id, reason, usage, datetime.now(UTC).timestamp(), run_id),
            )
            if output is not None:
                row = await (
                    await conn.execute("SELECT funding FROM canonical_runs WHERE id=?", (run_id,))
                ).fetchone()
                if row is None:
                    raise LookupError("Run not found")
                quoted = (
                    self.sparks.cost_milli(
                        output.usage, provider_cost_rub=output.usage.provider_cost_rub
                    )
                    if row[0] == "wallet"
                    else 0
                )
                await conn.execute(
                    "UPDATE canonical_runs SET cost_milli=?,cost_state=? WHERE id=? "
                    "AND NOT EXISTS (SELECT 1 FROM run_settlements WHERE run_id=?)",
                    (
                        quoted if output.usage_complete else None,
                        "pending" if output.usage_complete else "unknown",
                        run_id,
                        run_id,
                    ),
                )

    async def retry_known_settlements(self, payer_id: int) -> None:
        rows = await self.database.fetch_all(
            "SELECT q.run_id,q.usage_json,r.funding,r.delivery_state FROM run_reconciliation q "
            "JOIN canonical_runs r ON r.id=q.run_id WHERE r.payer_id=? AND q.resolved=0 "
            "AND q.usage_json IS NOT NULL AND r.delivery_state!='pending' "
            "ORDER BY r.created_at,r.id",
            (payer_id,),
        )
        for row in rows:
            data = json.loads(row["usage_json"])
            if not data["complete"]:
                continue
            output = RunOutput(
                "", (), usage_tokens=data["tokens"], usage=TurnUsage(**data["usage"])
            )
            try:
                await self.settle(
                    row["run_id"],
                    Admission(
                        payer_id, row["funding"] == "wallet", row["funding"] == "complimentary"
                    ),
                    output,
                )
            except AllowanceError:
                return

    async def reconcile(
        self, run_id: str, usage: TurnUsage, *, tokens: int, cost_milli: int, evidence: str
    ) -> None:
        """Operator-only explicit evidence. Never query a provider or infer unknown usage."""
        if (
            type(tokens) is not int
            or tokens < 0
            or type(cost_milli) is not int
            or not 0 <= cost_milli <= 10**12
            or re.fullmatch(r"[A-Za-z0-9._:/-]{1,200}", evidence) is None
        ):
            raise ValueError(
                "Use nonnegative integer totals and an opaque provider evidence reference"
            )
        if any(
            type(value) is not int or value < 0
            for value in (
                usage.input_tokens,
                usage.output_tokens,
                usage.cached_tokens,
                usage.reasoning_tokens,
                usage.images,
                usage.connector_calls,
            )
        ):
            raise ValueError("Invalid usage breakdown")
        if usage.provider_cost_rub is not None and (
            not math.isfinite(usage.provider_cost_rub) or usage.provider_cost_rub < 0
        ):
            raise ValueError("Invalid provider cost")
        if tokens != usage.total_tokens or usage.cached_tokens > usage.input_tokens:
            raise ValueError("Usage totals must match the supplied breakdown")
        row = await self.database.fetch_one(
            "SELECT r.payer_id,r.funding,q.resolved,q.evidence FROM canonical_runs r "
            "JOIN run_reconciliation q ON q.run_id=r.id WHERE r.id=?",
            (run_id,),
        )
        if row is None:
            raise LookupError("Reconciliation item not found")
        if row["resolved"]:
            if row["evidence"] != evidence:
                raise ValueError("Already resolved; do not rewrite settled accounting")
            return
        funding = row["funding"]
        output = RunOutput("", (), usage_tokens=tokens, usage=usage)
        async with self.database.transaction() as conn:
            await conn.execute(
                "UPDATE run_reconciliation SET evidence=?,usage_json=?,updated=? "
                "WHERE run_id=? AND resolved=0",
                (
                    evidence,
                    json.dumps({"usage": asdict(usage), "tokens": tokens, "complete": True}),
                    datetime.now(UTC).timestamp(),
                    run_id,
                ),
            )
            await conn.execute(
                "UPDATE canonical_runs SET cost_milli=?,cost_state='pending' WHERE id=?",
                (cost_milli if funding == "wallet" else 0, run_id),
            )
        await self.settle(
            run_id,
            Admission(row["payer_id"], funding == "wallet", funding == "complimentary"),
            output,
        )

    async def record_provider_receipt(
        self, run_id: str, reference: str, usage: TurnUsage | None = None
    ) -> None:
        if re.fullmatch(r"[A-Za-z0-9._:-]{1,200}", reference) is None:
            return
        await self.database.execute_write(
            "INSERT INTO run_provider_receipts VALUES(?,?,?) "
            "ON CONFLICT(run_id,provider_ref) DO UPDATE SET "
            "usage_json=COALESCE(excluded.usage_json,run_provider_receipts.usage_json)",
            (run_id, reference, json.dumps(asdict(usage)) if usage is not None else None),
        )


def _failure_code(error: BaseException) -> str:
    """Map provider/runtime failures to a safe, non-sensitive run reason."""
    if isinstance(error, ContextLimitError):
        return "context"
    name = type(error).__name__.lower()
    if "moderation" in name:
        return "moderation"
    if isinstance(error, AllowanceError):
        return "quota"
    return "provider"
