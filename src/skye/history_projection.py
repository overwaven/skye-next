"""Conservative Stage 0 projection spike. Never treat assistant prose as public history.

This is not wired into the live database. Production backfill additionally needs channel
delivery receipts for fallback text and media, and an ownership-checked migration manifest.
"""

import json
from collections.abc import Mapping, Sequence
from typing import Any

from .web_contracts import TextPart, VisibleMessage


def project_history(items: Sequence[Mapping[str, Any]], *, thread_id: str) -> list[VisibleMessage]:
    confirmed = {
        item.get("call_id")
        for item in items
        if item.get("type") == "function_call_output" and item.get("output") == "sent"
    }
    messages: list[VisibleMessage] = []
    seen: set[str] = set()
    for index, item in enumerate(items):
        text = ""
        role: str = "user"
        if item.get("role") == "user":
            content = item.get("content")
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                text = "\n".join(
                    str(part["text"])
                    for part in content
                    if isinstance(part, dict)
                    and part.get("type") == "input_text"
                    and isinstance(part.get("text"), str)
                )
        elif (
            item.get("type") == "function_call"
            and item.get("name") in {"send_message", "send_voice"}
            and item.get("call_id") in confirmed
        ):
            call_id = str(item["call_id"])
            if call_id in seen:
                continue
            seen.add(call_id)
            try:
                args = json.loads(str(item.get("arguments", "")))
            except ValueError, TypeError:
                continue
            if isinstance(args, dict) and isinstance(args.get("text"), str):
                text = args["text"]
                role = "assistant"
        if text.strip():
            messages.append(
                VisibleMessage(
                    id=f"legacy:{index}",
                    thread_id=thread_id,
                    sequence=len(messages) + 1,
                    role="assistant" if role == "assistant" else "user",
                    origin="telegram",
                    parts=[TextPart(text=text)],
                )
            )
    return messages
