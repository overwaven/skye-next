import asyncio
import runpy
import shutil
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from skye.access import AccessService
from skye.automations import AutomationService
from skye.config import HOSTED_MODEL
from skye.db import Database
from skye.models import RequestContext, Scope
from skye.pricing import PricingService
from skye.quota import QuotaService
from skye.runtime import RunOutput
from skye.sparks import SparkService
from skye.telegram_projects import TelegramProjectService
from skye.threads import ThreadStore
from skye.turns import Admission, BusyTurn, DuplicateRun, TurnService


@pytest.fixture
async def database(tmp_path: Path):
    database = Database(tmp_path / "test.db", HOSTED_MODEL, "low")
    await database.open()
    try:
        yield database
    finally:
        await database.close()


async def test_migration_preserves_sessions_and_is_repeat_safe(database: Database):
    projects = TelegramProjectService(database)
    await database.save_conversation(1, 0, "old-private")
    default = await projects.ensure_skye(1)
    custom = await projects.create(1, name="Work", instructions="Be precise")
    await database.set_telegram_conversation(1, custom.id, "work-ref")
    await database.save_conversation(-100, 4, "group-topic")
    await database.add_session_items("work-ref", [{"role": "user", "content": "Keep this"}])
    store = ThreadStore(database)
    counts = await store.migrate()
    assert counts == {"projects": 2, "private": 0, "groups": 1, "automations": 0}
    first = await store.sync_project(1, default.id)
    work = await store.sync_project(1, custom.id)
    assert first.session_ref == "old-private"
    assert first.record.project_id is None
    assert work.session_ref == "work-ref"
    assert work.instructions == "Be precise"
    assert await store.migrate() == dict.fromkeys(counts, 0)
    assert len(await database.session_items("work-ref")) == 1
    assert len(await store.list_threads(1)) == 2
    assert await store.list_threads(2) == []
    with pytest.raises(LookupError):
        await store.require(Scope("user", 2), work.record.id)
    assert (await database.fetch_one("PRAGMA integrity_check"))[0] == "ok"


async def test_selected_thread_is_independent_and_project_delete_retains_history(
    database: Database,
):
    await ThreadStore(database).migrate()
    store = ThreadStore(database)
    projects = TelegramProjectService(database, store)
    project = await projects.create(1, name="Work")
    original = await store.sync_project(1, project.id)
    another = await store.create(1, project.id, "Independent")
    assert await projects.conversation_id(project) == original.session_ref
    await store.select(1, project.id, another.record.id)
    assert await projects.conversation_id(project) == another.session_ref
    await store.append(
        Scope("user", 1),
        another.record.id,
        role="user",
        origin="telegram",
        text="Keep me",
        receipt="tg:1:10",
    )
    await projects.delete(1, project.id)
    assert (await store.require(Scope("user", 1), another.record.id)).record.project_id is None
    assert len(await store.history(1, another.record.id)) == 1
    assert (
        await store.require(Scope("user", 1), original.record.id)
    ).session_ref == original.session_ref


async def test_receipts_are_repeat_safe_and_history_is_bounded(database: Database):
    store = ThreadStore(database)
    await store.migrate()
    thread = await store.create(1, None, "Test")
    for n in range(4):
        await store.append(
            Scope("user", 1),
            thread.record.id,
            role="assistant",
            origin="telegram",
            text=f"Reply {n}",
            receipt=f"tg:1:{n}",
        )
    duplicate = await store.append(
        Scope("user", 1),
        thread.record.id,
        role="assistant",
        origin="telegram",
        text="Not inserted",
        receipt="tg:1:0",
    )
    assert duplicate.sequence == 1
    page = await store.history(1, thread.record.id, before=4, limit=2)
    assert [item.sequence for item in page] == [2, 3]
    with pytest.raises(LookupError):
        await store.history(2, thread.record.id)
    await store.clear(1, thread.record.id)
    assert await store.history(1, thread.record.id) == []


async def test_builtin_instructions_never_spread_to_independent_unassigned_threads(database):
    store = ThreadStore(database)
    await store.migrate()
    projects = TelegramProjectService(database, store)
    default = await projects.ensure_skye(1)
    initial = await store.sync_project(1, default.id)
    await projects.update(1, default.id, instructions="Default conversation only")
    independent = await store.create(1, None, "Independent")
    await store.select(1, default.id, independent.record.id)
    selected = await store.sync_project(1, default.id)
    assert selected.instructions == ""
    assert (
        await store.require(Scope("user", 1), initial.record.id)
    ).instructions == "Default conversation only"


def turns(database: Database) -> TurnService:
    access = AccessService(database, frozenset({999}))
    return TurnService(
        database, access, QuotaService(database, access), SparkService(database, PricingService())
    )


async def test_durable_run_idempotency_and_atomic_free_settlement(database: Database):
    store = ThreadStore(database)
    await store.migrate()
    thread = await store.create(1, None, "Test")
    service = turns(database)
    calls = 0

    async def operation(admission: Admission, run_id: str):
        nonlocal calls
        calls += 1
        return RunOutput("", (), usage_tokens=12)

    context = RequestContext(1, "private", 1)
    output, admission, run_id = await service.execute(thread, context, "request1", operation)
    await service.settle(run_id, admission, output)
    with pytest.raises(DuplicateRun):
        await service.execute(thread, context, "request1", operation)
    assert calls == 1
    assert await database.usage_totals(1) == (12, 12)
    assert (await database.fetch_one("SELECT state FROM canonical_runs WHERE id=?", (run_id,)))[
        0
    ] == "completed"


async def test_busy_cancel_and_interrupted_runs_are_not_replayed(database: Database):
    store = ThreadStore(database)
    await store.migrate()
    thread = await store.create(1, None, "Test")
    service = turns(database)
    context = RequestContext(1, "private", 1)
    started = asyncio.Event()

    async def operation(admission: Admission, run_id: str):
        started.set()
        await asyncio.Event().wait()
        return RunOutput("", ())

    task = asyncio.create_task(service.execute(thread, context, "request", operation))
    await started.wait()
    with pytest.raises(BusyTurn):
        await service.execute(thread, context, "second", operation)
    run_id = (await database.fetch_one("SELECT id FROM canonical_runs"))[0]
    with pytest.raises(LookupError):
        await service.cancel(2, run_id)
    assert await service.cancel(1, run_id)
    with pytest.raises(asyncio.CancelledError):
        await task
    assert (await database.fetch_one("SELECT state FROM canonical_runs"))[0] == "cancelled"
    await database.execute_write("UPDATE canonical_runs SET state='running'")
    assert await store.interrupt_runs() == 1
    with pytest.raises(DuplicateRun):
        await service.execute(thread, context, "request", operation)


async def test_automation_target_does_not_follow_telegram_selection(database: Database):
    store = ThreadStore(database)
    await store.migrate()
    projects = TelegramProjectService(database, store)
    project = await projects.create(1, name="Work")
    original = await store.sync_project(1, project.id)
    service = AutomationService(database, None, store)
    item = await service.create_schedule(
        RequestContext(1, "private", 1), name="Daily", cron="0 9 * * *", task="Report progress"
    )
    other = await store.create(1, project.id, "Other")
    await store.select(1, project.id, other.record.id)
    row = await database.fetch_one(
        "SELECT thread_id FROM automation_thread_bindings WHERE automation_id=?", (item.id,)
    )
    assert row[0] == original.record.id
    from skye.telegram import TelegramApp

    app = object.__new__(TelegramApp)
    app.access = AccessService(database, frozenset({999}))
    app.database, app.telegram_projects = database, projects
    app._stream_turn = AsyncMock()
    await app.fire_automation(item)
    assert app._stream_turn.await_args.kwargs["conversation_id"] == original.session_ref


async def test_group_reset_clears_only_its_canonical_transcript(database: Database):
    from skye.conversations import ConversationService

    store = ThreadStore(database)
    await store.migrate()
    conversations = ConversationService(database, store)
    ref = await conversations.get_or_create(-100, 7)
    thread = await store.group(-100, 7, ref)
    await store.append(
        Scope("chat", -100),
        thread.record.id,
        role="user",
        origin="telegram",
        text="Group text",
        receipt="tg:-100:123",
    )
    assert await store.list_threads(1) == []
    assert await conversations.reset(-100, 7)
    assert await database.fetch_all("SELECT * FROM visible_messages") == []
    assert (await store.group(-100, 7, ref)).record.id == thread.record.id


async def test_backup_and_restore_rehearsal_uses_complete_legacy_snapshot(
    database: Database, tmp_path: Path
):
    project = await TelegramProjectService(database).create(1, name="Original")
    await database.credit_wallet(1, 12345)
    path = database.path
    await database.close()
    media = tmp_path / "files"
    media.mkdir()
    (media / "example.txt").write_text("material")
    backup = tmp_path / "backup"
    migrate = runpy.run_path("scripts/migrate_threads.py")["migrate"]
    await migrate(path, media, backup)
    assert (backup / "files/example.txt").read_text() == "material"
    # Restore into a different file: never overwrite an active database.
    restored = tmp_path / "restored.db"
    shutil.copy2(backup / "skye.db", restored)
    with sqlite3.connect(restored) as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert (
            conn.execute("SELECT name FROM telegram_projects WHERE id=?", (project.id,)).fetchone()[
                0
            ]
            == "Original"
        )
        assert (
            conn.execute("SELECT balance_milli FROM wallets WHERE user_id=1").fetchone()[0] == 12345
        )
    with pytest.raises(ValueError):
        await migrate(path, media, media / "unsafe-backup")
    await database.open()


async def test_paid_settlement_is_once_per_run_and_payer_is_serialized(database: Database):
    from skye.pricing import TurnUsage

    store = ThreadStore(database)
    await store.migrate()
    first, second = await store.create(1, None, "First"), await store.create(1, None, "Second")
    service = turns(database)
    await database.add_usage(1, 400_000)
    await database.credit_wallet(1, 10_000)
    active, maximum = 0, 0

    async def operation(admission: Admission, run_id: str):
        nonlocal active, maximum
        assert admission.paid
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0.01)
        active -= 1
        return RunOutput("", (), usage_tokens=12, usage=TurnUsage(provider_cost_rub=1))

    context = RequestContext(1, "private", 1)
    results = await asyncio.gather(
        service.execute(first, context, "one", operation),
        service.execute(second, context, "two", operation),
    )
    for output, admission, run_id in results:
        await service.settle(run_id, admission, output)
    assert maximum == 1
    assert await database.wallet_balance(1) == 8_000
    ledger = await database.fetch_all("SELECT reference FROM wallet_ledger WHERE kind='spend'")
    assert len(ledger) == 2 and all(row[0].startswith("run:") for row in ledger)


async def test_telegram_adapter_uses_shared_turn_service_and_records_only_receipted_text(database):
    from aiogram.types import Chat, Message, User

    from skye.rich import RichMessages
    from skye.telegram import TelegramApp

    store = ThreadStore(database)
    await store.migrate()
    projects = TelegramProjectService(database, store)
    project = await projects.create(1, name="Test")
    thread = await store.sync_project(1, project.id)
    app = object.__new__(TelegramApp)
    app.database, app.telegram_projects = database, projects
    app.turns = turns(database)
    app.sparks, app.quota = app.turns.sparks, app.turns.quota
    app._can_edit = AsyncMock(return_value=False)
    app._show_free_spend = AsyncMock()
    app.growth = SimpleNamespace(completed_task=AsyncMock(return_value=False))
    incoming = Message(
        message_id=1,
        date=0,
        chat=Chat(id=1, type="private"),
        from_user=User(id=1, is_bot=False, first_name="User"),
        text="Hello",
    )
    seq = 10

    async def send(*args, **kwargs):
        nonlocal seq
        seq += 1
        return incoming.model_copy(update={"message_id": seq})

    async def run(*args, **kwargs):
        assert kwargs["run_key"] == f"thread:{thread.record.id}"
        assert args[0].conversation_thread_id == thread.record.id
        await kwargs["on_reply"]("Visible reply")
        return RunOutput("PRIVATE INTERNAL TEXT", (), usage_tokens=12, sent=1)

    app.runtime = SimpleNamespace(run=AsyncMock(side_effect=run))
    app.rich = SimpleNamespace(
        draft=AsyncMock(),
        send=AsyncMock(side_effect=send),
        output=RichMessages.output,
        delete=AsyncMock(),
    )
    context = RequestContext(1, "private", 1)
    await app._stream_turn(incoming, context, "Hello", conversation_id=thread.session_ref)
    await app._stream_turn(incoming, context, "Hello", conversation_id=thread.session_ref)
    assert app.runtime.run.await_count == 1
    history = await store.history(1, thread.record.id)
    assert [part.text for item in history for part in item.parts] == ["Hello", "Visible reply"]
    assert await database.usage_totals(1) == (12, 12)
