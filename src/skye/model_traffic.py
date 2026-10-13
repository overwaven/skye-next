"""Log one structured line per model HTTP call, without storing any payload.

The OpenAI client is the only thing behind this transport, so Dozzle sees chat
completions, images, and audio as ``model_call`` events with status, duration
and byte counts. Request and response bodies are never read or stored: model
tokens and the model id come from the ``turn_finished`` event instead. This
keeps sensitive prompts out of the logs while still surfacing retries, rate
limits and failures.
"""

from __future__ import annotations

import time

import httpx
import structlog

log = structlog.get_logger()


class ModelCallTransport(httpx.AsyncBaseTransport):
    """Wrap an httpx transport and emit a ``model_call`` event per request."""

    def __init__(self, inner: httpx.AsyncBaseTransport) -> None:
        self._inner = inner

    async def aclose(self) -> None:
        await self._inner.aclose()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        started = time.monotonic()
        path = request.url.path
        try:
            response = await self._inner.handle_async_request(request)
        except BaseException as error:
            log.warning(
                "model_call",
                kind="model",
                method=request.method,
                host=request.url.host,
                path=path,
                ok=False,
                duration_ms=_elapsed(started),
                error=type(error).__name__,
            )
            raise
        content_type = response.headers.get("content-type", "")
        log.info(
            "model_call",
            kind="model",
            method=request.method,
            host=request.url.host,
            path=path,
            status=response.status_code,
            ok=response.status_code < 400,
            duration_ms=_elapsed(started),
            stream=content_type.startswith("text/event-stream"),
        )
        return response


def _elapsed(started: float) -> int:
    # Time to response headers; a streamed body is consumed by the caller after
    # this returns, so duration here is time-to-first-byte.
    return int((time.monotonic() - started) * 1000)
