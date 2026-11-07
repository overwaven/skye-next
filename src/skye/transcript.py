"""Allowlisted legacy projection; assistant prose and arbitrary tool output stay private."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal
from uuid import NAMESPACE_URL, uuid5

from .citations import sanitize_citations
from .web_contracts import FilePart, MessagePart, TextPart


@dataclass(frozen=True)
class LegacyDelivery:
    source_id: int
    role: Literal["user", "assistant"]
    parts: list[MessagePart]


def legacy_deliveries(
    items: Sequence[tuple[int, dict[str, Any]]], thread_id: str
) -> list[LegacyDelivery]:
    # A successful delivery-tool acknowledgement proves only that explicit tool
    # delivery. It never proves visibility of adjacent assistant prose or files.
    confirmed = {
        item.get("call_id")
        for _, item in items
        if item.get("type") == "function_call_output" and item.get("output") == "sent"
    }
    seen: set[str] = set()
    result: list[LegacyDelivery] = []
    for source_id, item in items:
        parts: list[MessagePart] = []
        role: Literal["user", "assistant"] = "user"
        if item.get("role") == "user":
            content = item.get("content")
            if isinstance(content, str):
                if content.strip():
                    parts.append(TextPart(text=content))
            elif isinstance(content, list):
                for index, part in enumerate(content):
                    if not isinstance(part, dict):
                        continue
                    if part.get("type") == "input_text" and isinstance(part.get("text"), str):
                        if part["text"].strip():
                            parts.append(TextPart(text=part["text"]))
                    elif part.get("type") in {"input_image", "input_file", "input_audio"}:
                        kind = str(part["type"])
                        # Never copy URLs, base64, filesystem paths or guessed library names.
                        parts.append(
                            FilePart(
                                file_id=uuid5(
                                    NAMESPACE_URL, f"skye:{thread_id}:{source_id}:{index}"
                                ).hex,
                                name={
                                    "input_image": "Historical image",
                                    "input_file": "Historical file",
                                    "input_audio": "Historical audio",
                                }[kind],
                                media_type={
                                    "input_image": "image/*",
                                    "input_file": "application/octet-stream",
                                    "input_audio": "audio/*",
                                }[kind],
                                availability="unresolved",
                            )
                        )
        elif (
            item.get("type") == "function_call"
            and item.get("name") == "send_message"
            and isinstance(item.get("call_id"), str)
            and item["call_id"] in confirmed
            and item["call_id"] not in seen
        ):
            seen.add(item["call_id"])
            try:
                args = json.loads(item.get("arguments", ""))
            except TypeError, ValueError:
                continue
            if isinstance(args, dict) and isinstance(args.get("text"), str):
                text = sanitize_citations(args["text"]).strip()
                if text:
                    parts.append(TextPart(text=text))
                    role = "assistant"
        if parts:
            result.append(LegacyDelivery(source_id, role, parts))
    return result
