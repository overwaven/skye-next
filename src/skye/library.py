from __future__ import annotations

import asyncio
import os
import re
import shutil
import time
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import structlog
from agents import FunctionTool, function_tool

from .models import Scope

log = structlog.get_logger()

SCOPES_DIRNAME = "scopes"
LAST_USED_NAME = ".skye-last-used"
DEFAULT_TTL_SECONDS = 30 * 86_400
DEFAULT_SCOPE_BYTES = 512 * 1_048_576
DEFAULT_TOTAL_BYTES = 5 * 1_073_741_824
DEFAULT_LIST_LIMIT = 20
MAX_SEEDED_FILES = 20
SKIP_PARTS = frozenset({"__pycache__", ".git", ".venv", "venv", "node_modules", "site-packages"})
_IMAGE_NAME = re.compile(r"image-(\d+)\.[A-Za-z0-9]+")
_IMAGE_MIMES = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
}


def sniff_image(data: bytes) -> str | None:
    """Return the image MIME type when the bytes are a known picture format."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    return None


@dataclass(frozen=True, slots=True)
class MediaEntry:
    name: str
    mime: str
    size: int
    created_at: float

    @property
    def is_image(self) -> bool:
        return self.mime.startswith("image/")


class MediaLibrary:
    """Per-scope durable store for pictures and files the user shared.

    Every incoming attachment and every finished picture is written here, so a
    later message — and any tool — can read it by name. Nothing is tied to the
    conversation window or to the optional Docker sandbox: the bytes live on
    disk under one directory per user (private chat) or chat (group). Scope
    directories are bounded by an idle TTL and a byte cap, swept by a janitor.
    """

    def __init__(
        self,
        root: Path,
        *,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        scope_bytes: int = DEFAULT_SCOPE_BYTES,
        total_bytes: int = DEFAULT_TOTAL_BYTES,
    ) -> None:
        self.root = root
        self.ttl_seconds = ttl_seconds
        self.scope_bytes = scope_bytes
        self.total_bytes = total_bytes

    def scope_dir(self, scope: Scope) -> Path:
        path = self.root / SCOPES_DIRNAME / _scope_key(scope)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save(self, scope: Scope, data: bytes, *, name: str = "", mime: str = "") -> MediaEntry:
        """Store one file, choosing a stable, reusable name.

        Pictures become ``image-<n>.<ext>`` so the model can refer to them by
        name; documents keep their original (sanitized) filename.
        """
        if not data:
            raise ValueError("Cannot store an empty file.")
        directory = self.scope_dir(scope)
        if self._size(directory) + len(data) > self.scope_bytes:
            raise ValueError("The saved-files folder is full. Remove some files first.")
        kind = sniff_image(data)
        if kind is not None:
            mime = kind
            filename = self._next_image_name(directory, _IMAGE_MIMES.get(kind, "png"))
        else:
            mime = mime or "application/octet-stream"
            filename = self._free_name(directory, name)
        target = directory / filename
        target.write_bytes(data)
        self._touch(scope)
        return MediaEntry(filename, mime, len(data), target.stat().st_mtime)

    def entries(self, scope: Scope) -> list[MediaEntry]:
        """Every stored file, oldest first."""
        directory = self.scope_dir(scope)
        found: list[MediaEntry] = []
        try:
            paths = sorted(directory.iterdir())
        except OSError:
            return []
        for path in paths:
            if not path.is_file() or _skip(path.name):
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            found.append(
                MediaEntry(path.name, _mime_for(path.name), stat.st_size, stat.st_mtime)
            )
        found.sort(key=lambda entry: (entry.created_at, entry.name))
        return found

    def images(self, scope: Scope) -> list[MediaEntry]:
        return [entry for entry in self.entries(scope) if entry.is_image]

    def recent(self, scope: Scope, limit: int = MAX_SEEDED_FILES) -> list[MediaEntry]:
        return self.entries(scope)[-limit:] if limit > 0 else []

    def entry(self, scope: Scope, name: str) -> MediaEntry | None:
        if not _safe_name(name):
            return None
        path = self.scope_dir(scope) / name
        if not path.is_file():
            return None
        try:
            stat = path.stat()
        except OSError:
            return None
        return MediaEntry(name, _mime_for(name), stat.st_size, stat.st_mtime)

    def read(self, scope: Scope, name: str) -> bytes:
        directory = self.scope_dir(scope).resolve()
        cleaned = name.replace("\\", "/").strip().lstrip("/")
        if not cleaned or ".." in PurePosixPath(cleaned).parts:
            raise ValueError("Use a saved file name.")
        candidate = (directory / cleaned).resolve()
        if candidate != directory and directory not in candidate.parents:
            raise ValueError("Use a saved file name.")
        return candidate.read_bytes()

    def describe(self, scope: Scope, limit: int = DEFAULT_LIST_LIMIT) -> str:
        """One compact line listing the newest saved files, or an empty string."""
        entries = self.entries(scope)[-limit:]
        if not entries:
            return ""
        parts = [
            f"{entry.name} ({'picture' if entry.is_image else 'file'}, {_size_label(entry.size)})"
            for entry in entries
        ]
        return "; ".join(parts)

    def tool(self, scope: Scope) -> FunctionTool:
        library = self

        @function_tool
        async def list_files() -> str:
            """List pictures and files saved in this chat from earlier messages.

            Use it to find the names to pass to edit_image or to the workspace
            tools. The list is newest last.
            """
            described = library.describe(scope)
            return described or "Nothing has been shared in this chat yet."

        return list_files

    async def run_janitor(self, interval: float = 3_600.0) -> None:
        while True:
            try:
                await asyncio.to_thread(self.cleanup)
            except Exception as error:  # noqa: BLE001 - the loop must survive
                log.warning("library_janitor_failed", error=type(error).__name__)
            await asyncio.sleep(interval)

    def cleanup(self) -> None:
        root = self.root / SCOPES_DIRNAME
        if not root.is_dir():
            return
        now = time.time()
        entries: list[tuple[float, int, Path]] = []
        for scope_dir in root.iterdir():
            if not scope_dir.is_dir():
                continue
            try:
                last_used = (scope_dir / LAST_USED_NAME).stat().st_mtime
            except OSError:
                try:
                    last_used = scope_dir.stat().st_mtime
                except OSError:
                    continue
            entries.append((last_used, _dir_size(scope_dir), scope_dir))
        expired = (
            [item for item in entries if now - item[0] > self.ttl_seconds]
            if self.ttl_seconds > 0
            else []
        )
        for _, _, path in expired:
            shutil.rmtree(path, ignore_errors=True)
            log.info("library_scope_expired", scope=path.name)
        kept = [item for item in entries if item not in expired]
        total = sum(size for _, size, _ in kept)
        if total > self.total_bytes:
            for _, size, path in sorted(kept):
                if total <= self.total_bytes:
                    break
                shutil.rmtree(path, ignore_errors=True)
                total -= size
                log.info("library_scope_evicted", scope=path.name)

    def _next_image_name(self, directory: Path, suffix: str) -> str:
        used: set[int] = set()
        for path in directory.iterdir():
            match = _IMAGE_NAME.fullmatch(path.name)
            if match is not None:
                used.add(int(match.group(1)))
        index = 1
        while index in used:
            index += 1
        return f"image-{index}.{suffix}"

    def _free_name(self, directory: Path, name: str) -> str:
        safe = _safe_name(name) or "file"
        target = PurePosixPath(safe)
        stem, suffix = target.stem or "file", target.suffix
        candidate = f"{stem}{suffix}"
        counter = 1
        while (directory / candidate).exists():
            counter += 1
            candidate = f"{stem}-{counter}{suffix}"
        return candidate

    def _size(self, directory: Path) -> int:
        return _dir_size(directory)

    def _touch(self, scope: Scope) -> None:
        with suppress(OSError):
            marker = self.scope_dir(scope) / LAST_USED_NAME
            marker.write_bytes(str(int(time.time())).encode())


def _safe_name(name: str) -> str | None:
    cleaned = name.replace("\\", "/").strip().lstrip("/")
    if not cleaned or ".." in PurePosixPath(cleaned).parts:
        return None
    return PurePosixPath(cleaned).name.strip()[:200] or None


def _skip(name: str) -> bool:
    return name.startswith(".") or any(part in SKIP_PARTS for part in PurePosixPath(name).parts)


def _mime_for(name: str) -> str:
    suffix = PurePosixPath(name).suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(suffix, "application/octet-stream")


def _size_label(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1_048_576:
        return f"{size / 1024:.0f} KB"
    return f"{size / 1_048_576:.1f} MB"


def _scope_key(scope: Scope) -> str:
    return f"{scope.kind[0]}{scope.id}"


def _dir_size(path: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            with suppress(OSError):
                total += (Path(root) / name).stat().st_size
    return total
