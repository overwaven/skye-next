"""Inspect billing holds read-only, or settle one offline using explicit operator evidence."""

import argparse
import asyncio
import json
import sqlite3
from pathlib import Path

from skye.access import AccessService
from skye.config import HOSTED_MODEL
from skye.db import Database
from skye.pricing import PricingService, TurnUsage
from skye.quota import QuotaService
from skye.sparks import SparkService
from skye.threads import ThreadStore
from skye.turns import TurnService


async def reconcile(args: argparse.Namespace) -> None:
    if not args.confirm_stopped:
        raise ValueError(
            "Stop the bot/API/scheduler and supply --confirm-stopped before settlement"
        )
    if not args.run_id or args.cost_milli is None or not args.evidence:
        raise ValueError("Supply --run-id, --cost-milli and an opaque --evidence reference")
    database = Database(args.database, HOSTED_MODEL, "low")
    await database.open()
    try:
        await ThreadStore(database).require_schema()
        access = AccessService(database, frozenset())
        turns = TurnService(
            database,
            access,
            QuotaService(database, access),
            SparkService(database, PricingService()),
        )
        usage = TurnUsage(
            model=args.model,
            input_tokens=args.input_tokens,
            output_tokens=args.output_tokens,
            cached_tokens=args.cached_tokens,
            images=args.images,
            provider_cost_rub=args.provider_cost_rub,
        )
        await turns.reconcile(
            args.run_id,
            usage,
            tokens=usage.total_tokens,
            cost_milli=args.cost_milli,
            evidence=args.evidence,
        )
        print("Settlement committed once; no request was executed or replayed.")
    finally:
        await database.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--confirm-stopped", action="store_true")
    parser.add_argument("--run-id")
    parser.add_argument("--cost-milli", type=int)
    parser.add_argument("--evidence")
    parser.add_argument("--model")
    parser.add_argument("--input-tokens", type=int, default=0)
    parser.add_argument("--output-tokens", type=int, default=0)
    parser.add_argument("--cached-tokens", type=int, default=0)
    parser.add_argument("--images", type=int, default=0)
    parser.add_argument("--provider-cost-rub", type=float)
    args = parser.parse_args()
    if not args.database.is_file():
        parser.error("Use an existing database")
    if args.list:
        with sqlite3.connect(f"file:{args.database.resolve()}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT q.run_id,r.payer_id,r.funding,q.reason,"
                "r.cost_milli,r.cost_state,(SELECT json_group_array(p.provider_ref) "
                "FROM run_provider_receipts p WHERE p.run_id=r.id) AS provider_refs_json "
                "FROM run_reconciliation q JOIN canonical_runs r "
                "ON r.id=q.run_id WHERE q.resolved=0 ORDER BY q.updated LIMIT 100"
            ).fetchall()
            result = [dict(row) for row in rows]
            for item in result:
                item["provider_refs"] = json.loads(item.pop("provider_refs_json"))
            print(json.dumps(result))
    else:
        asyncio.run(reconcile(args))
