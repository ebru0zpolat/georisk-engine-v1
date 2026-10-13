#!/usr/bin/env python3
"""Trusted CLI for provisioning and revoking API keys (WP-1: identity/tenancy).

The plaintext key is printed exactly once, at creation; only its digest is
stored, so a lost key cannot be recovered. Run against the configured database
(``DATABASE_URL``); production should set ``API_KEY_PEPPER`` so a leaked dump
cannot be replayed.

Examples::

    python scripts/api_key_ops.py generate --organisation acme --scope risk:read
    python scripts/api_key_ops.py list --organisation acme
    python scripts/api_key_ops.py revoke k_0123456789abcdef01234567
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone

from app.core.security import SCOPES
from app.db.session import get_session_factory
from app.services.api_key_service import create_api_key, list_api_keys, revoke_api_key


async def _generate(args: argparse.Namespace) -> int:
    session_factory = get_session_factory()
    async with session_factory() as session:
        plaintext, record = await create_api_key(
            session,
            organisation_id=args.organisation,
            scopes=args.scope,
            label=args.label,
            ttl_days=args.expires_in_days,
        )
        await session.commit()
    print("API key created — copy it now, it is never shown again.")
    print(f"  key_id    : {record.id}")
    print(f"  organisation_id : {record.organisation_id}")
    print(f"  label     : {record.label or '(none)'}")
    print(f"  scopes    : {', '.join(sorted(record.scopes)) or '(none)'}")
    if record.expires_at is not None:
        print(f"  expires_at: {record.expires_at.isoformat()}")
    print(f"  api_key   : {plaintext}")
    return 0


async def _list(args: argparse.Namespace) -> int:
    session_factory = get_session_factory()
    async with session_factory() as session:
        records = await list_api_keys(session, organisation_id=args.organisation)
    if not records:
        print(f"No API keys for organisation {args.organisation!r}.")
        return 0
    print(f"{'key_id':<28}  {'label':<24}  {'state':<8}  scopes")
    for record in records:
        if record.revoked_at is not None:
            state = "revoked"
        elif record.expires_at is not None and _expired(record.expires_at):
            state = "expired"
        else:
            state = "active"
        print(
            f"{record.id:<28}  {(record.label or '-'):<24}  {state:<8}  "
            f"{', '.join(sorted(record.scopes)) or '(none)'}"
        )
    return 0


async def _revoke(args: argparse.Namespace) -> int:
    session_factory = get_session_factory()
    async with session_factory() as session:
        revoked = await revoke_api_key(session, key_id=args.key_id)
        await session.commit()
    if not revoked:
        print(f"No API key with id {args.key_id!r}.", file=sys.stderr)
        return 1
    print(f"Revoked {args.key_id}.")
    return 0


def _expired(expires_at: datetime) -> bool:
    now = datetime.now(timezone.utc)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= now


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="Generate and store a new API key.")
    gen.add_argument("--organisation", required=True, help="Owning organisation id.")
    gen.add_argument("--label", default="", help="Human-readable label.")
    gen.add_argument(
        "--scope",
        action="append",
        default=[],
        choices=list(SCOPES),
        help="Scope to grant (repeatable).",
    )
    gen.add_argument("--expires-in-days", type=int, default=None)
    gen.set_defaults(func=_generate)

    lst = sub.add_parser("list", help="List keys for an organisation.")
    lst.add_argument("--organisation", required=True)
    lst.set_defaults(func=_list)

    rev = sub.add_parser("revoke", help="Soft-revoke a key by id.")
    rev.add_argument("key_id")
    rev.set_defaults(func=_revoke)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return asyncio.run(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
