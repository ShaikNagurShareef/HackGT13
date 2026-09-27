"""Housekeeping for Ask PathPro memory: delete stale visitor clones on Backboard.

Lists the account's assistants and deletes those named `pathpro-visitor-*` created longer ago
than --older-than (default 30d). The shared docs assistant is never touched, and a clone with no
readable creation time is kept. Prints counts only: never ids, names, or the API key.

Usage: cd backend && uv run python -m app.tools.prune_backboard [--older-than 30d] [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.services.ask_memory import CLONE_PREFIX
from app.services.backboard import Backboard, BackboardError

DEFAULT_AGE = "30d"
PAGE_SIZE = 100
MAX_PAGES = 100  # 10,000 assistants; a guard against an API that ignores paging
EXIT_OK, EXIT_FAIL, EXIT_NO_KEY = 0, 1, 2
_AGE_RE = re.compile(r"^([1-9]\d{0,3})([dh])$")


@dataclass(frozen=True)
class PruneResult:
    matched: int
    deleted: int
    failed: int


def parse_age(raw: str) -> timedelta:
    """'30d' or '12h' (a positive whole number of days or hours)."""
    match = _AGE_RE.match(raw.strip())
    if match is None:
        raise ValueError("age must look like 30d or 12h")
    amount, unit = int(match.group(1)), match.group(2)
    return timedelta(days=amount) if unit == "d" else timedelta(hours=amount)


def _created(row: dict[str, Any]) -> datetime | None:
    raw = row.get("created_at")
    if not isinstance(raw, str):
        return None
    try:
        created = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return created if created.tzinfo else created.replace(tzinfo=UTC)


def _is_stale_clone(row: dict[str, Any], cutoff: datetime, keep: frozenset[str]) -> bool:
    name, assistant_id = row.get("name"), row.get("assistant_id")
    if not isinstance(name, str) or not name.startswith(CLONE_PREFIX):
        return False
    if not isinstance(assistant_id, str) or not assistant_id or assistant_id in keep:
        return False
    created = _created(row)
    return created is not None and created < cutoff


async def _all_assistants(backboard: Backboard) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for page in range(MAX_PAGES):
        batch = await backboard.list_assistants(skip=page * PAGE_SIZE, limit=PAGE_SIZE)
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
    return rows


async def prune(
    backboard: Backboard,
    older_than: timedelta,
    *,
    now: datetime | None = None,
    dry_run: bool = False,
    keep: frozenset[str] = frozenset(),
) -> PruneResult:
    """Delete visitor clones older than `older_than`; failures are counted, not raised."""
    cutoff = (now or datetime.now(UTC)) - older_than
    stale = [r for r in await _all_assistants(backboard) if _is_stale_clone(r, cutoff, keep)]
    if dry_run:
        return PruneResult(matched=len(stale), deleted=0, failed=0)
    deleted = failed = 0
    for row in stale:
        try:
            await backboard.delete_assistant(str(row["assistant_id"]))
            deleted += 1
        except httpx.HTTPError:
            failed += 1
    return PruneResult(matched=len(stale), deleted=deleted, failed=failed)


def _args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Delete stale Ask PathPro memory clones.")
    parser.add_argument("--older-than", default=DEFAULT_AGE, help="e.g. 30d or 12h")
    parser.add_argument("--dry-run", action="store_true", help="count only; delete nothing")
    return parser.parse_args(list(argv))


async def main_async(cfg: Settings, argv: Sequence[str]) -> int:
    args = _args(argv)
    key = cfg.backboard_api_key.get_secret_value() if cfg.backboard_api_key else ""
    if not key:
        print("BACKBOARD_API_KEY is not set in backend/.env")
        return EXIT_NO_KEY
    try:
        age = parse_age(args.older_than)
    except ValueError as exc:
        print(f"--older-than: {exc}")
        return EXIT_FAIL
    keep = frozenset({cfg.backboard_assistant_id}) if cfg.backboard_assistant_id else frozenset()
    async with httpx.AsyncClient() as client:
        try:
            result = await prune(Backboard(client, key), age, dry_run=args.dry_run, keep=keep)
        except (httpx.HTTPError, BackboardError) as exc:
            print(f"prune failed: {type(exc).__name__}")
            return EXIT_FAIL
    verb = "would delete" if args.dry_run else "deleted"
    print(f"stale visitor clones: {result.matched}")
    print(f"{verb}: {result.matched if args.dry_run else result.deleted}")
    if result.failed:
        print(f"failed: {result.failed}")
    return EXIT_OK if result.failed == 0 else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(asyncio.run(main_async(get_settings(), sys.argv[1:])))
