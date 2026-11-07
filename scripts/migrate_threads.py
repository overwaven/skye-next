"""Offline canonical migration. Stop Skye first; database and media are backed up together."""

import argparse
import asyncio
import hashlib
import json
import shutil
import sqlite3
from pathlib import Path

from skye.config import HOSTED_MODEL
from skye.db import Database
from skye.threads import ThreadStore


async def migrate(path: Path, media: Path, backup: Path) -> dict[str, int]:
    if not path.is_file() or not media.is_dir():
        raise ValueError("Both the existing database and media directory are required")
    if backup.resolve().is_relative_to(media.resolve()):
        raise ValueError("The backup must be outside the media source directory")
    backup.mkdir(mode=0o700, parents=True, exist_ok=False)
    with (
        sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True) as source,
        sqlite3.connect(backup / "skye.db") as target,
    ):
        source.backup(target)
    shutil.copytree(media, backup / "files")
    database = Database(path, HOSTED_MODEL, "low")
    await database.open()
    try:
        counts = await ThreadStore(database).migrate()
        row = await database.fetch_one("PRAGMA integrity_check")
        if row is None or row[0] != "ok":
            raise RuntimeError("Database integrity check failed")
        checksums = {}
        for file in sorted(backup.rglob("*")):
            if file.is_file():
                with file.open("rb") as stream:
                    checksums[str(file.relative_to(backup))] = hashlib.file_digest(
                        stream, "sha256"
                    ).hexdigest()
        (backup / "migration.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "counts": counts,
                    "sha256": checksums,
                    "legacy_history": "preserved_not_backfilled",
                }
            )
            + "\n"
        )
        return counts
    finally:
        await database.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--media", type=Path, required=True)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--confirm-stopped", action="store_true", required=True)
    args = parser.parse_args()
    print(asyncio.run(migrate(args.database, args.media, args.backup)))
