"""Exercise the Stage 0 SSE lab through the Next.js same-origin development rewrite."""

import time

import httpx

ORIGIN = "http://localhost:3000"

with httpx.Client(base_url=ORIGIN, timeout=10) as client:
    response = client.post("/api/v1/spike/session", headers={"Origin": ORIGIN})
    response.raise_for_status()
    started = time.monotonic()
    with client.stream("GET", "/api/v1/spike/events") as stream:
        stream.raise_for_status()
        assert stream.headers["content-type"] == "text/event-stream"
        lines = stream.iter_lines()
        assert next(lines) == "retry: 1000"
        assert next(lines) == ": heartbeat"
        first_byte = time.monotonic() - started
        body = "\n".join(lines)
    assert "id: 1" in body and "id: 4" in body
    response = client.get("/api/v1/spike/events", headers={"Last-Event-ID": "2"})
    response.raise_for_status()
    assert "id: 1" not in response.text and "id: 2" not in response.text
    assert "id: 3" in response.text and "id: 4" in response.text
    assert first_byte < 0.5, f"Heartbeat buffered: {first_byte:.3f}s"
    print(f"Next.js → Python SSE: heartbeat {first_byte:.3f}s; replay 3/4 only; passed.")
