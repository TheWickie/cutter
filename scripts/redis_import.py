#!/usr/bin/env python3
"""
Import users with ID codes into Redis.

Usage examples:
  REDIS_URL=rediss://:password@host:port/0 \
    python scripts/redis_import.py --csv docs/seed.sample.csv

  python scripts/redis_import.py --jsonl docs/seed.sample.jsonl --overwrite

The script writes:
  - idcode_to_user:{IDCODE} -> user_id
  - number_to_user:{number} -> user_id (if provided)
  - user:{user_id} hash with name, id_code, number?

It skips duplicates unless --overwrite is specified.
"""

import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
from typing import Dict, Iterable, Optional

# Ensure local imports work when running from repo root
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from core.redis_store import get_client  # type: ignore

IDCODE_RE = re.compile(r"^[A-Za-z0-9-]{4,32}$")


def normalize_idcode(code: str) -> str:
    return code.strip().upper()


def validate_row(row: Dict[str, str]) -> Optional[str]:
    name = (row.get("name") or "").strip()
    id_code_raw = (row.get("id_code") or "").strip()
    number = (row.get("number") or "").strip()
    if not name:
        return "missing name"
    if not id_code_raw:
        return "missing id_code"
    if not IDCODE_RE.match(id_code_raw):
        return "invalid id_code format"
    if number and not re.match(r"^[0-9+]{6,20}$", number):
        return "invalid number format"
    return None


def iter_csv(path: str) -> Iterable[Dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row


def iter_jsonl(path: str) -> Iterable[Dict[str, str]]:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def upsert_user(row: Dict[str, str], overwrite: bool = False) -> str:
    r = get_client()
    now = dt.datetime.utcnow().isoformat()

    id_code = normalize_idcode(row["id_code"])
    name = row["name"].strip()
    number = (row.get("number") or "").strip() or None

    existing_uid = r.get(f"idcode_to_user:{id_code}")
    if existing_uid and not overwrite:
        return existing_uid

    user_id = existing_uid or __import__("uuid").uuid4().hex

    # Reverse mappings
    r.set(f"idcode_to_user:{id_code}", user_id)
    if number:
        r.set(f"number_to_user:{number}", user_id)

    # User hash
    r.hset(
        f"user:{user_id}",
        mapping={
            "name": name,
            "number": number or "",
            "id_code": id_code,
            "authed": "1",
            "created_at": now,
            "last_seen": now,
        },
    )
    return user_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Import users with ID codes into Redis")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--csv", dest="csv_path", help="CSV file with id_code,name,number")
    g.add_argument("--jsonl", dest="jsonl_path", help="JSONL file with objects including id_code,name,number")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing users for duplicate id_code")

    args = parser.parse_args()

    source: Iterable[Dict[str, str]]
    if args.csv_path:
        source = iter_csv(args.csv_path)
    else:
        source = iter_jsonl(args.jsonl_path)

    imported = 0
    skipped = 0
    for row in source:
        err = validate_row(row)
        if err:
            print(f"skip row: {err}: {row}")
            skipped += 1
            continue
        uid_before = get_client().get(f"idcode_to_user:{normalize_idcode(row['id_code'])}")
        uid = upsert_user(row, overwrite=args.overwrite)
        if uid_before and not args.overwrite:
            print(f"skip duplicate id_code -> user_id={uid}")
            skipped += 1
        else:
            print(f"imported user_id={uid}")
            imported += 1

    print(f"done: imported={imported} skipped={skipped}")


if __name__ == "__main__":
    main()

