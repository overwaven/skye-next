"""Opaque web media IDs over the shared per-scope MediaLibrary."""

from __future__ import annotations

import mimetypes
import time
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal
from uuid import NAMESPACE_URL, uuid4, uuid5

from .db import Database
from .library import MediaLibrary, sniff_image
from .models import Scope
from .web_contracts import MediaRecord

# Only verified raster images are served inline. Every other uploaded type is
# download-only, so arbitrary files (including HTML, SVG and scripts) can never
# execute in the application origin.
SAFE_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}


@dataclass(frozen=True, slots=True)
class MediaRef:
    record: MediaRecord
    library_name: str


def library_id(user_id: int, name: str, size: int, created: float) -> str:
    return uuid5(NAMESPACE_URL, f"skye:web:{user_id}:{name}:{size}:{int(created)}").hex


def clean_name(name: str) -> str:
    base = PurePosixPath(str(name).replace("\\", "/")).name.strip()[:200]
    base = "".join(char for char in base if char.isprintable() and char not in '\r\n"')
    return base.strip() or "File"


def media_type(name: str, declared: str = "") -> str:
    kind = declared.split(";", 1)[0].strip().lower()
    if not kind or kind == "application/octet-stream":
        guessed, _ = mimetypes.guess_type(name)
        kind = guessed or "application/octet-stream"
    return kind[:128]


class WebMediaStore:
    def __init__(self, database: Database, files: MediaLibrary) -> None:
        self.database = database
        self.files = files

    async def save(
        self, user_id: int, name: str, declared_type: str, data: bytes
    ) -> MediaRef:
        if not data:
            raise ValueError("The file is empty.")
        cleaned = clean_name(name)
        detected = sniff_image(data)
        kind = detected or media_type(cleaned, declared_type)
        scope = Scope("user", user_id)
        entry = self.files.save(scope, data, name=cleaned, mime=kind)
        media_id = uuid4().hex
        now = time.time()
        await self.database.execute_write(
            "INSERT INTO web_uploads(id,user_id,library_name,name,media_type,size,created) "
            "VALUES(?,?,?,?,?,?,?)",
            (media_id, user_id, entry.name, cleaned, entry.mime, entry.size, now),
        )
        return MediaRef(
            MediaRecord(
                id=media_id,
                name=cleaned,
                media_type=entry.mime,
                size=entry.size,
                created_at=now,
                is_image=entry.mime in SAFE_IMAGE_TYPES,
                availability="available",
            ),
            entry.name,
        )

    async def save_generated(
        self, user_id: int, name: str, data: bytes, declared_type: str = ""
    ) -> MediaRef:
        return await self.save(user_id, name, declared_type, data)

    async def list(self, user_id: int) -> list[MediaRef]:
        scope = Scope("user", user_id)
        entries = {entry.name: entry for entry in self.files.entries(scope)}
        rows = await self.database.fetch_all(
            "SELECT * FROM web_uploads WHERE user_id=? ORDER BY created DESC", (user_id,)
        )
        seen: set[str] = set()
        found: list[MediaRef] = []
        for row in rows:
            name = str(row["library_name"])
            seen.add(name)
            entry = entries.get(name)
            found.append(
                MediaRef(
                    MediaRecord(
                        id=str(row["id"]),
                        name=str(row["name"]),
                        media_type=str(row["media_type"]),
                        size=int(row["size"]),
                        created_at=float(row["created"]),
                        is_image=str(row["media_type"]) in SAFE_IMAGE_TYPES,
                        availability="available" if entry is not None else "expired",
                    ),
                    name,
                )
            )
        for name, entry in entries.items():
            if name in seen:
                continue
            media_id = library_id(user_id, entry.name, entry.size, entry.created_at)
            found.append(
                MediaRef(
                    MediaRecord(
                        id=media_id,
                        name=entry.name,
                        media_type=entry.mime,
                        size=entry.size,
                        created_at=entry.created_at,
                        is_image=entry.mime in SAFE_IMAGE_TYPES,
                        availability="available",
                    ),
                    name,
                )
            )
        found.sort(key=lambda item: item.record.created_at, reverse=True)
        return found[:100]

    async def resolve(self, user_id: int, media_id: str) -> MediaRef:
        row = await self.database.fetch_one(
            "SELECT * FROM web_uploads WHERE id=? AND user_id=?", (media_id, user_id)
        )
        entry = None
        if row is not None:
            entry = self.files.entry(Scope("user", user_id), str(row["library_name"]))
            if entry is None:
                raise LookupError("This file has expired.")
            return MediaRef(
                MediaRecord(
                    id=str(row["id"]),
                    name=str(row["name"]),
                    media_type=str(row["media_type"]),
                    size=int(row["size"]),
                    created_at=float(row["created"]),
                    is_image=str(row["media_type"]) in SAFE_IMAGE_TYPES,
                    availability="available",
                ),
                entry.name,
            )
        for candidate in self.files.entries(Scope("user", user_id)):
            candidate_id = library_id(
                user_id, candidate.name, candidate.size, candidate.created_at
            )
            if candidate_id == media_id:
                return MediaRef(
                    MediaRecord(
                        id=media_id,
                        name=candidate.name,
                        media_type=candidate.mime,
                        size=candidate.size,
                        created_at=candidate.created_at,
                        is_image=candidate.mime in SAFE_IMAGE_TYPES,
                        availability="available",
                    ),
                    candidate.name,
                )
        raise LookupError("This file is not available.")

    async def read(self, user_id: int, media_id: str) -> tuple[MediaRef, bytes]:
        ref = await self.resolve(user_id, media_id)
        data = self.files.read(Scope("user", user_id), ref.library_name)
        return ref, data

    async def read_canonical(self, user_id: int, part_id: str) -> tuple[MediaRef, bytes]:
        row = await self.database.fetch_one(
            "SELECT m.source_file_id,t.scope_kind,t.scope_id FROM canonical_media m "
            "JOIN visible_messages v ON v.id=m.message_id "
            "JOIN threads t ON t.id=v.thread_id WHERE m.id=? AND t.scope_kind='user' "
            "AND t.scope_id=?",
            (part_id, user_id),
        )
        if row is None or not row["source_file_id"]:
            raise LookupError("This file is not available.")
        return await self.read(user_id, str(row["source_file_id"]))

    async def delete(self, user_id: int, media_id: str) -> bool:
        row = await self.database.fetch_one(
            "SELECT library_name FROM web_uploads WHERE id=? AND user_id=?", (media_id, user_id)
        )
        if row is not None:
            removed = self.files.remove(Scope("user", user_id), str(row["library_name"]))
            await self.database.execute_write(
                "DELETE FROM web_uploads WHERE id=? AND user_id=?", (media_id, user_id)
            )
            return removed
        try:
            ref = await self.resolve(user_id, media_id)
        except LookupError:
            return False
        return self.files.remove(Scope("user", user_id), ref.library_name)

    @staticmethod
    def disposition(record: MediaRecord) -> Literal["inline", "attachment"]:
        return "inline" if record.is_image else "attachment"
