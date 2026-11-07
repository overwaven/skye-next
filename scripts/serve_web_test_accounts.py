"""Loopback-only synthetic accounts for Next.js owner-isolation checks. No real bot or DB."""

import argparse
import json
import logging
import os
import tempfile
from pathlib import Path

import structlog
from aiohttp import web

from skye.access import AccessService
from skye.config import HOSTED_MODEL, Settings
from skye.db import Database
from skye.models import Scope
from skye.telegram_projects import TelegramProjectService
from skye.threads import ThreadStore
from skye.web_api import create_app
from skye.web_auth import AuthStore


async def fixture(output: Path) -> web.Application:
    if output.exists():
        raise ValueError("Use a new output path for synthetic account credentials")
    temporary = tempfile.TemporaryDirectory(prefix="skye-auth-test-")
    database = Database(Path(temporary.name) / "fixture.db", HOSTED_MODEL, "low")
    await database.open()
    store = ThreadStore(database)
    await store.migrate()
    internal_token = "fixture-internal-token-not-for-production-123456789"
    accounts = {"internal_token": internal_token}
    projects = TelegramProjectService(database, store)
    for owner in (101, 202):
        project = await projects.create(owner, name=f"Private project {owner}")
        thread = await store.sync_project(owner, project.id)
        await store.append(
            Scope("user", owner),
            thread.record.id,
            role="assistant",
            origin="telegram",
            text=f"Private message for account {owner}",
            receipt=f"tg:{owner}:1",
        )
        accounts[str(owner)] = {
            "token": await AuthStore(database).issue(owner),
            "thread_id": thread.record.id,
            "project_id": project.id,
            "logout_tokens": [await AuthStore(database).issue(owner) for _ in range(3)],
        }
    await store.backfill_private_history()
    output.parent.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "w") as file:
        json.dump(accounts, file)
    config = Settings(
        _env_file=None,
        telegram_bot_token="test",
        skye_owner_ids={999},
        skye_web_origin="https://localhost:3004",
        skye_oidc_client_id="fixture",
        skye_oidc_client_secret="unused-fixture-secret",
        skye_web_internal_token=internal_token,
    )
    app = create_app(config, database, store, AccessService(database, frozenset({999})))

    async def cleanup(app: web.Application) -> None:
        await database.close()
        temporary.cleanup()
        output.unlink(missing_ok=True)

    app.on_cleanup.append(cleanup)
    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING))
    web.run_app(fixture(args.output), host="127.0.0.1", port=8092, access_log=None)
