import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from skye.history_projection import project_history
from skye.web_contracts import EventEnvelope, SendRequest


@pytest.mark.parametrize(
    "case",
    json.loads(Path("tests/fixtures/web_history.json").read_text()),
    ids=lambda case: case["case"],
)
def test_visible_projection(case: dict) -> None:
    messages = project_history(case["items"], thread_id="fixture-thread")
    assert [message.parts[0].text for message in messages] == case["expected"]
    assert "PRIVATE_" not in str([message.model_dump() for message in messages])


def test_send_contract_has_no_client_owner() -> None:
    with pytest.raises(ValidationError):
        SendRequest(request_id="request-00000001", text="Hello", user_id=42)


def test_event_rejects_raw_tool_payload() -> None:
    with pytest.raises(ValidationError):
        EventEnvelope.model_validate(
            {"cursor": "1", "data": {"type": "tool", "arguments": "secret"}}
        )
