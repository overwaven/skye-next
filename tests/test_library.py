import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any

import pytest
from agents import FunctionTool

from skye.library import LAST_USED_NAME, MediaLibrary
from skye.models import Scope

PNG = b"\x89PNG\r\n\x1a\nhead"
JPEG = b"\xff\xd8\xffhead"


def library(tmp_path: Path, **overrides: Any) -> MediaLibrary:
    options: dict[str, Any] = {
        "ttl_seconds": 30 * 86_400,
        "scope_bytes": 1_048_576,
        "total_bytes": 10_485_760,
        "scope_count": 50,
        "group_count": 20,
    }
    options.update(overrides)
    return MediaLibrary(tmp_path / "files", **options)


def tool_context(name: str, payload: str) -> Any:
    from agents.tool_context import ToolContext

    return ToolContext(
        context=None,
        tool_name=name,
        tool_arguments=payload,
        tool_call_id="call_1",
        run_config=None,
    )


async def invoke(tool: FunctionTool) -> str:
    payload = json.dumps({})
    return await tool.on_invoke_tool(tool_context(tool.name, payload), payload)


def test_pictures_get_sequential_names(tmp_path: Path) -> None:
    store = library(tmp_path)
    scope = Scope("user", 7)

    first = store.save(scope, PNG, name="attached-0.png")
    second = store.save(scope, JPEG, name="attached-1.jpg")

    assert first.name == "image-1.png"
    assert second.name == "image-2.jpg"
    assert [entry.name for entry in store.images(scope)] == ["image-1.png", "image-2.jpg"]
    assert store.read(scope, "image-1.png") == PNG
    assert store.entry(scope, "image-1.png") is not None
    assert store.entry(scope, "nope.png") is None


def test_documents_keep_their_names_and_avoid_collisions(tmp_path: Path) -> None:
    store = library(tmp_path)
    scope = Scope("user", 7)

    one = store.save(scope, b"report", name="report.txt", mime="text/plain")
    two = store.save(scope, b"report again", name="report.txt", mime="text/plain")

    assert one.name == "report.txt"
    assert two.name == "report-2.txt"
    assert not store.images(scope)


def test_describe_lists_the_newest_files(tmp_path: Path) -> None:
    store = library(tmp_path)
    scope = Scope("user", 7)
    store.save(scope, PNG)
    store.save(scope, b"notes", name="notes.txt")

    described = store.describe(scope)

    assert "image-1.png (picture," in described
    assert "notes.txt (file," in described


async def test_tool_lists_saved_files(tmp_path: Path) -> None:
    store = library(tmp_path)
    scope = Scope("user", 7)
    empty = store.tool(scope)

    assert await invoke(empty) == "Nothing has been shared in this chat yet."

    store.save(scope, PNG)
    listed = await invoke(store.tool(scope))

    assert "image-1.png" in listed


def test_read_rejects_a_traversal(tmp_path: Path) -> None:
    store = library(tmp_path)
    scope = Scope("user", 7)
    store.save(scope, PNG)

    with pytest.raises(ValueError):
        store.read(scope, "../secret")


def test_scope_byte_cap_is_enforced(tmp_path: Path) -> None:
    store = library(tmp_path, scope_bytes=8)
    scope = Scope("user", 7)
    store.save(scope, b"12345")

    with pytest.raises(ValueError, match="full"):
        store.save(scope, b"67890")


def test_oldest_files_are_evicted_past_the_count(tmp_path: Path) -> None:
    store = library(tmp_path, scope_count=3)
    scope = Scope("user", 7)

    for index in range(4):
        store.save(scope, PNG + bytes([index]))

    assert [entry.name for entry in store.images(scope)] == [
        "image-2.png",
        "image-3.png",
        "image-4.png",
    ]
    assert store.entry(scope, "image-1.png") is None


def test_groups_keep_fewer_files_than_private_chats(tmp_path: Path) -> None:
    store = library(tmp_path, scope_count=50, group_count=2)
    chat = Scope("chat", -100)
    private = Scope("user", 7)

    for index in range(4):
        store.save(chat, PNG + bytes([index]))
        store.save(private, PNG + bytes([index]))

    assert [entry.name for entry in store.images(chat)] == ["image-3.png", "image-4.png"]
    assert len(store.images(private)) == 4


def test_cleanup_enforces_the_count_on_existing_files(tmp_path: Path) -> None:
    store = library(tmp_path, scope_count=2)
    scope = Scope("user", 7)
    directory = store.scope_dir(scope)
    for index in range(4):
        path = directory / f"image-{index + 1}.png"
        path.write_bytes(PNG)
        os.utime(path, (1_000 + index, 1_000 + index))

    store.cleanup()

    assert [entry.name for entry in store.images(scope)] == ["image-3.png", "image-4.png"]


def test_cleanup_removes_expired_scopes(tmp_path: Path) -> None:
    store = library(tmp_path, ttl_seconds=10)
    old = store.scope_dir(Scope("user", 1))
    store.save(Scope("user", 1), PNG)
    marker = old / LAST_USED_NAME
    stale = time.time() - 3_600
    os.utime(marker, (stale, stale))
    fresh = store.scope_dir(Scope("user", 2))
    store.save(Scope("user", 2), PNG)

    store.cleanup()

    assert not old.exists()
    assert fresh.exists()


async def test_janitor_survives_and_repeats(tmp_path: Path, monkeypatch: Any) -> None:
    store = library(tmp_path, ttl_seconds=0)
    store.scope_dir(Scope("user", 1))

    async def fast_sleep(_seconds: float) -> None:
        raise asyncio.CancelledError

    monkeypatch.setattr("skye.library.asyncio.sleep", fast_sleep)
    with pytest.raises(asyncio.CancelledError):
        await store.run_janitor(interval=0.001)
