#!/usr/bin/env python3
"""Seal or verify a Gate-1 pre-registration against repository history."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from app.validation.gate1 import (
    freeze_pre_registration,
    load_pre_registration,
    verify_git_freeze,
)


def _head(repository: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--repository", type=Path, default=Path("."))
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        verify_git_freeze(args.path, repository=args.repository)
        print("verified: payload digest matches the file at freeze_commit")
        return 0

    prereg = load_pre_registration(args.path)
    frozen = freeze_pre_registration(
        prereg,
        timestamp=datetime.now(timezone.utc).isoformat(),
        commit=_head(args.repository.resolve()),
    )
    args.path.write_text(
        json.dumps(frozen.summary(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"frozen: {frozen.preregistration_sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
