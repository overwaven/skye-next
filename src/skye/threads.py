"""Canonical ownership and thread storage. Legacy sessions are referenced, never copied."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import uuid4

import aiosqlite

from .db import Database
from .models import Scope
from .web_auth import SCHEMA as AUTH_SCHEMA
from .web_contracts import ProjectRecord, ThreadRecord, VisibleMessage

# Applied only by the explicit migration command, not by Database.open().
SCHEMA = """
CREATE TABLE IF NOT EXISTS web_schema (version INTEGER PRIMARY KEY);
CREATE TABLE IF NOT EXISTS threads (
    id TEXT PRIMARY KEY,
    scope_kind TEXT NOT NULL CHECK(scope_kind IN ('user', 'chat')),
    scope_id INTEGER NOT NULL,
    project_id TEXT REFERENCES telegram_projects(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    session_ref TEXT NOT NULL UNIQUE,
    default_instructions TEXT NOT NULL DEFAULT '',
    archived INTEGER NOT NULL DEFAULT 0,
    revision INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS threads_owner ON threads(scope_kind, scope_id, id);
CREATE TABLE IF NOT EXISTS telegram_thread_bindings (
    project_id TEXT PRIMARY KEY REFERENCES telegram_projects(id) ON DELETE CASCADE,
    initial_thread_id TEXT NOT NULL REFERENCES threads(id),
    selected_thread_id TEXT NOT NULL REFERENCES threads(id)
);
CREATE TABLE IF NOT EXISTS group_thread_bindings (
    chat_id INTEGER NOT NULL,
    topic_id INTEGER NOT NULL,
    thread_id TEXT NOT NULL REFERENCES threads(id),
    PRIMARY KEY(chat_id, topic_id)
);
CREATE TABLE IF NOT EXISTS automation_thread_bindings (
    automation_id TEXT PRIMARY KEY REFERENCES automations(id) ON DELETE CASCADE,
    thread_id TEXT NOT NULL REFERENCES threads(id)
);
CREATE TABLE IF NOT EXISTS visible_messages (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL REFERENCES threads(id),
    sequence INTEGER NOT NULL,
    payload TEXT NOT NULL,
    receipt TEXT UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(thread_id, sequence)
);
CREATE TABLE IF NOT EXISTS canonical_runs (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL REFERENCES threads(id),
    requester_id INTEGER NOT NULL,
    payer_id INTEGER NOT NULL,
    request_key TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN
      ('accepted','running','completed','failed','cancelling','cancelled','interrupted')),
    cost_milli INTEGER,
    cost_state TEXT NOT NULL DEFAULT 'pending',
    funding TEXT NOT NULL CHECK(funding IN ('free','complimentary','wallet')),
    settings_snapshot TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(requester_id, request_key)
);
CREATE TABLE IF NOT EXISTS run_settlements (
    run_id TEXT PRIMARY KEY REFERENCES canonical_runs(id),
    payer_id INTEGER NOT NULL,
    tokens INTEGER NOT NULL,
    cost_milli INTEGER NOT NULL,
    funding TEXT NOT NULL CHECK(funding IN ('free','complimentary','wallet')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


@dataclass(frozen=True)
class Thread:
    record: ThreadRecord
    scope: Scope
    session_ref: str
    instructions: str


class ThreadStore:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def require_schema(self) -> None:
        try:
            row = await self.database.fetch_one("SELECT version FROM web_schema WHERE version = 1")
        except aiosqlite.OperationalError:
            raise RuntimeError(
                "Run the backed-up canonical migration before enabling web"
            ) from None
        if row is None:
            raise RuntimeError("Run the backed-up canonical migration before enabling web")

    async def migrate(self) -> dict[str, int]:
        """Run offline against a backed-up database. Repeat-safe, additive cutover."""
        # DDL is additive; data + version commit atomically below. An interrupted
        # schema installation can safely be retried. Never drop a legacy table.
        await self.database.execute_script(SCHEMA + AUTH_SCHEMA)
        await self.database._ensure_column(
            "telegram_projects", "revision", "INTEGER NOT NULL DEFAULT 1"
        )
        await self.database.conn.commit()
        counts = {"projects": 0, "private": 0, "groups": 0, "automations": 0}
        async with self.database.transaction() as conn:
            await conn.execute("""CREATE TRIGGER IF NOT EXISTS project_revision
                AFTER UPDATE OF name,emoji,instructions ON telegram_projects
                BEGIN UPDATE telegram_projects SET revision=OLD.revision+1 WHERE id=NEW.id; END""")
            rows = await (await conn.execute("SELECT * FROM telegram_projects")).fetchall()
            for row in rows:
                if await self._bound(conn, str(row["id"])):
                    continue
                await self._import_project(conn, row)
                counts["projects"] += 1
            rows = await (await conn.execute("SELECT * FROM conversations")).fetchall()
            for row in rows:
                chat_id, topic_id = int(row["chat_id"]), int(row["thread_id"])
                ref = str(row["openai_conversation_id"])
                existing = await (
                    await conn.execute(
                        "SELECT id, scope_kind, scope_id FROM threads WHERE session_ref = ?", (ref,)
                    )
                ).fetchone()
                if chat_id > 0:
                    # A lazy-migrated default and its old lookup may coexist.
                    if topic_id != 0:
                        raise ValueError(
                            "Unexpected private topic: migration needs operator review"
                        )
                    if existing is not None:
                        if existing["scope_kind"] != "user" or existing["scope_id"] != chat_id:
                            raise ValueError("Session reference crosses owners")
                        continue
                    await self._insert(conn, Scope("user", chat_id), None, "Skye", ref)
                    counts["private"] += 1
                else:
                    bound = await (
                        await conn.execute(
                            "SELECT thread_id FROM group_thread_bindings "
                            "WHERE chat_id=? AND topic_id=?",
                            (chat_id, topic_id),
                        )
                    ).fetchone()
                    if bound:
                        continue
                    if existing is not None:
                        raise ValueError("Group session reference is already bound")
                    thread_id = await self._insert(
                        conn, Scope("chat", chat_id), None, "Telegram conversation", ref
                    )
                    await conn.execute(
                        "INSERT INTO group_thread_bindings VALUES (?, ?, ?)",
                        (chat_id, topic_id, thread_id),
                    )
                    counts["groups"] += 1
            # Pin old private automations once to the then-selected project/default.
            rows = await (
                await conn.execute("SELECT * FROM automations WHERE scope_kind='user'")
            ).fetchall()
            for row in rows:
                bound = await (
                    await conn.execute(
                        "SELECT 1 FROM automation_thread_bindings WHERE automation_id=?",
                        (row["id"],),
                    )
                ).fetchone()
                if bound:
                    continue
                target = await (
                    await conn.execute(
                        """SELECT b.selected_thread_id FROM telegram_thread_bindings b
                       JOIN telegram_projects p ON p.id=b.project_id
                       LEFT JOIN user_settings s ON s.user_id=p.user_id
                       WHERE p.user_id=? ORDER BY (p.id=s.active_telegram_project_id) DESC,
                       (p.kind='skye') DESC, p.id LIMIT 1""",
                        (row["scope_id"],),
                    )
                ).fetchone()
                if target is None:
                    raise ValueError("Private automation has no resolvable thread")
                await conn.execute(
                    "INSERT INTO automation_thread_bindings VALUES (?, ?)", (row["id"], target[0])
                )
                counts["automations"] += 1
            await conn.execute("INSERT OR IGNORE INTO web_schema VALUES (1)")
        return counts

    @staticmethod
    async def _bound(conn: aiosqlite.Connection, project_id: str) -> str | None:
        row = await (
            await conn.execute(
                "SELECT selected_thread_id FROM telegram_thread_bindings WHERE project_id=?",
                (project_id,),
            )
        ).fetchone()
        return str(row[0]) if row else None

    async def _import_project(self, conn: aiosqlite.Connection, row: aiosqlite.Row) -> str:
        ProjectRecord(
            id=row["id"],
            name=row["name"],
            instructions=row["instructions"],
            revision=row["revision"],
        )
        project_id = str(row["id"])
        scope = Scope("user", int(row["user_id"]))
        ref = row["openai_conversation_id"]
        if not ref and row["kind"] == "skye":
            old = await (
                await conn.execute(
                    "SELECT openai_conversation_id FROM conversations "
                    "WHERE chat_id=? AND thread_id=0",
                    (scope.id,),
                )
            ).fetchone()
            ref = old[0] if old else None
        ref = str(ref or f"telegram-project:{project_id}")
        existing = await (
            await conn.execute(
                "SELECT id, scope_kind, scope_id, project_id FROM threads WHERE session_ref=?",
                (ref,),
            )
        ).fetchone()
        custom = row["kind"] == "custom"
        if existing:
            if custom or existing["scope_kind"] != "user" or existing["scope_id"] != scope.id:
                raise ValueError("Ambiguous project session reference")
            thread_id = str(existing["id"])
        else:
            thread_id = await self._insert(
                conn,
                scope,
                project_id if custom else None,
                str(row["name"]),
                ref,
                "" if custom else str(row["instructions"]),
            )
        await conn.execute(
            "INSERT INTO telegram_thread_bindings VALUES (?, ?, ?)",
            (project_id, thread_id, thread_id),
        )
        return thread_id

    @staticmethod
    async def _insert(
        conn: aiosqlite.Connection,
        scope: Scope,
        project_id: str | None,
        title: str,
        ref: str,
        instructions: str = "",
    ) -> str:
        thread_id = uuid4().hex
        await conn.execute(
            """INSERT INTO threads
               (id,scope_kind,scope_id,project_id,title,session_ref,default_instructions)
               VALUES (?,?,?,?,?,?,?)""",
            (thread_id, scope.kind, scope.id, project_id, title, ref, instructions),
        )
        return thread_id

    async def sync_project(self, owner: int, project_id: str) -> Thread:
        async with self.database.transaction() as conn:
            row = await (
                await conn.execute(
                    "SELECT * FROM telegram_projects WHERE id=? AND user_id=?", (project_id, owner)
                )
            ).fetchone()
            if row is None:
                raise LookupError("Project not found")
            thread_id = await self._bound(conn, project_id)
            if thread_id is None:
                thread_id = await self._import_project(conn, row)
            if row["kind"] == "skye":
                await conn.execute(
                    "UPDATE threads SET default_instructions=? WHERE id="
                    "(SELECT initial_thread_id FROM telegram_thread_bindings WHERE project_id=?)",
                    (row["instructions"], project_id),
                )
        return await self.require(Scope("user", owner), thread_id)

    async def require(self, scope: Scope, thread_id: str) -> Thread:
        row = await self.database.fetch_one(
            """SELECT t.*, p.instructions AS project_instructions FROM threads t
               LEFT JOIN telegram_projects p ON p.id=t.project_id AND p.user_id=t.scope_id
               WHERE t.id=? AND t.scope_kind=? AND t.scope_id=?""",
            (thread_id, scope.kind, scope.id),
        )
        if row is None:
            raise LookupError("Thread not found")
        return Thread(
            ThreadRecord(
                id=row["id"],
                project_id=row["project_id"],
                title=row["title"],
                archived=bool(row["archived"]),
                revision=row["revision"],
            ),
            scope,
            str(row["session_ref"]),
            str(row["project_instructions"] or row["default_instructions"]),
        )

    async def list_threads(self, owner: int) -> list[ThreadRecord]:
        rows = await self.database.fetch_all(
            "SELECT id,project_id,title,archived,revision FROM threads "
            "WHERE scope_kind='user' AND scope_id=? ORDER BY rowid DESC LIMIT 200",
            (owner,),
        )
        return [
            ThreadRecord(
                id=row["id"],
                project_id=row["project_id"],
                title=row["title"],
                archived=bool(row["archived"]),
                revision=row["revision"],
            )
            for row in rows
        ]

    async def create(self, owner: int, project_id: str | None, title: str) -> Thread:
        title = " ".join(title.split())
        if not 1 <= len(title) <= 128:
            raise ValueError("Thread title must be 1–128 characters")
        async with self.database.transaction() as conn:
            if project_id is not None:
                row = await (
                    await conn.execute(
                        "SELECT 1 FROM telegram_projects "
                        "WHERE id=? AND user_id=? AND kind='custom'",
                        (project_id, owner),
                    )
                ).fetchone()
                if row is None:
                    raise LookupError("Project not found")
            thread_id = await self._insert(
                conn, Scope("user", owner), project_id, title, f"thread:{uuid4().hex}"
            )
        return await self.require(Scope("user", owner), thread_id)

    async def select(self, owner: int, project_id: str, thread_id: str) -> Thread:
        thread = await self.require(Scope("user", owner), thread_id)
        project = await self.database.telegram_project(owner, project_id)
        if (
            project is None
            or thread.record.archived
            or thread.record.project_id != (project_id if project.kind == "custom" else None)
        ):
            raise LookupError("Thread not found in this project")
        async with self.database.transaction() as conn:
            await conn.execute(
                "UPDATE telegram_thread_bindings SET selected_thread_id=? WHERE project_id=?",
                (thread_id, project_id),
            )
            await conn.execute(
                "UPDATE user_settings SET active_telegram_project_id=? WHERE user_id=?",
                (project_id, owner),
            )
        return thread

    async def append(
        self,
        scope: Scope,
        thread_id: str,
        *,
        role: Literal["user", "assistant"],
        origin: Literal["telegram", "web", "automation"],
        text: str,
        receipt: str,
        run_id: str | None = None,
    ) -> VisibleMessage:
        await self.require(scope, thread_id)
        async with self.database.transaction() as conn:
            previous = await (
                await conn.execute(
                    "SELECT thread_id,payload FROM visible_messages WHERE receipt=?", (receipt,)
                )
            ).fetchone()
            if previous:
                if previous["thread_id"] != thread_id:
                    raise ValueError("Receipt belongs to a different thread")
                return VisibleMessage.model_validate_json(previous["payload"])
            row = await (
                await conn.execute(
                    "SELECT COALESCE(MAX(sequence),0)+1 FROM visible_messages WHERE thread_id=?",
                    (thread_id,),
                )
            ).fetchone()
            assert row is not None
            result = VisibleMessage.model_validate(
                {
                    "id": uuid4().hex,
                    "thread_id": thread_id,
                    "sequence": row[0],
                    "role": role,
                    "origin": origin,
                    "parts": [{"type": "text", "text": text}],
                    "run_id": run_id,
                }
            )
            await conn.execute(
                "INSERT INTO visible_messages(id,thread_id,sequence,payload,receipt)"
                " VALUES(?,?,?,?,?)",
                (result.id, thread_id, result.sequence, result.model_dump_json(), receipt),
            )
        return result

    async def history(
        self, owner: int, thread_id: str, *, before: int = 2**63 - 1, limit: int = 50
    ) -> list[VisibleMessage]:
        await self.require(Scope("user", owner), thread_id)
        rows = await self.database.fetch_all(
            "SELECT payload FROM visible_messages WHERE thread_id=? AND sequence<? "
            "ORDER BY sequence DESC LIMIT ?",
            (thread_id, before, min(100, max(1, limit))),
        )
        return [VisibleMessage.model_validate_json(row[0]) for row in reversed(rows)]

    async def clear(self, owner: int, thread_id: str) -> None:
        await self.clear_scope(Scope("user", owner), thread_id)

    async def clear_scope(self, scope: Scope, thread_id: str) -> None:
        thread = await self.require(scope, thread_id)
        async with self.database.transaction() as conn:
            active = await (
                await conn.execute(
                    "SELECT 1 FROM canonical_runs WHERE thread_id=? AND state IN "
                    "('accepted','running','cancelling')",
                    (thread_id,),
                )
            ).fetchone()
            if active:
                raise ValueError("Stop the active request before clearing this thread")
            await conn.execute(
                "DELETE FROM agent_messages WHERE session_id=?", (thread.session_ref,)
            )
            await conn.execute("DELETE FROM visible_messages WHERE thread_id=?", (thread_id,))
            await conn.execute("UPDATE threads SET revision=revision+1 WHERE id=?", (thread_id,))

    async def by_session(self, scope: Scope, ref: str) -> Thread:
        row = await self.database.fetch_one(
            "SELECT id FROM threads WHERE scope_kind=? AND scope_id=? AND session_ref=?",
            (scope.kind, scope.id, ref),
        )
        if row is None:
            raise LookupError("Thread not found")
        return await self.require(scope, str(row[0]))

    async def group(self, chat_id: int, topic_id: int, ref: str) -> Thread:
        if chat_id >= 0:
            raise ValueError("Group binding requires a group chat")
        async with self.database.transaction() as conn:
            row = await (
                await conn.execute(
                    "SELECT thread_id FROM group_thread_bindings WHERE chat_id=? AND topic_id=?",
                    (chat_id, topic_id),
                )
            ).fetchone()
            if row:
                thread_id = str(row[0])
            else:
                thread_id = await self._insert(
                    conn, Scope("chat", chat_id), None, "Telegram conversation", ref
                )
                await conn.execute(
                    "INSERT INTO group_thread_bindings VALUES(?,?,?)",
                    (chat_id, topic_id, thread_id),
                )
        return await self.require(Scope("chat", chat_id), thread_id)

    async def interrupt_runs(self) -> int:
        cursor = await self.database.execute_write(
            "UPDATE canonical_runs SET state='interrupted',cost_state=CASE WHEN EXISTS "
            "(SELECT 1 FROM run_settlements WHERE run_id=canonical_runs.id) "
            "THEN 'settled' ELSE 'unknown' END "
            "WHERE state IN ('accepted','running','cancelling')"
        )
        return cursor.rowcount
