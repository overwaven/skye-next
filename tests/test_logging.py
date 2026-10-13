from __future__ import annotations

import json
import logging

import httpx
import pytest
import structlog

from skye.app import configure_logging
from skye.model_traffic import ModelCallTransport


@pytest.fixture(autouse=True)
def _restore_logging() -> object:
    yield
    structlog.contextvars.clear_contextvars()
    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, "is_json_handler", False):
            root.removeHandler(handler)


def _events(captured: str) -> dict[str, dict[str, object]]:
    rows = [json.loads(line) for line in captured.splitlines() if line.strip()]
    return {str(row["event"]): row for row in rows}


def test_pipeline_jsonifies_app_stdlib_and_context(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging()
    log = structlog.get_logger()
    log.info("app_event", kind="turn", chat_id=7, duration_ms=12)
    logging.getLogger("skye.dependency").warning("lib_event")
    structlog.contextvars.bind_contextvars(run_id="r-1", chat_id=9, user_id=5)
    log.info("ctx_event")

    captured = capsys.readouterr()
    events = _events(captured.out + captured.err)
    assert events["app_event"]["level"] == "info"
    assert events["app_event"]["kind"] == "turn"
    assert events["app_event"]["duration_ms"] == 12
    assert events["app_event"]["chat_id"] == 7
    assert events["lib_event"]["level"] == "warning"
    assert events["ctx_event"]["run_id"] == "r-1"
    assert events["ctx_event"]["chat_id"] == 9
    assert events["ctx_event"]["user_id"] == 5


def test_exception_is_a_traceback_not_true(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging()
    log = structlog.get_logger()
    try:
        raise ValueError("nope")
    except ValueError:
        log.exception("boom")

    captured = capsys.readouterr()
    events = _events(captured.out + captured.err)
    exception = str(events["boom"]["exception"])
    assert "ValueError: nope" in exception
    assert exception != "True"


def test_configure_logging_installs_a_single_handler() -> None:
    configure_logging()
    configure_logging()
    handlers = [
        handler
        for handler in logging.getLogger().handlers
        if getattr(handler, "is_json_handler", False)
    ]
    assert len(handlers) == 1


class _LogSink:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    def info(self, event: str, **fields: object) -> None:
        self.events.append({"event": event, "level": "info", **fields})

    def warning(self, event: str, **fields: object) -> None:
        self.events.append({"event": event, "level": "warning", **fields})


async def test_model_call_transport_reports_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sink = _LogSink()
    monkeypatch.setattr("skye.model_traffic.log", sink)
    transport = ModelCallTransport(httpx.MockTransport(lambda _r: httpx.Response(200)))
    client = httpx.AsyncClient(transport=transport)
    try:
        response = await client.post("https://api.example.com/v1/chat/completions")
    finally:
        await client.aclose()
    assert response.status_code == 200
    call = next(event for event in sink.events if event["event"] == "model_call")
    assert call["kind"] == "model"
    assert call["status"] == 200
    assert call["ok"] is True
    assert call["host"] == "api.example.com"


async def test_model_call_transport_reports_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sink = _LogSink()
    monkeypatch.setattr("skye.model_traffic.log", sink)

    def boom(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    transport = ModelCallTransport(httpx.MockTransport(boom))
    client = httpx.AsyncClient(transport=transport)
    with pytest.raises(httpx.ConnectError):
        await client.get("https://api.example.com/v1/models")
    await client.aclose()
    call = next(event for event in sink.events if event["event"] == "model_call")
    assert call["ok"] is False
    assert call["error"] == "ConnectError"
