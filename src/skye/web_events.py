"""Durable per-scope web events: snapshot/replay streams and cross-tab invalidation."""

from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

import aiosqlite
import structlog

from .db import Database
from .models import Scope
from .web_contracts import ActivityRecord, RunStatus

log = structlog.get_logger()

RETENTION_SECONDS = 7 * 86_400
MAX_EVENTS_PER_SCOPE = 20_000

SCHEMA = """
CREATE TABLE IF NOT EXISTS web_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope_kind TEXT NOT NULL,
    scope_id INTEGER NOT NULL,
    thread_id TEXT,
    type TEXT NOT NULL,
    payload TEXT NOT NULL,
    created REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS web_events_scope ON web_events(scope_kind, scope_id, id);
CREATE TABLE IF NOT EXISTS web_uploads (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    library_name TEXT NOT NULL,
    name TEXT NOT NULL,
    media_type TEXT NOT NULL,
    size INTEGER NOT NULL,
    created REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS web_uploads_user ON web_uploads(user_id, created);
"""

RUN_LABELS = {
    "accepted": "Queued",
    "running": "Working",
    "completed": "Finished",
    "failed": "Failed",
    "cancelling": "Stopping",
    "cancelled": "Stopped",
    "interrupted": "Interrupted",
}


@dataclass(frozen=True, slots=True)
class StoredEvent:
    id: int
    type: str
    payload: dict[str, Any]
    thread_id: str | None = None


def run_status(row: aiosqlite.Row) -> RunStatus:
    keys = set(row.keys())
    return RunStatus(
        id=row["id"],
        thread_id=row["thread_id"],
        state=row["state"],
        label=RUN_LABELS.get(row["state"], "Working"),
        cost_milli=row["cost_milli"],
        cost_state=row["cost_state"],
        delivery_state=row["delivery_state"] if "delivery_state" in keys else "pending",
        failure=row["failure"] if "failure" in keys else None,
    )


def activity_record(row: aiosqlite.Row) -> ActivityRecord:
    keys = set(row.keys())
    return ActivityRecord(
        sequence=row["sequence"] if "sequence" in keys else row["id"],
        category=row["category"],
        status=row["status"],
        label=row["label"] if "label" in keys else "",
        tool_id=row["tool_id"] if "tool_id" in keys else "",
    )


class WebEventStore:
    """Small durable fan-out. Slow subscribers coalesce and replay from the database."""

    def __init__(self, database: Database) -> None:
        self.database = database
        self._subscribers: defaultdict[tuple[str, int], set[asyncio.Queue[None]]] = defaultdict(set)
        self._writes = 0

    async def install(self, conn: aiosqlite.Connection) -> None:
        """Add the version-three runtime tables. Repeat-safe."""
        for statement in SCHEMA.split(";"):
            if statement.strip():
                await conn.execute(statement)
        self.database.resource_changed = self.publish_resource

    async def publish(
        self,
        scope: Scope,
        event_type: str,
        payload: dict[str, Any],
        *,
        thread_id: str | None = None,
    ) -> int:
        now = time.time()
        async with self.database.transaction() as conn:
            cursor = await conn.execute(
                "INSERT INTO web_events(scope_kind,scope_id,thread_id,type,payload,created) "
                "VALUES(?,?,?,?,?,?)",
                (scope.kind, scope.id, thread_id, event_type, json.dumps(payload), now),
            )
            event_id = int(cursor.lastrowid or 0)
        self._notify(scope)
        self._writes += 1
        if self._writes % 100 == 0:
            await self.prune()
        return event_id

    async def publish_resource(self, scope: Scope, resource: str, resource_id: str) -> None:
        await self.publish(
            scope,
            "resource.changed",
            {
                "type": "resource.changed",
                "resource": resource,
                "resource_id": resource_id[:200],
            },
        )

    async def latest(self, scope: Scope) -> int:
        row = await self.database.fetch_one(
            "SELECT COALESCE(MAX(id),0) FROM web_events WHERE scope_kind=? AND scope_id=?",
            (scope.kind, scope.id),
        )
        return int(row[0]) if row is not None else 0

    async def replay(self, scope: Scope, after: int, limit: int = 500) -> list[StoredEvent]:
        rows = await self.database.fetch_all(
            "SELECT id,type,payload,thread_id FROM web_events "
            "WHERE scope_kind=? AND scope_id=? AND id>? ORDER BY id LIMIT ?",
            (scope.kind, scope.id, max(0, after), min(1000, max(1, limit))),
        )
        return [
            StoredEvent(
                int(row["id"]),
                str(row["type"]),
                json.loads(row["payload"]),
                str(row["thread_id"]) if row["thread_id"] else None,
            )
            for row in rows
        ]

    def subscribe(self, scope: Scope) -> asyncio.Queue[None]:
        queue: asyncio.Queue[None] = asyncio.Queue(maxsize=1)
        self._subscribers[(scope.kind, scope.id)].add(queue)
        return queue

    def unsubscribe(self, scope: Scope, queue: asyncio.Queue[None]) -> None:
        listeners = self._subscribers.get((scope.kind, scope.id))
        if listeners is None:
            return
        listeners.discard(queue)
        if not listeners:
            self._subscribers.pop((scope.kind, scope.id), None)

    def _notify(self, scope: Scope) -> None:
        for queue in tuple(self._subscribers.get((scope.kind, scope.id), ())):
            with suppress(asyncio.QueueFull):
                # The subscriber will replay from its last cursor.
                queue.put_nowait(None)

    async def prune(self) -> None:
        now = time.time()
        await self.database.execute_write(
            "DELETE FROM web_events WHERE created<?", (now - RETENTION_SECONDS,)
        )
        scopes = await self.database.fetch_all(
            "SELECT scope_kind,scope_id,COUNT(*) AS total FROM web_events "
            "GROUP BY scope_kind,scope_id HAVING total>?",
            (MAX_EVENTS_PER_SCOPE,),
        )
        for row in scopes:
            await self.database.execute_write(
                "DELETE FROM web_events WHERE scope_kind=? AND scope_id=? AND id NOT IN "
                "(SELECT id FROM web_events WHERE scope_kind=? AND scope_id=? "
                "ORDER BY id DESC LIMIT ?)",
                (
                    row["scope_kind"],
                    row["scope_id"],
                    row["scope_kind"],
                    row["scope_id"],
                    MAX_EVENTS_PER_SCOPE,
                ),
            )
        await self.database.execute_write(
            "DELETE FROM web_uploads WHERE created<?", (now - RETENTION_SECONDS,)
        )
