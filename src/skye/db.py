from __future__ import annotations

import asyncio
import json
import re
import time
from collections.abc import AsyncIterator, Iterable, Mapping, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import aiosqlite

from .config import ModelId, Reasoning
from .models import (
    AccessEffect,
    AccessEntry,
    AgentCapability,
    AgentProfile,
    AgentVersion,
    AgentVisibility,
    Automation,
    AutomationKind,
    ChatSettings,
    ConnectorKind,
    ConnectorShare,
    CustomConnector,
    GroupMessage,
    InstalledAgent,
    KnownGroup,
    MediaGroupItem,
    Memory,
    MemoryCategory,
    ProjectKind,
    Scope,
    ScopeKind,
    Skill,
    TelegramProject,
    WalletEntry,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS access_entries (
    kind TEXT NOT NULL CHECK (kind IN ('user', 'chat')),
    telegram_id INTEGER NOT NULL,
    effect TEXT NOT NULL CHECK (effect IN ('allow', 'ban')),
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (kind, telegram_id)
);

CREATE TABLE IF NOT EXISTS user_settings (
    user_id INTEGER PRIMARY KEY,
    model TEXT NOT NULL,
    reasoning TEXT NOT NULL,
    memory_enabled INTEGER NOT NULL DEFAULT 1,
    active_agent_id TEXT,
    active_telegram_project_id TEXT,
    sparks_display INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_settings (
    chat_id INTEGER PRIMARY KEY,
    model TEXT NOT NULL,
    reasoning TEXT NOT NULL,
    memory_enabled INTEGER NOT NULL DEFAULT 1,
    active_agent_id TEXT,
    sparks_display INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversations (
    chat_id INTEGER NOT NULL,
    thread_id INTEGER NOT NULL DEFAULT 0,
    openai_conversation_id TEXT NOT NULL,
    context_message_id INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (chat_id, thread_id)
);

CREATE TABLE IF NOT EXISTS agent_sessions (
    session_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES agent_sessions(session_id) ON DELETE CASCADE,
    message_data TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS agent_messages_session
ON agent_messages(session_id, id);

CREATE TABLE IF NOT EXISTS telegram_projects (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('skye', 'custom')),
    name TEXT NOT NULL,
    emoji TEXT NOT NULL,
    instructions TEXT NOT NULL DEFAULT '',
    openai_conversation_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS telegram_projects_user
ON telegram_projects(user_id, updated_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS telegram_projects_skye
ON telegram_projects(user_id) WHERE kind = 'skye';

CREATE TABLE IF NOT EXISTS updates (
    update_id INTEGER PRIMARY KEY,
    payload TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('processing', 'pending', 'done')),
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope_kind TEXT NOT NULL CHECK (scope_kind IN ('user', 'chat')),
    scope_id INTEGER NOT NULL,
    category TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (scope_kind, scope_id, content)
);

CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    owner_id INTEGER NOT NULL,
    visibility TEXT NOT NULL CHECK (visibility IN ('private', 'unlisted', 'public')),
    current_version INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_versions (
    agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    instructions TEXT NOT NULL,
    model TEXT,
    capabilities TEXT NOT NULL,
    checksum TEXT NOT NULL,
    share_token TEXT UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (agent_id, version)
);

CREATE TABLE IF NOT EXISTS agent_installs (
    scope_kind TEXT NOT NULL CHECK (scope_kind IN ('user', 'chat')),
    scope_id INTEGER NOT NULL,
    agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    installed_by INTEGER NOT NULL,
    installed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (scope_kind, scope_id, agent_id),
    FOREIGN KEY (agent_id, version) REFERENCES agent_versions(agent_id, version)
);

CREATE INDEX IF NOT EXISTS agent_installs_scope
ON agent_installs(scope_kind, scope_id, enabled, installed_at);

CREATE TABLE IF NOT EXISTS group_messages (
    chat_id INTEGER NOT NULL,
    thread_id INTEGER NOT NULL DEFAULT 0,
    message_id INTEGER NOT NULL,
    sender_id INTEGER,
    sender_name TEXT NOT NULL,
    sender_username TEXT,
    text TEXT NOT NULL DEFAULT '',
    media_kind TEXT,
    media_file_id TEXT,
    reply_to_message_id INTEGER,
    reply_sender_name TEXT,
    reply_sender_username TEXT,
    reply_excerpt TEXT,
    sent_at INTEGER NOT NULL,
    PRIMARY KEY (chat_id, message_id)
);

CREATE INDEX IF NOT EXISTS group_messages_context
ON group_messages(chat_id, thread_id, message_id DESC);

CREATE TABLE IF NOT EXISTS media_group_items (
    chat_id INTEGER NOT NULL,
    media_group_id TEXT NOT NULL,
    message_id INTEGER NOT NULL,
    thread_id INTEGER NOT NULL DEFAULT 0,
    media_kind TEXT NOT NULL,
    file_id TEXT NOT NULL,
    file_unique_id TEXT NOT NULL,
    file_name TEXT,
    mime_type TEXT,
    file_size INTEGER,
    width INTEGER,
    height INTEGER,
    caption TEXT,
    sent_at INTEGER NOT NULL,
    PRIMARY KEY (chat_id, message_id)
);

CREATE INDEX IF NOT EXISTS media_group_items_lookup
ON media_group_items(chat_id, media_group_id, message_id);

CREATE TABLE IF NOT EXISTS media_group_claims (
    chat_id INTEGER NOT NULL,
    media_group_id TEXT NOT NULL,
    claimed_message_id INTEGER NOT NULL,
    claimed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (chat_id, media_group_id)
);

CREATE TABLE IF NOT EXISTS custom_connectors (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    headers TEXT NOT NULL DEFAULT '{}',
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS custom_connectors_user
ON custom_connectors(user_id, enabled, updated_at);

CREATE TABLE IF NOT EXISTS user_toolkits (
    user_id INTEGER NOT NULL,
    slug TEXT NOT NULL,
    PRIMARY KEY (user_id, slug)
);

CREATE TABLE IF NOT EXISTS composio_sessions (
    user_id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL,
    mcp_url TEXT NOT NULL,
    toolkit_key TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS composio_session_cache (
    user_id INTEGER NOT NULL,
    toolkit_key TEXT NOT NULL,
    session_id TEXT NOT NULL,
    mcp_url TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, toolkit_key)
);

CREATE TABLE IF NOT EXISTS known_chats (
    chat_id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS connector_shares (
    id TEXT PRIMARY KEY,
    chat_id INTEGER NOT NULL,
    owner_id INTEGER NOT NULL,
    owner_name TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('app', 'custom')),
    ref TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (chat_id, owner_id, kind, ref)
);

CREATE INDEX IF NOT EXISTS connector_shares_chat
ON connector_shares(chat_id, created_at);

CREATE INDEX IF NOT EXISTS connector_shares_owner
ON connector_shares(owner_id, kind, ref);

CREATE TABLE IF NOT EXISTS skills (
    id TEXT PRIMARY KEY,
    scope_kind TEXT NOT NULL CHECK (scope_kind IN ('user', 'chat')),
    scope_id INTEGER NOT NULL,
    openai_skill_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    filename TEXT NOT NULL,
    archive BLOB NOT NULL,
    file_count INTEGER NOT NULL,
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (scope_kind, scope_id, name)
);

CREATE INDEX IF NOT EXISTS skills_scope
ON skills(scope_kind, scope_id, created_at);

CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    content,
    category,
    content='memories',
    content_rowid='id',
    tokenize='unicode61'
);

CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, content, category)
    VALUES (new.id, new.content, new.category);
END;

CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content, category)
    VALUES ('delete', old.id, old.content, old.category);
END;

CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content, category)
    VALUES ('delete', old.id, old.content, old.category);
    INSERT INTO memories_fts(rowid, content, category)
    VALUES (new.id, new.content, new.category);
END;

CREATE TABLE IF NOT EXISTS usage_counters (
    user_id INTEGER PRIMARY KEY,
    day_utc TEXT NOT NULL,
    month_utc TEXT NOT NULL,
    daily_tokens INTEGER NOT NULL DEFAULT 0,
    monthly_tokens INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS product_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    source TEXT,
    capability TEXT,
    occurred_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS product_events_user
ON product_events(user_id, name, occurred_at);

CREATE TABLE IF NOT EXISTS wallets (
    user_id INTEGER PRIMARY KEY,
    balance_milli INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS wallet_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    delta_milli INTEGER NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('topup', 'spend', 'bonus', 'adjust', 'refund')),
    reason TEXT NOT NULL DEFAULT '',
    reference TEXT,
    provider_cost_rub REAL,
    detail TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS wallet_ledger_user ON wallet_ledger(user_id, id);

CREATE TABLE IF NOT EXISTS spark_topups (
    telegram_payment_charge_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    package_id TEXT NOT NULL,
    stars INTEGER NOT NULL,
    sparks_milli INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_sponsors (
    chat_id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS automations (
    id TEXT PRIMARY KEY,
    scope_kind TEXT NOT NULL CHECK (scope_kind IN ('user', 'chat')),
    scope_id INTEGER NOT NULL,
    thread_id INTEGER NOT NULL DEFAULT 0,
    created_by INTEGER NOT NULL,
    name TEXT NOT NULL,
    prompt TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('schedule', 'webhook')),
    cron TEXT,
    timezone TEXT,
    webhook_authorization TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_fired_at INTEGER,
    next_run_at INTEGER,
    once INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS automations_scope
ON automations(scope_kind, scope_id, thread_id, created_at);

CREATE INDEX IF NOT EXISTS automations_due
ON automations(kind, enabled, next_run_at);

CREATE TABLE IF NOT EXISTS ops_config_overrides (
    env TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: Path, default_model: ModelId, default_reasoning: Reasoning) -> None:
        self.path = path
        self.default_model = default_model
        self.default_reasoning = default_reasoning
        self.connection: aiosqlite.Connection | None = None
        self._write_lock = asyncio.Lock()

    async def open(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = await aiosqlite.connect(self.path)
        self.connection.row_factory = aiosqlite.Row
        await self.connection.execute("PRAGMA journal_mode=WAL")
        await self.connection.execute("PRAGMA foreign_keys=ON")
        await self.connection.execute("PRAGMA busy_timeout=5000")
        await self.connection.executescript(SCHEMA)
        await self._ensure_column("user_settings", "memory_enabled", "INTEGER NOT NULL DEFAULT 1")
        await self._ensure_column("chat_settings", "memory_enabled", "INTEGER NOT NULL DEFAULT 1")
        await self._ensure_column("user_settings", "active_agent_id", "TEXT")
        await self._ensure_column("chat_settings", "active_agent_id", "TEXT")
        await self._ensure_column(
            "composio_session_cache", "mcp_headers", "TEXT NOT NULL DEFAULT '{}'"
        )
        await self._ensure_column(
            "conversations", "context_message_id", "INTEGER NOT NULL DEFAULT 0"
        )
        await self._ensure_column("user_settings", "active_telegram_project_id", "TEXT")
        await self._ensure_column("automations", "once", "INTEGER NOT NULL DEFAULT 0")
        await self._ensure_column(
            "user_settings", "sparks_display", "INTEGER NOT NULL DEFAULT 1"
        )
        await self._ensure_column(
            "chat_settings", "sparks_display", "INTEGER NOT NULL DEFAULT 1"
        )
        await self._normalize_group_message_threads()
        await self._migrate_composio_sessions()
        await self.connection.commit()

    async def close(self) -> None:
        if self.connection is not None:
            await self.connection.close()
            self.connection = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self.connection is None:
            raise RuntimeError("Database is not open")
        return self.connection

    async def _write(self, sql: str, parameters: Sequence[object] = ()) -> aiosqlite.Cursor:
        async with self._write_lock:
            cursor = await self.conn.execute(sql, parameters)
            await self.conn.commit()
            return cursor

    # -- Operator surfaces (observability, config overrides). These share the
    # process write lock so the ops worker can never commit a run's transaction.

    async def execute_write(
        self, sql: str, parameters: Sequence[object] = ()
    ) -> aiosqlite.Cursor:
        return await self._write(sql, parameters)

    async def execute_many(self, sql: str, rows: Iterable[Any]) -> None:
        async with self._write_lock:
            await self.conn.executemany(sql, rows)
            await self.conn.commit()

    async def execute_script(self, script: str) -> None:
        async with self._write_lock:
            await self.conn.executescript(script)
            await self.conn.commit()

    async def fetch_all(
        self, sql: str, parameters: Sequence[object] = ()
    ) -> list[aiosqlite.Row]:
        cursor = await self.conn.execute(sql, parameters)
        return list(await cursor.fetchall())

    async def fetch_one(
        self, sql: str, parameters: Sequence[object] = ()
    ) -> aiosqlite.Row | None:
        cursor = await self.conn.execute(sql, parameters)
        return await cursor.fetchone()

    async def config_overrides(self) -> dict[str, Any]:
        """Panel-managed settings overrides, keyed by environment variable."""
        rows = await self.fetch_all(
            "SELECT env, value FROM ops_config_overrides ORDER BY env"
        )
        result: dict[str, Any] = {}
        for row in rows:
            raw = str(row["value"])
            try:
                result[str(row["env"])] = json.loads(raw)
            except json.JSONDecodeError:
                result[str(row["env"])] = raw
        return result

    async def set_config_overrides(
        self, updates: Mapping[str, Any], removals: Sequence[str]
    ) -> None:
        if updates:
            now = datetime.now(UTC).isoformat(timespec="milliseconds")
            await self.execute_many(
                """INSERT INTO ops_config_overrides (env, value, updated_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(env) DO UPDATE SET
                       value = excluded.value, updated_at = excluded.updated_at""",
                [
                    (env, json.dumps(value, ensure_ascii=False), now)
                    for env, value in updates.items()
                ],
            )
        for env in removals:
            await self.execute_write(
                "DELETE FROM ops_config_overrides WHERE env = ?", (env,)
            )

    async def _ensure_column(self, table: str, column: str, definition: str) -> None:
        cursor = await self.conn.execute(f"PRAGMA table_info({table})")
        if column not in {row[1] for row in await cursor.fetchall()}:
            await self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    async def _migrate_composio_sessions(self) -> None:
        cursor = await self.conn.execute("SELECT COUNT(*) FROM composio_session_cache")
        row = await cursor.fetchone()
        if row and int(row[0]) > 0:
            return
        cursor = await self.conn.execute(
            "SELECT user_id, session_id, mcp_url, toolkit_key FROM composio_sessions"
        )
        for item in await cursor.fetchall():
            await self.conn.execute(
                """INSERT OR IGNORE INTO composio_session_cache
                   (user_id, toolkit_key, session_id, mcp_url)
                   VALUES (?, ?, ?, ?)""",
                (item["user_id"], item["toolkit_key"], item["session_id"], item["mcp_url"]),
            )

    async def _normalize_group_message_threads(self) -> None:
        await self.conn.execute(
            """UPDATE group_messages AS message
               SET thread_id = 0
               WHERE thread_id != 0
                 AND EXISTS (
                     SELECT 1 FROM updates
                     WHERE COALESCE(
                               json_extract(payload, '$.message.chat.id'),
                               json_extract(payload, '$.edited_message.chat.id')
                           ) = message.chat_id
                       AND COALESCE(
                               json_extract(payload, '$.message.message_id'),
                               json_extract(payload, '$.edited_message.message_id')
                           ) = message.message_id
                       AND COALESCE(
                               json_extract(payload, '$.message.is_topic_message'),
                               json_extract(payload, '$.edited_message.is_topic_message'),
                               0
                           ) = 0
                 )"""
        )

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[aiosqlite.Connection]:
        async with self._write_lock:
            await self.conn.execute("BEGIN IMMEDIATE")
            try:
                yield self.conn
            except BaseException:
                await self.conn.rollback()
                raise
            else:
                await self.conn.commit()

    async def access_effect(self, scope: Scope) -> AccessEffect | None:
        cursor = await self.conn.execute(
            "SELECT effect FROM access_entries WHERE kind = ? AND telegram_id = ?",
            (scope.kind, scope.id),
        )
        row = await cursor.fetchone()
        return cast(AccessEffect, row["effect"]) if row else None

    async def set_access(self, scope: Scope, effect: AccessEffect, created_by: int) -> None:
        await self._write(
            """INSERT INTO access_entries (kind, telegram_id, effect, created_by)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(kind, telegram_id) DO UPDATE SET
                   effect = excluded.effect,
                   created_by = excluded.created_by,
                   created_at = CURRENT_TIMESTAMP""",
            (scope.kind, scope.id, effect, created_by),
        )

    async def remove_access(self, scope: Scope) -> bool:
        cursor = await self._write(
            "DELETE FROM access_entries WHERE kind = ? AND telegram_id = ?",
            (scope.kind, scope.id),
        )
        return cursor.rowcount > 0

    async def list_access(self) -> list[AccessEntry]:
        cursor = await self.conn.execute(
            "SELECT kind, telegram_id, effect, created_by, created_at "
            "FROM access_entries ORDER BY created_at"
        )
        return [
            AccessEntry(
                Scope(cast(ScopeKind, row["kind"]), int(row["telegram_id"])),
                cast(AccessEffect, row["effect"]),
                int(row["created_by"]),
                str(row["created_at"]),
            )
            for row in await cursor.fetchall()
        ]

    async def wallet_balance(self, user_id: int) -> int:
        cursor = await self.conn.execute(
            "SELECT balance_milli FROM wallets WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return int(row["balance_milli"]) if row else 0

    async def credit_wallet(
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
            raise ValueError("Credit must be positive.")
        async with self.transaction() as connection:
            await connection.execute(
                """INSERT INTO wallets (user_id, balance_milli)
                   VALUES (?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET
                       balance_milli = wallets.balance_milli + excluded.balance_milli,
                       updated_at = CURRENT_TIMESTAMP""",
                (user_id, milli),
            )
            await connection.execute(
                """INSERT INTO wallet_ledger (
                       user_id, delta_milli, kind, reason, reference,
                       provider_cost_rub, detail
                   ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_id, milli, kind, reason, reference, provider_cost_rub, detail),
            )
            cursor = await connection.execute(
                "SELECT balance_milli FROM wallets WHERE user_id = ?", (user_id,)
            )
            row = await cursor.fetchone()
        return int(row["balance_milli"]) if row else milli

    async def debit_wallet(
        self,
        user_id: int,
        milli: int,
        *,
        kind: str = "spend",
        reason: str = "",
        reference: str | None = None,
        provider_cost_rub: float | None = None,
        detail: str | None = None,
    ) -> bool:
        if milli <= 0:
            return True
        async with self.transaction() as connection:
            cursor = await connection.execute(
                """UPDATE wallets
                   SET balance_milli = balance_milli - ?, updated_at = CURRENT_TIMESTAMP
                   WHERE user_id = ? AND balance_milli >= ?""",
                (milli, user_id, milli),
            )
            if cursor.rowcount == 0:
                return False
            await connection.execute(
                """INSERT INTO wallet_ledger (
                       user_id, delta_milli, kind, reason, reference,
                       provider_cost_rub, detail
                   ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_id, -milli, kind, reason, reference, provider_cost_rub, detail),
            )
        return True

    async def wallet_ledger(self, user_id: int, *, limit: int = 10) -> list[WalletEntry]:
        cursor = await self.conn.execute(
            """SELECT id, user_id, delta_milli, kind, reason, reference,
                      provider_cost_rub, detail, created_at
               FROM wallet_ledger WHERE user_id = ?
               ORDER BY id DESC LIMIT ?""",
            (user_id, limit),
        )
        return [self._wallet_entry(row) for row in await cursor.fetchall()]

    @staticmethod
    def _wallet_entry(row: aiosqlite.Row) -> WalletEntry:
        raw_cost = row["provider_cost_rub"]
        return WalletEntry(
            id=int(row["id"]),
            user_id=int(row["user_id"]),
            delta_milli=int(row["delta_milli"]),
            kind=str(row["kind"]),
            reason=str(row["reason"]),
            reference=cast(str | None, row["reference"]),
            provider_cost_rub=None if raw_cost is None else float(raw_cost),
            detail=cast(str | None, row["detail"]),
            created_at=str(row["created_at"]),
        )

    async def record_spark_topup(
        self,
        *,
        telegram_payment_charge_id: str,
        user_id: int,
        package_id: str,
        stars: int,
        sparks_milli: int,
    ) -> bool:
        cursor = await self._write(
            """INSERT OR IGNORE INTO spark_topups (
                   telegram_payment_charge_id, user_id, package_id, stars, sparks_milli
               ) VALUES (?, ?, ?, ?, ?)""",
            (telegram_payment_charge_id, user_id, package_id, stars, sparks_milli),
        )
        return cursor.rowcount > 0

    async def spark_topup(self, telegram_payment_charge_id: str) -> bool:
        cursor = await self.conn.execute(
            "SELECT 1 FROM spark_topups WHERE telegram_payment_charge_id = ?",
            (telegram_payment_charge_id,),
        )
        return await cursor.fetchone() is not None

    async def chat_sponsor(self, chat_id: int) -> int | None:
        cursor = await self.conn.execute(
            "SELECT user_id FROM chat_sponsors WHERE chat_id = ?", (chat_id,)
        )
        row = await cursor.fetchone()
        return int(row["user_id"]) if row else None

    async def set_chat_sponsor(self, chat_id: int, user_id: int) -> None:
        await self._write(
            """INSERT INTO chat_sponsors (chat_id, user_id)
               VALUES (?, ?)
               ON CONFLICT(chat_id) DO UPDATE SET
                   user_id = excluded.user_id,
                   updated_at = CURRENT_TIMESTAMP""",
            (chat_id, user_id),
        )

    async def clear_chat_sponsor(self, chat_id: int) -> None:
        await self._write("DELETE FROM chat_sponsors WHERE chat_id = ?", (chat_id,))

    async def usage_totals(
        self, user_id: int, *, now: datetime | None = None
    ) -> tuple[int, int]:
        day, month = _usage_keys(now)
        cursor = await self.conn.execute(
            """SELECT day_utc, month_utc, daily_tokens, monthly_tokens
               FROM usage_counters WHERE user_id = ?""",
            (user_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return 0, 0
        daily = int(row["daily_tokens"]) if str(row["day_utc"]) == day else 0
        monthly = int(row["monthly_tokens"]) if str(row["month_utc"]) == month else 0
        return daily, monthly

    async def add_usage(
        self, user_id: int, tokens: int, *, now: datetime | None = None
    ) -> tuple[int, int]:
        if tokens < 0:
            raise ValueError("Usage cannot be negative.")
        day, month = _usage_keys(now)
        async with self.transaction() as connection:
            cursor = await connection.execute(
                """SELECT day_utc, month_utc, daily_tokens, monthly_tokens
                   FROM usage_counters WHERE user_id = ?""",
                (user_id,),
            )
            row = await cursor.fetchone()
            daily = (
                int(row["daily_tokens"])
                if row is not None and str(row["day_utc"]) == day
                else 0
            )
            monthly = (
                int(row["monthly_tokens"])
                if row is not None and str(row["month_utc"]) == month
                else 0
            )
            daily += tokens
            monthly += tokens
            await connection.execute(
                """INSERT INTO usage_counters (
                       user_id, day_utc, month_utc, daily_tokens, monthly_tokens
                   ) VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET
                       day_utc = excluded.day_utc,
                       month_utc = excluded.month_utc,
                       daily_tokens = excluded.daily_tokens,
                       monthly_tokens = excluded.monthly_tokens,
                       updated_at = CURRENT_TIMESTAMP""",
                (user_id, day, month, daily, monthly),
            )
        return daily, monthly

    async def record_product_event(
        self,
        user_id: int,
        name: str,
        *,
        source: str | None = None,
        capability: str | None = None,
        occurred_at: int | None = None,
    ) -> None:
        await self._write(
            """INSERT INTO product_events (user_id, name, source, capability, occurred_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                user_id,
                name,
                source,
                capability,
                int(time.time()) if occurred_at is None else occurred_at,
            ),
        )

    async def activation_progress(self, user_id: int) -> tuple[int, int, bool]:
        cursor = await self.conn.execute(
            """SELECT COUNT(*) AS tasks,
                      COUNT(DISTINCT date(occurred_at, 'unixepoch')) AS active_days,
                      MAX(CASE WHEN capability != 'chat' THEN 1 ELSE 0 END) AS rich_capability
               FROM product_events
               WHERE user_id = ? AND name = 'task_completed'""",
            (user_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return 0, 0, False
        return int(row["tasks"]), int(row["active_days"]), bool(row["rich_capability"])


    async def grant_activation_bonus(self, user_id: int, milli: int, now: int) -> bool:
        """Credit a one-time Sparks bonus once a user has genuinely activated."""

        async with self.transaction() as connection:
            cursor = await connection.execute(
                """SELECT 1 FROM wallet_ledger
                   WHERE user_id = ? AND kind = 'bonus' AND reason = 'activation'""",
                (user_id,),
            )
            if await cursor.fetchone() is not None:
                return False
            cursor = await connection.execute(
                """SELECT COUNT(*) AS tasks,
                          COUNT(DISTINCT date(occurred_at, 'unixepoch')) AS active_days,
                          MAX(CASE WHEN capability != 'chat' THEN 1 ELSE 0 END)
                              AS rich_capability
                   FROM product_events
                   WHERE user_id = ? AND name = 'task_completed'""",
                (user_id,),
            )
            progress = await cursor.fetchone()
            if progress is None or not (
                int(progress["tasks"]) >= 3
                and int(progress["active_days"]) >= 2
                and bool(progress["rich_capability"])
            ):
                return False
            await connection.execute(
                """INSERT INTO wallets (user_id, balance_milli)
                   VALUES (?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET
                       balance_milli = wallets.balance_milli + excluded.balance_milli,
                       updated_at = CURRENT_TIMESTAMP""",
                (user_id, milli),
            )
            await connection.execute(
                """INSERT INTO wallet_ledger (user_id, delta_milli, kind, reason)
                   VALUES (?, ?, 'bonus', 'activation')""",
                (user_id, milli),
            )
            await connection.execute(
                """INSERT INTO product_events (user_id, name, occurred_at)
                   VALUES (?, 'bonus_granted', ?)""",
                (user_id, now),
            )
        return True

    async def get_settings(self, scope: Scope) -> ChatSettings:
        table, key = self._settings_table(scope)
        cursor = await self.conn.execute(
            f"""SELECT model, reasoning, memory_enabled, active_agent_id, sparks_display
                FROM {table} WHERE {key} = ?""",
            (scope.id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return ChatSettings(self.default_model, self.default_reasoning)
        return ChatSettings(
            cast(ModelId, row["model"]),
            cast(Reasoning, row["reasoning"]),
            bool(row["memory_enabled"]),
            cast(str | None, row["active_agent_id"]),
            bool(row["sparks_display"]),
        )

    async def set_model(self, scope: Scope, model: ModelId) -> ChatSettings:
        current = await self.get_settings(scope)
        result = ChatSettings(
            model,
            current.reasoning,
            current.memory_enabled,
            current.active_agent_id,
            current.sparks_display,
        )
        await self._set_settings(scope, result)
        return result

    async def set_reasoning(self, scope: Scope, reasoning: Reasoning) -> ChatSettings:
        current = await self.get_settings(scope)
        result = ChatSettings(
            current.model,
            reasoning,
            current.memory_enabled,
            current.active_agent_id,
            current.sparks_display,
        )
        await self._set_settings(scope, result)
        return result

    async def set_memory_enabled(self, scope: Scope, enabled: bool) -> ChatSettings:
        current = await self.get_settings(scope)
        result = ChatSettings(
            current.model,
            current.reasoning,
            enabled,
            current.active_agent_id,
            current.sparks_display,
        )
        await self._set_settings(scope, result)
        return result

    async def set_active_agent(self, scope: Scope, agent_id: str | None) -> ChatSettings:
        current = await self.get_settings(scope)
        result = ChatSettings(
            current.model,
            current.reasoning,
            current.memory_enabled,
            agent_id,
            current.sparks_display,
        )
        await self._set_settings(scope, result)
        return result

    async def set_sparks_display(self, scope: Scope, enabled: bool) -> ChatSettings:
        current = await self.get_settings(scope)
        result = ChatSettings(
            current.model,
            current.reasoning,
            current.memory_enabled,
            current.active_agent_id,
            enabled,
        )
        await self._set_settings(scope, result)
        return result

    async def _set_settings(self, scope: Scope, settings: ChatSettings) -> None:
        table, key = self._settings_table(scope)
        await self._write(
            f"""INSERT INTO {table} (
                    {key}, model, reasoning, memory_enabled, active_agent_id, sparks_display
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT({key}) DO UPDATE SET
                    model = excluded.model,
                    reasoning = excluded.reasoning,
                    memory_enabled = excluded.memory_enabled,
                    active_agent_id = excluded.active_agent_id,
                    sparks_display = excluded.sparks_display,
                    updated_at = CURRENT_TIMESTAMP""",
            (
                scope.id,
                settings.model,
                settings.reasoning,
                settings.memory_enabled,
                settings.active_agent_id,
                settings.sparks_display,
            ),
        )

    @staticmethod
    def _settings_table(scope: Scope) -> tuple[str, str]:
        if scope.kind == "user":
            return "user_settings", "user_id"
        return "chat_settings", "chat_id"

    async def create_agent(
        self,
        *,
        agent_id: str,
        owner_id: int,
        scope: Scope,
        name: str,
        description: str,
        instructions: str,
        model: ModelId | None,
        capabilities: tuple[AgentCapability, ...],
        checksum: str,
    ) -> InstalledAgent:
        async with self.transaction() as connection:
            await connection.execute(
                """INSERT INTO agents (id, owner_id, visibility, current_version)
                   VALUES (?, ?, 'private', 1)""",
                (agent_id, owner_id),
            )
            await connection.execute(
                """INSERT INTO agent_versions (
                       agent_id, version, name, description, instructions, model,
                       capabilities, checksum
                   ) VALUES (?, 1, ?, ?, ?, ?, ?, ?)""",
                (
                    agent_id,
                    name,
                    description,
                    instructions,
                    model,
                    json.dumps(capabilities, separators=(",", ":")),
                    checksum,
                ),
            )
            await connection.execute(
                """INSERT INTO agent_installs (
                       scope_kind, scope_id, agent_id, version, installed_by
                   ) VALUES (?, ?, ?, 1, ?)""",
                (scope.kind, scope.id, agent_id, owner_id),
            )
            if scope != Scope("user", owner_id):
                await connection.execute(
                    """INSERT INTO agent_installs (
                           scope_kind, scope_id, agent_id, version, installed_by
                       ) VALUES ('user', ?, ?, 1, ?)""",
                    (owner_id, agent_id, owner_id),
                )
        installed = await self.installed_agent(scope, agent_id)
        if installed is None:
            raise RuntimeError("Agent was not created")
        return installed

    async def create_agent_version(
        self,
        *,
        agent_id: str,
        owner_id: int,
        scope: Scope,
        name: str,
        description: str,
        instructions: str,
        model: ModelId | None,
        capabilities: tuple[AgentCapability, ...],
        checksum: str,
    ) -> InstalledAgent:
        async with self.transaction() as connection:
            cursor = await connection.execute(
                "SELECT owner_id, current_version FROM agents WHERE id = ?", (agent_id,)
            )
            row = await cursor.fetchone()
            if row is None:
                raise LookupError("Agent not found.")
            if row["owner_id"] != owner_id:
                raise PermissionError("Only the agent owner can edit it.")
            version = cast(int, row["current_version"]) + 1
            await connection.execute(
                """INSERT INTO agent_versions (
                       agent_id, version, name, description, instructions, model,
                       capabilities, checksum
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    agent_id,
                    version,
                    name,
                    description,
                    instructions,
                    model,
                    json.dumps(capabilities, separators=(",", ":")),
                    checksum,
                ),
            )
            await connection.execute(
                """UPDATE agents SET current_version = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (version, agent_id),
            )
            await connection.execute(
                """INSERT INTO agent_installs (
                       scope_kind, scope_id, agent_id, version, installed_by
                   ) VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(scope_kind, scope_id, agent_id) DO UPDATE SET
                       version = excluded.version,
                       enabled = 1,
                       installed_by = excluded.installed_by,
                       installed_at = CURRENT_TIMESTAMP""",
                (scope.kind, scope.id, agent_id, version, owner_id),
            )
            if scope != Scope("user", owner_id):
                await connection.execute(
                    """UPDATE agent_installs SET version = ?, enabled = 1,
                           installed_at = CURRENT_TIMESTAMP
                       WHERE scope_kind = 'user' AND scope_id = ? AND agent_id = ?""",
                    (version, owner_id, agent_id),
                )
        installed = await self.installed_agent(scope, agent_id)
        if installed is None:
            raise RuntimeError("Agent version was not saved")
        return installed

    async def agent_profile(self, agent_id: str) -> AgentProfile | None:
        cursor = await self.conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
        row = await cursor.fetchone()
        return self._agent_profile(row) if row else None

    async def agent_version(self, agent_id: str, version: int) -> AgentVersion | None:
        cursor = await self.conn.execute(
            "SELECT * FROM agent_versions WHERE agent_id = ? AND version = ?",
            (agent_id, version),
        )
        row = await cursor.fetchone()
        return self._agent_version(row) if row else None

    async def installed_agent(self, scope: Scope, agent_id: str) -> InstalledAgent | None:
        cursor = await self.conn.execute(
            """SELECT
                   i.scope_kind, i.scope_id, i.enabled, i.installed_by, i.installed_at,
                   a.id, a.owner_id, a.visibility, a.current_version, a.created_at,
                   a.updated_at, v.version, v.name, v.description, v.instructions,
                   v.model, v.capabilities, v.checksum, v.share_token,
                   v.created_at AS version_created_at
               FROM agent_installs AS i
               JOIN agents AS a ON a.id = i.agent_id
               JOIN agent_versions AS v ON v.agent_id = i.agent_id AND v.version = i.version
               WHERE i.scope_kind = ? AND i.scope_id = ? AND i.agent_id = ?""",
            (scope.kind, scope.id, agent_id),
        )
        row = await cursor.fetchone()
        return self._installed_agent(row) if row else None

    async def installed_agents(
        self, scope: Scope, *, enabled_only: bool = False
    ) -> list[InstalledAgent]:
        enabled = " AND i.enabled = 1" if enabled_only else ""
        cursor = await self.conn.execute(
            """SELECT
                   i.scope_kind, i.scope_id, i.enabled, i.installed_by, i.installed_at,
                   a.id, a.owner_id, a.visibility, a.current_version, a.created_at,
                   a.updated_at, v.version, v.name, v.description, v.instructions,
                   v.model, v.capabilities, v.checksum, v.share_token,
                   v.created_at AS version_created_at
               FROM agent_installs AS i
               JOIN agents AS a ON a.id = i.agent_id
               JOIN agent_versions AS v ON v.agent_id = i.agent_id AND v.version = i.version
               WHERE i.scope_kind = ? AND i.scope_id = ?"""
            + enabled
            + " ORDER BY lower(v.name), i.installed_at",
            (scope.kind, scope.id),
        )
        return [self._installed_agent(row) for row in await cursor.fetchall()]

    async def share_agent_version(
        self, agent_id: str, owner_id: int, version: int, token: str
    ) -> str:
        async with self.transaction() as connection:
            cursor = await connection.execute(
                """SELECT a.owner_id, v.share_token
                   FROM agents AS a JOIN agent_versions AS v ON v.agent_id = a.id
                   WHERE a.id = ? AND v.version = ?""",
                (agent_id, version),
            )
            row = await cursor.fetchone()
            if row is None:
                raise LookupError("Agent version not found.")
            if row["owner_id"] != owner_id:
                raise PermissionError("Only the agent owner can share it.")
            existing = cast(str | None, row["share_token"])
            if existing:
                return existing
            await connection.execute(
                "UPDATE agent_versions SET share_token = ? WHERE agent_id = ? AND version = ?",
                (token, agent_id, version),
            )
            await connection.execute(
                """UPDATE agents SET visibility = 'unlisted', updated_at = CURRENT_TIMESTAMP
                   WHERE id = ? AND visibility = 'private'""",
                (agent_id,),
            )
        return token

    async def shared_agent(self, token: str) -> tuple[AgentProfile, AgentVersion] | None:
        cursor = await self.conn.execute(
            """SELECT
                   a.id, a.owner_id, a.visibility, a.current_version, a.created_at,
                   a.updated_at, v.version, v.name, v.description, v.instructions,
                   v.model, v.capabilities, v.checksum, v.share_token,
                   v.created_at AS version_created_at
               FROM agent_versions AS v JOIN agents AS a ON a.id = v.agent_id
               WHERE v.share_token = ? AND a.visibility IN ('unlisted', 'public')""",
            (token,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._agent_profile(row), self._joined_agent_version(row)

    async def install_agent(
        self, scope: Scope, agent_id: str, version: int, installed_by: int
    ) -> InstalledAgent:
        await self._write(
            """INSERT INTO agent_installs (
                   scope_kind, scope_id, agent_id, version, installed_by
               ) VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(scope_kind, scope_id, agent_id) DO UPDATE SET
                   version = excluded.version,
                   enabled = 1,
                   installed_by = excluded.installed_by,
                   installed_at = CURRENT_TIMESTAMP""",
            (scope.kind, scope.id, agent_id, version, installed_by),
        )
        installed = await self.installed_agent(scope, agent_id)
        if installed is None:
            raise RuntimeError("Agent was not installed")
        return installed

    async def remove_agent_install(self, scope: Scope, agent_id: str) -> bool:
        async with self.transaction() as connection:
            cursor = await connection.execute(
                """DELETE FROM agent_installs
                   WHERE scope_kind = ? AND scope_id = ? AND agent_id = ?""",
                (scope.kind, scope.id, agent_id),
            )
            table, key = self._settings_table(scope)
            await connection.execute(
                f"""UPDATE {table} SET active_agent_id = NULL, updated_at = CURRENT_TIMESTAMP
                    WHERE {key} = ? AND active_agent_id = ?""",
                (scope.id, agent_id),
            )
        return cursor.rowcount > 0

    @staticmethod
    def _agent_profile(row: aiosqlite.Row) -> AgentProfile:
        return AgentProfile(
            id=cast(str, row["id"]),
            owner_id=cast(int, row["owner_id"]),
            visibility=cast(AgentVisibility, row["visibility"]),
            current_version=cast(int, row["current_version"]),
            created_at=cast(str, row["created_at"]),
            updated_at=cast(str, row["updated_at"]),
        )

    @staticmethod
    def _agent_version(row: aiosqlite.Row) -> AgentVersion:
        return AgentVersion(
            agent_id=cast(str, row["agent_id"]),
            version=cast(int, row["version"]),
            name=cast(str, row["name"]),
            description=cast(str, row["description"]),
            instructions=cast(str, row["instructions"]),
            model=cast(ModelId | None, row["model"]),
            capabilities=tuple(cast(list[AgentCapability], json.loads(row["capabilities"]))),
            checksum=cast(str, row["checksum"]),
            share_token=cast(str | None, row["share_token"]),
            created_at=cast(str, row["created_at"]),
        )

    @classmethod
    def _joined_agent_version(cls, row: aiosqlite.Row) -> AgentVersion:
        return AgentVersion(
            agent_id=cast(str, row["id"]),
            version=cast(int, row["version"]),
            name=cast(str, row["name"]),
            description=cast(str, row["description"]),
            instructions=cast(str, row["instructions"]),
            model=cast(ModelId | None, row["model"]),
            capabilities=tuple(cast(list[AgentCapability], json.loads(row["capabilities"]))),
            checksum=cast(str, row["checksum"]),
            share_token=cast(str | None, row["share_token"]),
            created_at=cast(str, row["version_created_at"]),
        )

    @classmethod
    def _installed_agent(cls, row: aiosqlite.Row) -> InstalledAgent:
        return InstalledAgent(
            scope=Scope(cast(Any, row["scope_kind"]), cast(int, row["scope_id"])),
            profile=cls._agent_profile(row),
            version=cls._joined_agent_version(row),
            enabled=bool(row["enabled"]),
            installed_by=cast(int, row["installed_by"]),
            installed_at=cast(str, row["installed_at"]),
        )

    async def conversation_id(self, chat_id: int, thread_id: int) -> str | None:
        cursor = await self.conn.execute(
            "SELECT openai_conversation_id FROM conversations WHERE chat_id = ? AND thread_id = ?",
            (chat_id, thread_id),
        )
        row = await cursor.fetchone()
        return cast(str, row["openai_conversation_id"]) if row else None

    async def save_conversation(self, chat_id: int, thread_id: int, conversation_id: str) -> None:
        await self._write(
            """INSERT INTO conversations (chat_id, thread_id, openai_conversation_id)
               VALUES (?, ?, ?)
               ON CONFLICT(chat_id, thread_id) DO UPDATE SET
                   openai_conversation_id = excluded.openai_conversation_id,
                   updated_at = CURRENT_TIMESTAMP""",
            (chat_id, thread_id, conversation_id),
        )

    async def conversation_context_message_id(self, chat_id: int, thread_id: int) -> int:
        cursor = await self.conn.execute(
            "SELECT context_message_id FROM conversations WHERE chat_id = ? AND thread_id = ?",
            (chat_id, thread_id),
        )
        row = await cursor.fetchone()
        return cast(int, row["context_message_id"]) if row else 0

    async def set_conversation_context_message_id(
        self, chat_id: int, thread_id: int, message_id: int
    ) -> None:
        await self._write(
            """UPDATE conversations
               SET context_message_id = ?, updated_at = CURRENT_TIMESTAMP
               WHERE chat_id = ? AND thread_id = ?""",
            (message_id, chat_id, thread_id),
        )

    async def pop_conversation(self, chat_id: int, thread_id: int) -> str | None:
        conversation_id = await self.conversation_id(chat_id, thread_id)
        await self._write(
            "DELETE FROM conversations WHERE chat_id = ? AND thread_id = ?",
            (chat_id, thread_id),
        )
        return conversation_id

    async def session_items(self, session_id: str) -> list[dict[str, Any]]:
        cursor = await self.conn.execute(
            "SELECT message_data FROM agent_messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        )
        items: list[dict[str, Any]] = []
        for row in await cursor.fetchall():
            try:
                value = json.loads(cast(str, row["message_data"]))
            except json.JSONDecodeError, TypeError:
                continue
            if isinstance(value, dict):
                items.append(value)
        return items

    async def add_session_items(self, session_id: str, items: list[dict[str, Any]]) -> None:
        if not items:
            return
        async with self.transaction() as connection:
            await connection.execute(
                "INSERT OR IGNORE INTO agent_sessions (session_id) VALUES (?)",
                (session_id,),
            )
            await connection.executemany(
                "INSERT INTO agent_messages (session_id, message_data) VALUES (?, ?)",
                [
                    (session_id, json.dumps(item, ensure_ascii=False, separators=(",", ":")))
                    for item in items
                ],
            )
            await connection.execute(
                "UPDATE agent_sessions SET updated_at = CURRENT_TIMESTAMP WHERE session_id = ?",
                (session_id,),
            )

    async def session_item_count(self, session_id: str) -> int:
        cursor = await self.conn.execute(
            "SELECT COUNT(*) FROM agent_messages WHERE session_id = ?",
            (session_id,),
        )
        row = await cursor.fetchone()
        return int(row[0]) if row is not None else 0

    async def truncate_session(self, session_id: str, count: int) -> None:
        keep = max(count, 0)
        async with self.transaction() as connection:
            cursor = await connection.execute(
                """SELECT id FROM agent_messages
                   WHERE session_id = ? ORDER BY id LIMIT 1 OFFSET ?""",
                (session_id, keep),
            )
            first_extra = await cursor.fetchone()
            if first_extra is not None:
                await connection.execute(
                    "DELETE FROM agent_messages WHERE session_id = ? AND id >= ?",
                    (session_id, int(first_extra[0])),
                )

    async def replace_session_tail(
        self, session_id: str, count: int, items: list[dict[str, Any]]
    ) -> None:
        keep = max(count, 0)
        async with self.transaction() as connection:
            cursor = await connection.execute(
                """SELECT id FROM agent_messages
                   WHERE session_id = ? ORDER BY id LIMIT 1 OFFSET ?""",
                (session_id, keep),
            )
            first_extra = await cursor.fetchone()
            if first_extra is not None:
                await connection.execute(
                    "DELETE FROM agent_messages WHERE session_id = ? AND id >= ?",
                    (session_id, int(first_extra[0])),
                )
            await connection.executemany(
                "INSERT INTO agent_messages (session_id, message_data) VALUES (?, ?)",
                [
                    (session_id, json.dumps(item, ensure_ascii=False, separators=(",", ":")))
                    for item in items
                ],
            )
            await connection.execute(
                "UPDATE agent_sessions SET updated_at = CURRENT_TIMESTAMP WHERE session_id = ?",
                (session_id,),
            )

    async def pop_session_item(self, session_id: str) -> dict[str, Any] | None:
        async with self.transaction() as connection:
            cursor = await connection.execute(
                """DELETE FROM agent_messages
                   WHERE id = (SELECT id FROM agent_messages WHERE session_id = ?
                               ORDER BY id DESC LIMIT 1)
                   RETURNING message_data""",
                (session_id,),
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        try:
            value = json.loads(cast(str, row["message_data"]))
        except json.JSONDecodeError, TypeError:
            return None
        return value if isinstance(value, dict) else None

    async def clear_session(self, session_id: str) -> None:
        async with self.transaction() as connection:
            await connection.execute(
                "DELETE FROM agent_messages WHERE session_id = ?", (session_id,)
            )
            await connection.execute(
                "DELETE FROM agent_sessions WHERE session_id = ?", (session_id,)
            )

    async def session_has_items(self, session_id: str) -> bool:
        cursor = await self.conn.execute(
            "SELECT 1 FROM agent_messages WHERE session_id = ? LIMIT 1", (session_id,)
        )
        return await cursor.fetchone() is not None

    async def active_telegram_project_id(self, user_id: int) -> str | None:
        cursor = await self.conn.execute(
            "SELECT active_telegram_project_id FROM user_settings WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return cast(str | None, row["active_telegram_project_id"])

    async def set_active_telegram_project_id(self, user_id: int, project_id: str) -> None:
        await self._write(
            """INSERT INTO user_settings (
                   user_id, model, reasoning, memory_enabled, active_telegram_project_id
               ) VALUES (?, ?, ?, 1, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                   active_telegram_project_id = excluded.active_telegram_project_id,
                   updated_at = CURRENT_TIMESTAMP""",
            (user_id, self.default_model, self.default_reasoning, project_id),
        )

    async def create_telegram_project(self, project: TelegramProject) -> TelegramProject:
        await self._write(
            """INSERT INTO telegram_projects (
                   id, user_id, kind, name, emoji, instructions, openai_conversation_id
               ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                project.id,
                project.user_id,
                project.kind,
                project.name,
                project.emoji,
                project.instructions,
                project.openai_conversation_id,
            ),
        )
        saved = await self.telegram_project(project.user_id, project.id)
        if saved is None:
            raise RuntimeError("Project was not created")
        return saved

    async def telegram_project(self, user_id: int, project_id: str) -> TelegramProject | None:
        cursor = await self.conn.execute(
            "SELECT * FROM telegram_projects WHERE id = ? AND user_id = ?",
            (project_id, user_id),
        )
        row = await cursor.fetchone()
        return self._telegram_project(row) if row else None

    async def skye_telegram_project(self, user_id: int) -> TelegramProject | None:
        cursor = await self.conn.execute(
            "SELECT * FROM telegram_projects WHERE user_id = ? AND kind = 'skye'",
            (user_id,),
        )
        row = await cursor.fetchone()
        return self._telegram_project(row) if row else None

    async def list_telegram_projects(self, user_id: int) -> list[TelegramProject]:
        cursor = await self.conn.execute(
            """SELECT * FROM telegram_projects WHERE user_id = ?
               ORDER BY CASE WHEN kind = 'skye' THEN 0 ELSE 1 END,
                        updated_at DESC, created_at DESC""",
            (user_id,),
        )
        return [self._telegram_project(row) for row in await cursor.fetchall()]

    async def update_telegram_project(
        self,
        user_id: int,
        project_id: str,
        *,
        name: str | None = None,
        emoji: str | None = None,
        instructions: str | None = None,
    ) -> TelegramProject | None:
        current = await self.telegram_project(user_id, project_id)
        if current is None:
            return None
        await self._write(
            """UPDATE telegram_projects
               SET name = ?, emoji = ?, instructions = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ? AND user_id = ?""",
            (
                current.name if name is None else name,
                current.emoji if emoji is None else emoji,
                current.instructions if instructions is None else instructions,
                project_id,
                user_id,
            ),
        )
        return await self.telegram_project(user_id, project_id)

    async def set_telegram_conversation(
        self, user_id: int, project_id: str, conversation_id: str | None
    ) -> None:
        await self._write(
            """UPDATE telegram_projects
               SET openai_conversation_id = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ? AND user_id = ?""",
            (conversation_id, project_id, user_id),
        )

    async def touch_telegram_project(self, user_id: int, project_id: str) -> None:
        await self._write(
            """UPDATE telegram_projects
               SET updated_at = CURRENT_TIMESTAMP
               WHERE id = ? AND user_id = ?""",
            (project_id, user_id),
        )

    async def delete_telegram_project(
        self, user_id: int, project_id: str
    ) -> TelegramProject | None:
        current = await self.telegram_project(user_id, project_id)
        if current is None:
            return None
        if current.kind == "skye":
            raise PermissionError("The Skye project cannot be deleted.")
        await self._write(
            "DELETE FROM telegram_projects WHERE id = ? AND user_id = ? AND kind = 'custom'",
            (project_id, user_id),
        )
        return current

    @staticmethod
    def _telegram_project(row: aiosqlite.Row) -> TelegramProject:
        return TelegramProject(
            id=cast(str, row["id"]),
            user_id=int(row["user_id"]),
            kind=cast(ProjectKind, row["kind"]),
            name=cast(str, row["name"]),
            emoji=cast(str, row["emoji"]),
            instructions=cast(str, row["instructions"]),
            openai_conversation_id=cast(str | None, row["openai_conversation_id"]),
            created_at=cast(str, row["created_at"]),
            updated_at=cast(str, row["updated_at"]),
        )

    async def save_group_message(self, message: GroupMessage) -> None:
        await self._write(
            """INSERT INTO group_messages (
                   chat_id, thread_id, message_id, sender_id, sender_name, sender_username,
                   text, media_kind, media_file_id, reply_to_message_id, reply_sender_name,
                   reply_sender_username, reply_excerpt, sent_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(chat_id, message_id) DO UPDATE SET
                   thread_id = excluded.thread_id,
                   sender_id = excluded.sender_id,
                   sender_name = excluded.sender_name,
                   sender_username = excluded.sender_username,
                   text = excluded.text,
                   media_kind = excluded.media_kind,
                   media_file_id = excluded.media_file_id,
                   reply_to_message_id = excluded.reply_to_message_id,
                   reply_sender_name = excluded.reply_sender_name,
                   reply_sender_username = excluded.reply_sender_username,
                   reply_excerpt = excluded.reply_excerpt,
                   sent_at = excluded.sent_at""",
            (
                message.chat_id,
                message.thread_id,
                message.message_id,
                message.sender_id,
                message.sender_name,
                message.sender_username,
                message.text,
                message.media_kind,
                message.media_file_id,
                message.reply_to_message_id,
                message.reply_sender_name,
                message.reply_sender_username,
                message.reply_excerpt,
                message.sent_at,
            ),
        )

    async def prune_group_messages(self, chat_id: int, thread_id: int, keep: int) -> None:
        await self._write(
            """DELETE FROM group_messages
               WHERE chat_id = ? AND thread_id = ? AND message_id NOT IN (
                   SELECT message_id FROM group_messages
                   WHERE chat_id = ? AND thread_id = ?
                   ORDER BY message_id DESC LIMIT ?
               )""",
            (chat_id, thread_id, chat_id, thread_id, keep),
        )

    async def save_media_group_item(self, item: MediaGroupItem) -> None:
        await self._write(
            """INSERT INTO media_group_items (
                   chat_id, media_group_id, message_id, thread_id, media_kind,
                   file_id, file_unique_id, file_name, mime_type, file_size,
                   width, height, caption, sent_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(chat_id, message_id) DO UPDATE SET
                   media_group_id = excluded.media_group_id,
                   thread_id = excluded.thread_id,
                   media_kind = excluded.media_kind,
                   file_id = excluded.file_id,
                   file_unique_id = excluded.file_unique_id,
                   file_name = excluded.file_name,
                   mime_type = excluded.mime_type,
                   file_size = excluded.file_size,
                   width = excluded.width,
                   height = excluded.height,
                   caption = excluded.caption,
                   sent_at = excluded.sent_at""",
            (
                item.chat_id,
                item.media_group_id,
                item.message_id,
                item.thread_id,
                item.media_kind,
                item.file_id,
                item.file_unique_id,
                item.file_name,
                item.mime_type,
                item.file_size,
                item.width,
                item.height,
                item.caption,
                item.sent_at,
            ),
        )

    async def media_group_id_for_message(self, chat_id: int, message_id: int) -> str | None:
        cursor = await self.conn.execute(
            """SELECT media_group_id FROM media_group_items
               WHERE chat_id = ? AND message_id = ?""",
            (chat_id, message_id),
        )
        row = await cursor.fetchone()
        return cast(str | None, row["media_group_id"]) if row else None

    async def media_group_items(
        self, chat_id: int, media_group_id: str
    ) -> list[MediaGroupItem]:
        cursor = await self.conn.execute(
            """SELECT * FROM media_group_items
               WHERE chat_id = ? AND media_group_id = ?
               ORDER BY message_id""",
            (chat_id, media_group_id),
        )
        return [self._media_group_item(row) for row in await cursor.fetchall()]

    async def claim_media_group(self, chat_id: int, media_group_id: str, message_id: int) -> bool:
        cursor = await self._write(
            """INSERT INTO media_group_claims (chat_id, media_group_id, claimed_message_id)
               VALUES (?, ?, ?)
               ON CONFLICT(chat_id, media_group_id) DO NOTHING""",
            (chat_id, media_group_id, message_id),
        )
        return cursor.rowcount == 1

    @staticmethod
    def _media_group_item(row: aiosqlite.Row) -> MediaGroupItem:
        return MediaGroupItem(
            chat_id=int(row["chat_id"]),
            media_group_id=str(row["media_group_id"]),
            message_id=int(row["message_id"]),
            thread_id=int(row["thread_id"]),
            media_kind=str(row["media_kind"]),
            file_id=str(row["file_id"]),
            file_unique_id=str(row["file_unique_id"]),
            file_name=cast(str | None, row["file_name"]),
            mime_type=cast(str | None, row["mime_type"]),
            file_size=cast(int | None, row["file_size"]),
            width=cast(int | None, row["width"]),
            height=cast(int | None, row["height"]),
            caption=cast(str | None, row["caption"]),
            sent_at=int(row["sent_at"]),
        )

    async def group_messages(
        self,
        chat_id: int,
        thread_id: int,
        *,
        before: int,
        limit: int,
        after: int = 0,
    ) -> list[GroupMessage]:
        cursor = await self.conn.execute(
            """SELECT * FROM group_messages
               WHERE chat_id = ? AND thread_id = ? AND message_id > ? AND message_id < ?
               ORDER BY message_id DESC LIMIT ?""",
            (chat_id, thread_id, after, before, limit),
        )
        rows = list(await cursor.fetchall())
        return [self._group_message(row) for row in reversed(rows)]

    @staticmethod
    def _group_message(row: aiosqlite.Row) -> GroupMessage:
        return GroupMessage(
            chat_id=cast(int, row["chat_id"]),
            thread_id=cast(int, row["thread_id"]),
            message_id=cast(int, row["message_id"]),
            sender_id=cast(int | None, row["sender_id"]),
            sender_name=cast(str, row["sender_name"]),
            sender_username=cast(str | None, row["sender_username"]),
            text=cast(str, row["text"]),
            media_kind=cast(str | None, row["media_kind"]),
            media_file_id=cast(str | None, row["media_file_id"]),
            reply_to_message_id=cast(int | None, row["reply_to_message_id"]),
            reply_sender_name=cast(str | None, row["reply_sender_name"]),
            reply_sender_username=cast(str | None, row["reply_sender_username"]),
            reply_excerpt=cast(str | None, row["reply_excerpt"]),
            sent_at=cast(int, row["sent_at"]),
        )

    async def remember(
        self, scope: Scope, content: str, category: MemoryCategory
    ) -> Memory:
        await self._write(
            """INSERT INTO memories (scope_kind, scope_id, category, content)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(scope_kind, scope_id, content) DO UPDATE SET
                   category = excluded.category,
                   updated_at = CURRENT_TIMESTAMP""",
            (scope.kind, scope.id, category, content),
        )
        cursor = await self.conn.execute(
            """SELECT * FROM memories
               WHERE scope_kind = ? AND scope_id = ? AND content = ?""",
            (scope.kind, scope.id, content),
        )
        row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("Memory was not saved")
        return self._memory(row)

    async def memories(self, scope: Scope, limit: int = 20) -> list[Memory]:
        cursor = await self.conn.execute(
            """SELECT * FROM memories WHERE scope_kind = ? AND scope_id = ?
               ORDER BY updated_at DESC, id DESC LIMIT ?""",
            (scope.kind, scope.id, limit),
        )
        return [self._memory(row) for row in await cursor.fetchall()]

    async def search_memories(
        self, scope: Scope, query: str, limit: int = 8
    ) -> list[Memory]:
        terms = re.findall(r"\w+", query.casefold(), flags=re.UNICODE)[:12]
        if not terms:
            return await self.memories(scope, limit)
        match = " OR ".join(f'"{term}"' for term in terms)
        cursor = await self.conn.execute(
            """SELECT m.* FROM memories_fts
               JOIN memories AS m ON m.id = memories_fts.rowid
               WHERE memories_fts MATCH ? AND m.scope_kind = ? AND m.scope_id = ?
               ORDER BY bm25(memories_fts), m.updated_at DESC LIMIT ?""",
            (match, scope.kind, scope.id, limit),
        )
        return [self._memory(row) for row in await cursor.fetchall()]

    async def forget_memory(self, scope: Scope, memory_id: int) -> bool:
        cursor = await self._write(
            "DELETE FROM memories WHERE id = ? AND scope_kind = ? AND scope_id = ?",
            (memory_id, scope.kind, scope.id),
        )
        return cursor.rowcount > 0

    async def clear_memories(self, scope: Scope) -> int:
        cursor = await self._write(
            "DELETE FROM memories WHERE scope_kind = ? AND scope_id = ?",
            (scope.kind, scope.id),
        )
        return cursor.rowcount

    @staticmethod
    def _memory(row: aiosqlite.Row) -> Memory:
        return Memory(
            id=cast(int, row["id"]),
            scope=Scope(cast(Any, row["scope_kind"]), cast(int, row["scope_id"])),
            category=cast(MemoryCategory, row["category"]),
            content=cast(str, row["content"]),
            created_at=cast(str, row["created_at"]),
            updated_at=cast(str, row["updated_at"]),
        )

    async def list_custom_connectors(self, user_id: int) -> list[CustomConnector]:
        cursor = await self.conn.execute(
            """SELECT * FROM custom_connectors WHERE user_id = ?
               ORDER BY lower(name), updated_at DESC""",
            (user_id,),
        )
        return [self._custom_connector(row) for row in await cursor.fetchall()]

    async def get_custom_connector(self, user_id: int, connector_id: str) -> CustomConnector | None:
        cursor = await self.conn.execute(
            "SELECT * FROM custom_connectors WHERE id = ? AND user_id = ?",
            (connector_id, user_id),
        )
        row = await cursor.fetchone()
        return self._custom_connector(row) if row else None

    async def save_custom_connector(self, connector: CustomConnector) -> CustomConnector:
        await self._write(
            """INSERT INTO custom_connectors (
                   id, user_id, name, url, headers, enabled, created_at, updated_at
               ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
               ON CONFLICT(id) DO UPDATE SET
                   name = excluded.name,
                   url = excluded.url,
                   headers = excluded.headers,
                   enabled = excluded.enabled,
                   updated_at = CURRENT_TIMESTAMP
               WHERE custom_connectors.user_id = excluded.user_id""",
            (
                connector.id,
                connector.user_id,
                connector.name,
                connector.url,
                json.dumps(connector.headers, separators=(",", ":")),
                int(connector.enabled),
            ),
        )
        saved = await self.get_custom_connector(connector.user_id, connector.id)
        if saved is None:
            raise LookupError("Connector not found.")
        return saved

    async def delete_custom_connector(self, user_id: int, connector_id: str) -> bool:
        cursor = await self._write(
            "DELETE FROM custom_connectors WHERE id = ? AND user_id = ?",
            (connector_id, user_id),
        )
        return cursor.rowcount > 0

    async def list_skills(self, scope: Scope) -> list[Skill]:
        cursor = await self.conn.execute(
            """SELECT id, scope_kind, scope_id, openai_skill_id, name, description, filename,
                      archive, file_count, created_by, created_at
               FROM skills WHERE scope_kind = ? AND scope_id = ?
               ORDER BY lower(name), created_at""",
            (scope.kind, scope.id),
        )
        return [self._skill(row) for row in await cursor.fetchall()]

    async def get_skill(self, scope: Scope, skill_id: str) -> Skill | None:
        cursor = await self.conn.execute(
            "SELECT * FROM skills WHERE id = ? AND scope_kind = ? AND scope_id = ?",
            (skill_id, scope.kind, scope.id),
        )
        row = await cursor.fetchone()
        return self._skill(row) if row else None

    async def save_skill(self, skill: Skill) -> Skill:
        await self._write(
            """INSERT INTO skills (
                   id, scope_kind, scope_id, openai_skill_id, name, description,
                   filename, archive, file_count, created_by
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                skill.id,
                skill.scope.kind,
                skill.scope.id,
                skill.openai_skill_id,
                skill.name,
                skill.description,
                skill.filename,
                skill.archive,
                skill.file_count,
                skill.created_by,
            ),
        )
        saved = await self.get_skill(skill.scope, skill.id)
        if saved is None:
            raise LookupError("Skill not found.")
        return saved

    async def delete_skill(self, scope: Scope, skill_id: str) -> Skill | None:
        current = await self.get_skill(scope, skill_id)
        if current is None:
            return None
        await self._write(
            "DELETE FROM skills WHERE id = ? AND scope_kind = ? AND scope_id = ?",
            (skill_id, scope.kind, scope.id),
        )
        return current

    @staticmethod
    def _skill(row: aiosqlite.Row) -> Skill:
        try:
            raw_archive = row["archive"]
        except IndexError:
            raw_archive = None
        archive = bytes(raw_archive) if raw_archive is not None else b""
        return Skill(
            id=cast(str, row["id"]),
            scope=Scope(cast(ScopeKind, row["scope_kind"]), int(row["scope_id"])),
            openai_skill_id=cast(str, row["openai_skill_id"]),
            name=cast(str, row["name"]),
            description=cast(str, row["description"]),
            filename=cast(str, row["filename"]),
            file_count=int(row["file_count"]),
            created_by=int(row["created_by"]),
            created_at=cast(str, row["created_at"]),
            archive=archive,
        )

    async def list_user_toolkits(self, user_id: int) -> list[str]:
        cursor = await self.conn.execute(
            "SELECT slug FROM user_toolkits WHERE user_id = ? ORDER BY slug",
            (user_id,),
        )
        return [cast(str, row["slug"]) for row in await cursor.fetchall()]

    async def add_user_toolkit(self, user_id: int, slug: str) -> None:
        await self._write(
            "INSERT OR IGNORE INTO user_toolkits (user_id, slug) VALUES (?, ?)",
            (user_id, slug),
        )

    async def remove_user_toolkit(self, user_id: int, slug: str) -> bool:
        cursor = await self._write(
            "DELETE FROM user_toolkits WHERE user_id = ? AND slug = ?",
            (user_id, slug),
        )
        return cursor.rowcount > 0

    async def composio_session(
        self, user_id: int, toolkit_key: str
    ) -> tuple[str, str, dict[str, str]] | None:
        cursor = await self.conn.execute(
            """SELECT session_id, mcp_url, mcp_headers FROM composio_session_cache
               WHERE user_id = ? AND toolkit_key = ?""",
            (user_id, toolkit_key),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        raw = json.loads(cast(str, row["mcp_headers"] or "{}"))
        headers = {
            str(key): str(value)
            for key, value in raw.items()
            if isinstance(key, str) and isinstance(value, str)
        }
        return str(row["session_id"]), str(row["mcp_url"]), headers

    async def save_composio_session(
        self,
        user_id: int,
        session_id: str,
        mcp_url: str,
        toolkit_key: str,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        await self._write(
            """INSERT INTO composio_session_cache
               (user_id, toolkit_key, session_id, mcp_url, mcp_headers)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(user_id, toolkit_key) DO UPDATE SET
                   session_id = excluded.session_id,
                   mcp_url = excluded.mcp_url,
                   mcp_headers = excluded.mcp_headers,
                   updated_at = CURRENT_TIMESTAMP""",
            (
                user_id,
                toolkit_key,
                session_id,
                mcp_url,
                json.dumps(dict(headers or {}), separators=(",", ":")),
            ),
        )

    async def delete_composio_sessions(self, user_id: int) -> None:
        await self._write("DELETE FROM composio_session_cache WHERE user_id = ?", (user_id,))

    async def chat_title(self, chat_id: int) -> str:
        cursor = await self.conn.execute(
            "SELECT title FROM known_chats WHERE chat_id = ?", (chat_id,)
        )
        row = await cursor.fetchone()
        return str(row["title"]) if row else "this group"

    async def remember_chat(self, chat_id: int, title: str) -> None:
        label = " ".join(title.split())[:128] or "Group"
        await self._write(
            """INSERT INTO known_chats (chat_id, title)
               VALUES (?, ?)
               ON CONFLICT(chat_id) DO UPDATE SET
                   title = excluded.title,
                   updated_at = CURRENT_TIMESTAMP""",
            (chat_id, label),
        )

    async def shareable_groups(self, user_id: int) -> list[KnownGroup]:
        cursor = await self.conn.execute(
            """SELECT m.chat_id, COALESCE(k.title, 'Group') AS title
               FROM group_messages AS m
               JOIN access_entries AS a
                 ON a.kind = 'chat' AND a.telegram_id = m.chat_id AND a.effect = 'allow'
               LEFT JOIN known_chats AS k ON k.chat_id = m.chat_id
               WHERE m.sender_id = ?
               GROUP BY m.chat_id
               ORDER BY lower(title), m.chat_id""",
            (user_id,),
        )
        return [
            KnownGroup(int(row["chat_id"]), str(row["title"])) for row in await cursor.fetchall()
        ]

    async def save_connector_share(self, share: ConnectorShare) -> ConnectorShare:
        await self._write(
            """INSERT INTO connector_shares (
                   id, chat_id, owner_id, owner_name, kind, ref
               ) VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(chat_id, owner_id, kind, ref) DO UPDATE SET
                   owner_name = excluded.owner_name""",
            (share.id, share.chat_id, share.owner_id, share.owner_name, share.kind, share.ref),
        )
        saved = await self.connector_share_by_target(
            share.chat_id, share.owner_id, share.kind, share.ref
        )
        if saved is None:
            raise RuntimeError("Share was not saved")
        return saved

    async def connector_share(self, share_id: str) -> ConnectorShare | None:
        cursor = await self.conn.execute(
            """SELECT s.id, s.chat_id, COALESCE(k.title, 'Group') AS chat_title,
                      s.owner_id, s.owner_name, s.kind, s.ref, s.created_at
               FROM connector_shares AS s
               LEFT JOIN known_chats AS k ON k.chat_id = s.chat_id
               WHERE s.id = ?""",
            (share_id,),
        )
        row = await cursor.fetchone()
        return self._connector_share(row) if row else None

    async def connector_share_by_target(
        self, chat_id: int, owner_id: int, kind: ConnectorKind, ref: str
    ) -> ConnectorShare | None:
        cursor = await self.conn.execute(
            """SELECT s.id, s.chat_id, COALESCE(k.title, 'Group') AS chat_title,
                      s.owner_id, s.owner_name, s.kind, s.ref, s.created_at
               FROM connector_shares AS s
               LEFT JOIN known_chats AS k ON k.chat_id = s.chat_id
               WHERE s.chat_id = ? AND s.owner_id = ? AND s.kind = ? AND s.ref = ?""",
            (chat_id, owner_id, kind, ref),
        )
        row = await cursor.fetchone()
        return self._connector_share(row) if row else None

    async def list_connector_shares(
        self,
        *,
        chat_id: int | None = None,
        owner_id: int | None = None,
        kind: ConnectorKind | None = None,
        ref: str | None = None,
    ) -> list[ConnectorShare]:
        clauses = ["1 = 1"]
        params: list[object] = []
        if chat_id is not None:
            clauses.append("s.chat_id = ?")
            params.append(chat_id)
        if owner_id is not None:
            clauses.append("s.owner_id = ?")
            params.append(owner_id)
        if kind is not None:
            clauses.append("s.kind = ?")
            params.append(kind)
        if ref is not None:
            clauses.append("s.ref = ?")
            params.append(ref)
        cursor = await self.conn.execute(
            """SELECT s.id, s.chat_id, COALESCE(k.title, 'Group') AS chat_title,
                      s.owner_id, s.owner_name, s.kind, s.ref, s.created_at
               FROM connector_shares AS s
               LEFT JOIN known_chats AS k ON k.chat_id = s.chat_id
               WHERE """
            + " AND ".join(clauses)
            + " ORDER BY lower(s.owner_name), s.created_at",
            params,
        )
        return [self._connector_share(row) for row in await cursor.fetchall()]

    async def count_connector_shares(
        self, *, chat_id: int | None = None, owner_id: int | None = None
    ) -> int:
        clauses = ["1 = 1"]
        params: list[object] = []
        if chat_id is not None:
            clauses.append("chat_id = ?")
            params.append(chat_id)
        if owner_id is not None:
            clauses.append("owner_id = ?")
            params.append(owner_id)
        cursor = await self.conn.execute(
            "SELECT COUNT(*) FROM connector_shares WHERE " + " AND ".join(clauses),
            params,
        )
        row = await cursor.fetchone()
        return int(row[0]) if row else 0

    async def delete_connector_share(self, share_id: str) -> bool:
        cursor = await self._write("DELETE FROM connector_shares WHERE id = ?", (share_id,))
        return cursor.rowcount > 0

    async def delete_connector_shares(
        self, *, owner_id: int, kind: ConnectorKind | None = None, ref: str | None = None
    ) -> None:
        if kind is None:
            await self._write("DELETE FROM connector_shares WHERE owner_id = ?", (owner_id,))
            return
        if ref is None:
            await self._write(
                "DELETE FROM connector_shares WHERE owner_id = ? AND kind = ?",
                (owner_id, kind),
            )
            return
        await self._write(
            "DELETE FROM connector_shares WHERE owner_id = ? AND kind = ? AND ref = ?",
            (owner_id, kind, ref),
        )

    @staticmethod
    def _connector_share(row: aiosqlite.Row) -> ConnectorShare:
        return ConnectorShare(
            id=cast(str, row["id"]),
            chat_id=cast(int, row["chat_id"]),
            chat_title=cast(str, row["chat_title"]),
            owner_id=cast(int, row["owner_id"]),
            owner_name=cast(str, row["owner_name"]),
            kind=cast(ConnectorKind, row["kind"]),
            ref=cast(str, row["ref"]),
            name=cast(str, row["ref"]),
            available=True,
            created_at=cast(str, row["created_at"]),
        )

    @staticmethod
    def _custom_connector(row: aiosqlite.Row) -> CustomConnector:
        raw = json.loads(cast(str, row["headers"]) or "{}")
        headers = {
            str(key): str(value)
            for key, value in raw.items()
            if isinstance(key, str) and isinstance(value, str)
        }
        return CustomConnector(
            id=cast(str, row["id"]),
            user_id=cast(int, row["user_id"]),
            name=cast(str, row["name"]),
            url=cast(str, row["url"]),
            headers=headers,
            enabled=bool(row["enabled"]),
            created_at=cast(str, row["created_at"]),
            updated_at=cast(str, row["updated_at"]),
        )

    async def claim_update(self, update_id: int, payload: str) -> bool:
        async with self.transaction() as connection:
            cursor = await connection.execute(
                "SELECT state FROM updates WHERE update_id = ?", (update_id,)
            )
            row = await cursor.fetchone()
            if row and row["state"] in {"done", "processing"}:
                return False
            await connection.execute(
                """INSERT INTO updates (update_id, payload, state, attempts)
                   VALUES (?, ?, 'processing', 1)
                   ON CONFLICT(update_id) DO UPDATE SET
                       payload = excluded.payload,
                       state = 'processing',
                       attempts = updates.attempts + 1,
                       last_error = NULL,
                       updated_at = CURRENT_TIMESTAMP""",
                (update_id, payload),
            )
        return True

    async def finish_update(self, update_id: int, error: str | None = None) -> None:
        await self._write(
            "UPDATE updates SET state = ?, last_error = ?, updated_at = CURRENT_TIMESTAMP "
            "WHERE update_id = ?",
            ("pending" if error else "done", error, update_id),
        )

    async def drop_pending_updates(self) -> int:
        cursor = await self._write(
            """UPDATE updates
               SET state = 'done', last_error = NULL, updated_at = CURRENT_TIMESTAMP
               WHERE state IN ('pending', 'processing')"""
        )
        return max(cursor.rowcount, 0)

    @staticmethod
    def encode_payload(payload: dict[str, Any]) -> str:
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)

    async def save_automation(self, automation: Automation) -> Automation:
        await self._write(
            """INSERT INTO automations (
                   id, scope_kind, scope_id, thread_id, created_by, name, prompt, kind,
                   cron, timezone, webhook_authorization, enabled, last_fired_at, next_run_at,
                   once
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                automation.id,
                automation.scope.kind,
                automation.scope.id,
                automation.thread_id,
                automation.created_by,
                automation.name,
                automation.prompt,
                automation.kind,
                automation.cron,
                automation.timezone,
                automation.webhook_authorization,
                int(automation.enabled),
                automation.last_fired_at,
                automation.next_run_at,
                int(automation.once),
            ),
        )
        saved = await self.automation(automation.id)
        if saved is None:
            raise RuntimeError("Automation was not saved")
        return saved

    async def automation(self, automation_id: str) -> Automation | None:
        cursor = await self.conn.execute(
            "SELECT * FROM automations WHERE id = ?",
            (automation_id,),
        )
        row = await cursor.fetchone()
        return self._automation(row) if row else None

    async def list_automations(self, scope: Scope, thread_id: int) -> list[Automation]:
        cursor = await self.conn.execute(
            """SELECT * FROM automations
               WHERE scope_kind = ? AND scope_id = ? AND thread_id = ?
               ORDER BY lower(name), created_at""",
            (scope.kind, scope.id, thread_id),
        )
        return [self._automation(row) for row in await cursor.fetchall()]

    async def count_automations(self, scope: Scope, thread_id: int) -> int:
        cursor = await self.conn.execute(
            """SELECT COUNT(*) FROM automations
               WHERE scope_kind = ? AND scope_id = ? AND thread_id = ?""",
            (scope.kind, scope.id, thread_id),
        )
        row = await cursor.fetchone()
        return int(row[0]) if row else 0

    async def update_automation(self, automation: Automation) -> Automation:
        await self._write(
            """UPDATE automations
               SET name = ?, prompt = ?, cron = ?, timezone = ?, enabled = ?,
                   last_fired_at = ?, next_run_at = ?, once = ?
               WHERE id = ? AND scope_kind = ? AND scope_id = ? AND thread_id = ?""",
            (
                automation.name,
                automation.prompt,
                automation.cron,
                automation.timezone,
                int(automation.enabled),
                automation.last_fired_at,
                automation.next_run_at,
                int(automation.once),
                automation.id,
                automation.scope.kind,
                automation.scope.id,
                automation.thread_id,
            ),
        )
        saved = await self.automation(automation.id)
        if saved is None:
            raise LookupError("Automation not found.")
        return saved

    async def delete_automation(self, scope: Scope, thread_id: int, automation_id: str) -> bool:
        cursor = await self._write(
            """DELETE FROM automations
               WHERE id = ? AND scope_kind = ? AND scope_id = ? AND thread_id = ?""",
            (automation_id, scope.kind, scope.id, thread_id),
        )
        return cursor.rowcount > 0

    async def due_automations(self, now: int) -> list[Automation]:
        cursor = await self.conn.execute(
            """SELECT * FROM automations
               WHERE kind = 'schedule' AND enabled = 1
                 AND next_run_at IS NOT NULL AND next_run_at <= ?
               ORDER BY next_run_at, id LIMIT 50""",
            (now,),
        )
        return [self._automation(row) for row in await cursor.fetchall()]

    async def claim_due_automation(
        self,
        automation_id: str,
        expected_next_run_at: int,
        next_run_at: int,
        last_fired_at: int,
    ) -> bool:
        cursor = await self._write(
            """UPDATE automations
               SET next_run_at = ?, last_fired_at = ?
               WHERE id = ? AND kind = 'schedule' AND enabled = 1 AND once = 0
                 AND next_run_at = ?""",
            (next_run_at, last_fired_at, automation_id, expected_next_run_at),
        )
        return cursor.rowcount > 0

    async def claim_due_once_automation(
        self,
        automation_id: str,
        expected_next_run_at: int,
        last_fired_at: int,
    ) -> bool:
        cursor = await self._write(
            """UPDATE automations
               SET next_run_at = NULL, last_fired_at = ?, enabled = 0
               WHERE id = ? AND kind = 'schedule' AND enabled = 1 AND once = 1
                 AND next_run_at = ?""",
            (last_fired_at, automation_id, expected_next_run_at),
        )
        return cursor.rowcount > 0

    @staticmethod
    def _automation(row: aiosqlite.Row) -> Automation:
        return Automation(
            id=cast(str, row["id"]),
            scope=Scope(cast(ScopeKind, row["scope_kind"]), int(row["scope_id"])),
            thread_id=int(row["thread_id"]),
            created_by=int(row["created_by"]),
            name=cast(str, row["name"]),
            prompt=cast(str, row["prompt"]),
            kind=cast(AutomationKind, row["kind"]),
            enabled=bool(row["enabled"]),
            created_at=cast(str, row["created_at"]),
            cron=cast(str | None, row["cron"]),
            timezone=cast(str | None, row["timezone"]),
            webhook_authorization=cast(str | None, row["webhook_authorization"]),
            last_fired_at=cast(int | None, row["last_fired_at"]),
            next_run_at=cast(int | None, row["next_run_at"]),
            once=bool(row["once"]),
        )


def _usage_keys(now: datetime | None = None) -> tuple[str, str]:
    current = now or datetime.now(UTC)
    current = current.replace(tzinfo=UTC) if current.tzinfo is None else current.astimezone(UTC)
    return current.strftime("%Y-%m-%d"), current.strftime("%Y-%m")
