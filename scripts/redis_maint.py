#!/usr/bin/env python3
"""
Redis maintenance utilities: audit and targeted purge.

Usage examples:
  # Audit key counts and biggest keys
  REDIS_URL=rediss://:password@host:port/0 \
    python scripts/redis_maint.py audit --top 20

  # Purge all NA literature index keys (lit:*)
  REDIS_URL=... python scripts/redis_maint.py purge-lit --yes

  # Purge orphan users (no reverse mappings) older than 30 days
  REDIS_URL=... python scripts/redis_maint.py purge-orphan-users --days 30 --yes

  # Purge memory:* entries whose users don't exist or last_contact older than 60 days
  REDIS_URL=... python scripts/redis_maint.py purge-memory --days 60 --yes
"""

import argparse
import datetime as dt
import json
import os
import sys
from typing import Dict, Iterable, List, Optional, Set, Tuple

# Ensure local imports work when running from repo root
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from core.redis_store import get_client  # type: ignore


PREFIXES = [
    "session:",
    "memory:",
    "user:",
    "idcode_to_user:",
    "number_to_user:",
    "name_to_user:",
    "lit:",
    "rate:",
]


def _scan_keys(pattern: str) -> Iterable[str]:
    r = get_client()
    if hasattr(r, "scan_iter"):
        yield from r.scan_iter(pattern)
        return
    # MemoryStore fallback (dev/testing)
    try:
        store = getattr(r, "store", None)
        if isinstance(store, dict):
            for k in list(store.keys()):
                if _match_pattern(k, pattern):
                    yield k
    except Exception:
        return


def _match_pattern(key: str, pattern: str) -> bool:
    # very small glob support: only prefix*suffix
    if pattern.endswith("*"):
        return key.startswith(pattern[:-1])
    return key == pattern


def _memory_usage(r, key: str) -> Optional[int]:
    # Requires Redis server supporting MEMORY USAGE
    try:
        if hasattr(r, "memory_usage"):
            return int(r.memory_usage(key))  # type: ignore
        # Fallback to command execution
        return int(r.execute_command("MEMORY USAGE", key))
    except Exception:
        return None


def audit(top_n: int = 20) -> None:
    r = get_client()
    # Count by known prefixes
    counts: Dict[str, int] = {p: 0 for p in PREFIXES}
    other = 0
    biggest: List[Tuple[int, str]] = []
    for key in _scan_keys("*"):
        matched = False
        for p in PREFIXES:
            if key.startswith(p):
                counts[p] += 1
                matched = True
                break
        if not matched:
            other += 1
        # sample memory usage for top list
        mu = _memory_usage(r, key)
        if mu is not None:
            biggest.append((mu, key))
    biggest.sort(reverse=True)

    # Output
    print("Redis audit summary:\n")
    try:
        info = r.info() if hasattr(r, "info") else {}
    except Exception:
        info = {}
    if info:
        used = info.get("used_memory_human") or info.get("used_memory")
        peak = info.get("used_memory_peak_human") or info.get("used_memory_peak")
        keys = info.get("db0", {}).get("keys") if isinstance(info.get("db0"), dict) else None
        print(f"- Used memory: {used} (peak {peak})")
        if keys is not None:
            print(f"- Total keys: {keys}")
    print("- Counts by prefix:")
    for p in PREFIXES:
        print(f"  {p:<18} {counts[p]}")
    print(f"  {'other:':<18} {other}")

    if biggest:
        print(f"\nTop {min(top_n, len(biggest))} largest keys (bytes):")
        for mu, key in biggest[:top_n]:
            print(f"  {mu:>10}  {key}")
    else:
        print("\n(MEMORY USAGE not supported on this Redis server; skipping biggest keys.)")


def purge_lit(confirm: bool) -> None:
    if not confirm:
        print("Refusing to purge without --yes confirmation.")
        return
    r = get_client()
    count = 0
    for key in _scan_keys("lit:*"):
        try:
            r.unlink(key) if hasattr(r, "unlink") else r.delete(key)
            count += 1
        except Exception:
            pass
    print(f"Deleted {count} 'lit:*' keys.")


def _collect_mapped_user_ids() -> Set[str]:
    r = get_client()
    uids: Set[str] = set()
    for prefix in ("idcode_to_user:", "number_to_user:", "name_to_user:"):
        for key in _scan_keys(prefix + "*"):
            try:
                uid = r.get(key)
                if uid:
                    uids.add(str(uid))
            except Exception:
                continue
    return uids


def purge_orphan_users(days: int, confirm: bool) -> None:
    if not confirm:
        print("Refusing to purge without --yes confirmation.")
        return
    r = get_client()
    cutoff = dt.datetime.utcnow() - dt.timedelta(days=days)
    mapped = _collect_mapped_user_ids()
    deleted = 0
    scanned = 0
    for key in _scan_keys("user:*"):
        scanned += 1
        uid = key.split(":", 1)[1]
        if uid in mapped:
            continue
        try:
            data = r.hgetall(key)
            created = data.get("created_at") or data.get("last_seen")
            old_enough = True
            if created:
                try:
                    ts = dt.datetime.fromisoformat(created)
                    old_enough = ts < cutoff
                except Exception:
                    old_enough = True
            if old_enough:
                # also remove memory if present
                r.unlink(f"memory:{uid}") if hasattr(r, "unlink") else r.delete(f"memory:{uid}")
                r.unlink(key) if hasattr(r, "unlink") else r.delete(key)
                deleted += 1
        except Exception:
            continue
    print(f"Scanned {scanned} users; deleted {deleted} orphan users older than {days} days.")


def purge_memory(days: int, confirm: bool) -> None:
    if not confirm:
        print("Refusing to purge without --yes confirmation.")
        return
    r = get_client()
    cutoff = dt.datetime.utcnow() - dt.timedelta(days=days)
    deleted = 0
    scanned = 0
    for key in _scan_keys("memory:*"):
        scanned += 1
        uid = key.split(":", 1)[1]
        # skip if user exists and is recent
        user_exists = bool(r.hgetall(f"user:{uid}"))
        if not user_exists:
            r.unlink(key) if hasattr(r, "unlink") else r.delete(key)
            deleted += 1
            continue
        try:
            payload = r.get(key)
            if not payload:
                continue
            data = json.loads(payload)
            last = data.get("last_contact")
            if last:
                try:
                    ts = dt.datetime.fromisoformat(last)
                    if ts < cutoff:
                        r.unlink(key) if hasattr(r, "unlink") else r.delete(key)
                        deleted += 1
                except Exception:
                    pass
        except Exception:
            continue
    print(f"Scanned {scanned} memory entries; deleted {deleted} older than {days} days or without users.")


def main() -> None:
    p = argparse.ArgumentParser(description="Redis audit and purge tools")
    sub = p.add_subparsers(dest="cmd", required=True)

    pa = sub.add_parser("audit", help="Summarize key counts and biggest keys")
    pa.add_argument("--top", type=int, default=20, help="Show top-N biggest keys by memory usage")

    pl = sub.add_parser("purge-lit", help="Delete all 'lit:*' keys (literature index)")
    pl.add_argument("--yes", action="store_true", help="Confirm deletion")

    pou = sub.add_parser("purge-orphan-users", help="Delete user:* with no reverse mapping, older than N days")
    pou.add_argument("--days", type=int, default=30)
    pou.add_argument("--yes", action="store_true", help="Confirm deletion")

    pm = sub.add_parser("purge-memory", help="Delete memory:* older than N days or without users")
    pm.add_argument("--days", type=int, default=60)
    pm.add_argument("--yes", action="store_true", help="Confirm deletion")

    args = p.parse_args()
    if args.cmd == "audit":
        audit(top_n=args.top)
    elif args.cmd == "purge-lit":
        purge_lit(confirm=args.yes)
    elif args.cmd == "purge-orphan-users":
        purge_orphan_users(days=args.days, confirm=args.yes)
    elif args.cmd == "purge-memory":
        purge_memory(days=args.days, confirm=args.yes)


if __name__ == "__main__":
    main()

