import json
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.types import Chat, Document, Message, PhotoSize, Voice

from skye.access import AccessService
from skye.config import HOSTED_MODEL
from skye.db import Database
from skye.models import RequestContext, Scope
from skye.pricing import PricingService, TurnUsage
from skye.quota import AllowanceError, QuotaService
from skye.rich import RichMessages
from skye.runtime import RunOutput
from skye.sparks import SparkService
from skye.telegram_projects import TelegramProjectService
from skye.telegram_receipts import activity_category, message_media
from skye.threads import MediaReceipt, ThreadStore
from skye.turns import TurnService


@pytest.fixture
async def database(tmp_path: Path):
    database = Database(tmp_path / "skye.db", HOSTED_MODEL, "low")
    await database.open()
    await ThreadStore(database).migrate()
    try:
        yield database
    finally:
        await database.close()


def service(database):
    access = AccessService(database, frozenset({999}))
    return TurnService(
        database, access, QuotaService(database, access), SparkService(database, PricingService())
    )


async def test_media_ids_are_opaque_owner_scoped_and_deleted_with_transcript(database):
    store = ThreadStore(database)
    thread = await store.create(1, None, "Media")
    item = await store.append(
        Scope("user", 1),
        thread.record.id,
        role="assistant",
        origin="telegram",
        text="",
        receipt="tg:1:55",
        media=(
            MediaReceipt("../../report.pdf", "application/pdf", "private-telegram-file-id", 12),
        ),
    )
    assert item.parts[0].name == "report.pdf"
    assert "private-telegram-file-id" not in item.model_dump_json()
    assert item.parts[0].availability == "unresolved"
    assert (await database.fetch_one("SELECT source_file_id FROM canonical_media"))[
        0
    ] == "private-telegram-file-id"
    with pytest.raises(LookupError):
        await store.history(2, thread.record.id)
    await store.clear(1, thread.record.id)
    assert await database.fetch_all("SELECT * FROM canonical_media") == []


def test_telegram_media_receipts_use_confirmed_objects_not_guessed_names():
    base = dict(message_id=5, date=0, chat=Chat(id=1, type="private"))
    message = Message(**base, voice=Voice(file_id="voice", file_unique_id="v", duration=1))
    assert message_media(message)[0].source_file_id == "voice"
    message = Message(
        **base, photo=[PhotoSize(file_id="photo", file_unique_id="p", width=2, height=2)]
    )
    assert message_media(message)[0].media_type == "image/jpeg"
    message = Message(
        **base, document=Document(file_id="doc", file_unique_id="d", file_name="Report.txt")
    )
    assert message_media(message)[0].name == "Report.txt"


async def test_partial_media_send_records_only_successful_receipts():
    sent = Message(
        message_id=10,
        date=0,
        chat=Chat(id=1, type="private"),
        photo=[PhotoSize(file_id="photo", file_unique_id="p", width=2, height=2)],
    )
    bot = SimpleNamespace(
        send_photo=AsyncMock(side_effect=[sent, RuntimeError("second send failed")])
    )
    rich = RichMessages(bot)
    receipt = AsyncMock()
    with pytest.raises(RuntimeError):
        await rich.send_images_chat(1, 0, [b"first", b"second"], on_delivered=receipt)
    receipt.assert_awaited_once_with(sent)


async def test_private_backfill_has_a_frozen_cutover_and_no_private_assistant_text(database):
    projects = TelegramProjectService(database)
    project = await projects.create(1, name="Old")
    await database.set_telegram_conversation(1, project.id, "old-session")
    await database.add_session_items(
        "old-session",
        [
            {"role": "user", "content": "Old question"},
            {"role": "assistant", "content": "PRIVATE THOUGHTS NEVER PUBLIC"},
            {
                "type": "function_call",
                "name": "send_message",
                "call_id": "sent",
                "arguments": json.dumps({"text": "Old delivered reply"}),
            },
            {"type": "function_call_output", "call_id": "sent", "output": "sent"},
            {
                "type": "function_call",
                "name": "send_message",
                "call_id": "failed",
                "arguments": json.dumps({"text": "UNPROVEN"}),
            },
            {"type": "function_call_output", "call_id": "failed", "output": "PRIVATE TOOL SECRET"},
            {
                "role": "user",
                "content": [{"type": "input_image", "image_url": "secret-provider-url"}],
            },
        ],
    )
    store = ThreadStore(database)
    await store.migrate()
    thread = await store.sync_project(1, project.id)
    # Later runtime replay rows are not historical import candidates.
    await database.add_session_items("old-session", [{"role": "user", "content": "New question"}])
    await store.append(
        Scope("user", 1),
        thread.record.id,
        role="user",
        origin="telegram",
        text="New question",
        receipt="tg:1:100",
    )
    await store.backfill_private_history()
    history = await store.history(1, thread.record.id)
    payload = json.dumps([item.model_dump() for item in history])
    assert all(
        secret not in payload
        for secret in ("PRIVATE THOUGHTS", "PRIVATE TOOL SECRET", "UNPROVEN", "secret-provider-url")
    )
    assert [item.sequence for item in history] == [1, 2, 3, 4]
    assert payload.count("New question") == 1
    assert history[2].parts[0].availability == "unresolved"
    assert (
        await database.fetch_one(
            "SELECT coverage FROM history_imports WHERE thread_id=?", (thread.record.id,)
        )
    )[0] == "partial"
    assert await store.backfill_private_history() == {"threads": 0, "messages": 0}
    await store.clear(1, thread.record.id)
    await store.backfill_private_history()
    assert await store.history(1, thread.record.id) == []


async def test_durable_activity_is_allowlisted_bounded_and_retained_only_24h(database):
    store, turns = ThreadStore(database), service(database)
    thread = await store.create(1, None, "Activity")

    async def operation(admission, run_id):
        await store.record_activity(
            Scope("user", 1), run_id, activity_category("secret-third-party-tool-name"), "running"
        )
        await store.record_activity(Scope("user", 1), run_id, "PRIVATE ARGUMENTS", "completed")
        return RunOutput("", (), usage_tokens=1)

    _, _, run_id = await turns.execute(
        thread, RequestContext(1, "private", 1), "activity", operation
    )
    rows = await database.fetch_all("SELECT category,status FROM run_activity")
    assert [tuple(row) for row in rows] == [("tool", "running")]
    await database.execute_many(
        "INSERT INTO run_activity(run_id,category,status,created) VALUES(?,?,?,?)",
        [(run_id, "web", "completed", time.time()) for _ in range(10005)],
    )
    await store.record_activity(Scope("user", 1), run_id, "web", "completed")
    assert (await database.fetch_one("SELECT COUNT(*) FROM run_activity"))[0] == 10000
    with pytest.raises(LookupError):
        await store.record_activity(Scope("user", 2), run_id, "web", "running")
    await database.execute_write("UPDATE run_activity SET created=?", (time.time() - 86401,))
    await store.prune_activity()
    assert await database.fetch_all("SELECT * FROM run_activity") == []


async def test_known_charge_survives_insufficient_funds_and_settles_once_after_topup(database):
    store, turns = ThreadStore(database), service(database)
    thread = await store.create(1, None, "Paid")
    await database.add_usage(1, 400_000)
    await database.credit_wallet(1, 100)
    operation = AsyncMock(
        return_value=RunOutput(
            "Delivered",
            (),
            usage_tokens=10,
            usage=TurnUsage(input_tokens=6, output_tokens=4, provider_cost_rub=1),
        )
    )
    output, admission, run_id = await turns.execute(
        thread, RequestContext(1, "private", 1), "paid", operation
    )
    await turns.finish_delivery(run_id, complete=True)
    await turns.settle_delivered(run_id, admission, output)
    row = await database.fetch_one(
        "SELECT cost_milli,cost_state FROM canonical_runs WHERE id=?", (run_id,)
    )
    assert tuple(row) == (1000, "pending")
    assert await database.wallet_balance(1) == 100
    assert (await database.fetch_one("SELECT reason FROM run_reconciliation"))[
        0
    ] == "insufficient_funds"
    with pytest.raises(AllowanceError):
        await turns.execute(thread, RequestContext(1, "private", 1), "blocked", operation)
    assert operation.await_count == 1
    await database.credit_wallet(1, 2000)
    await turns.retry_known_settlements(1)
    await turns.retry_known_settlements(1)
    assert await database.wallet_balance(1) == 1100
    assert len(await database.fetch_all("SELECT * FROM wallet_ledger WHERE kind='spend'")) == 1


async def test_unknown_usage_never_becomes_free_and_requires_explicit_evidence(database):
    store, turns = ThreadStore(database), service(database)
    thread = await store.create(1, None, "Unknown")
    operation = AsyncMock(return_value=RunOutput("Delivered", (), usage_complete=False))
    _, _, run_id = await turns.execute(
        thread, RequestContext(1, "private", 1), "unknown", operation
    )
    assert await database.usage_totals(1) == (0, 0)
    assert (await database.fetch_one("SELECT cost_state FROM canonical_runs"))[0] == "unknown"
    await turns.finish_delivery(run_id, complete=True)
    with pytest.raises(AllowanceError):
        await turns.execute(thread, RequestContext(1, "private", 1), "blocked", operation)
    usage = TurnUsage(input_tokens=3, output_tokens=7)
    await turns.reconcile(run_id, usage, tokens=10, cost_milli=0, evidence="provider:usage-123")
    await turns.reconcile(run_id, usage, tokens=10, cost_milli=0, evidence="provider:usage-123")
    assert await database.usage_totals(1) == (10, 10)
    assert (await database.fetch_one("SELECT cost_state FROM canonical_runs"))[0] == "settled"
    with pytest.raises(ValueError):
        await turns.reconcile(run_id, usage, tokens=10, cost_milli=0, evidence="different-evidence")


async def test_provider_receipts_and_delivery_status_survive_partial_execution(database):
    store, turns = ThreadStore(database), service(database)
    thread = await store.create(1, None, "Receipts")

    async def operation(admission, run_id):
        await turns.record_provider_receipt(run_id, "gen-verified-provider-reference")
        await turns.record_provider_receipt(run_id, "PRIVATE TOOL ARGS MUST NOT BE STORED")
        await store.append(
            Scope("user", 1),
            thread.record.id,
            role="assistant",
            origin="telegram",
            text="Already delivered",
            receipt="tg:1:90",
            run_id=run_id,
        )
        raise RuntimeError("provider failed after delivery")

    with pytest.raises(RuntimeError):
        await turns.execute(thread, RequestContext(1, "private", 1), "partial", operation)
    run_id = (await database.fetch_one("SELECT id FROM canonical_runs"))[0]
    await turns.finish_delivery(run_id, complete=False)
    assert (await database.fetch_one("SELECT delivery_state FROM canonical_runs"))[0] == "partial"
    assert [
        row[0] for row in await database.fetch_all("SELECT provider_ref FROM run_provider_receipts")
    ] == ["gen-verified-provider-reference"]
    assert (await database.fetch_one("SELECT reason FROM run_reconciliation"))[
        0
    ] == "execution_failed"


async def test_request_waiting_for_the_same_payer_can_be_cancelled_before_execution(database):
    import asyncio

    store, turns = ThreadStore(database), service(database)
    first = await store.create(1, None, "First")
    second = await store.create(1, None, "Queued")
    started = asyncio.Event()
    release = asyncio.Event()

    async def first_operation(admission, run_id):
        started.set()
        await release.wait()
        return RunOutput("", (), usage_tokens=1)

    second_operation = AsyncMock(return_value=RunOutput("", (), usage_tokens=1))
    context = RequestContext(1, "private", 1)
    task = asyncio.create_task(turns.execute(first, context, "first", first_operation))
    await started.wait()
    queued = asyncio.create_task(turns.execute(second, context, "queued", second_operation))
    # Yield once so the second task registers, with no provider or timer polling.
    await asyncio.sleep(0)
    assert await turns.cancel_thread(Scope("user", 1), second.record.id)
    with pytest.raises(asyncio.CancelledError):
        await queued
    release.set()
    await task
    second_operation.assert_not_awaited()
    assert (await database.fetch_one("SELECT COUNT(*) FROM canonical_runs"))[0] == 1
