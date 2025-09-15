# Cutter Memory & Identity Plan (Stage 1)

This document plans the addition of persistent identity via alphanumeric ID codes and durable conversation memory for callers. It outlines APIs, Redis data model, validation rules, security, and rollout/testing. Stage 1 covers planning and seeding only — no runtime changes yet.

## Goals
- Identify callers by a provided `id_code` (alphanumeric) and name.
- Persist per-user profile, notes, and conversation context across sessions.
- Keep current session flow intact; add ID-code based auth alongside phone-number flow.
- Use Redis for low-latency storage with simple, reliable keyspace design.

## Non-Goals (for now)
- No full-text search over conversations.
- No PII beyond `name`, optional `number`.
- No GDPR erase/export flows yet (documented as future work).

## Data Model (Redis)

Keys and types:
- `user:{user_id}` (hash):
  - Fields: `name`, `number?`, `id_code`, `authed` ("1"), `created_at`, `last_seen` (ISO8601), optional app-specific profile fields.
- `idcode_to_user:{IDCODE}` (string): `user_id` (IDCODE is normalized uppercase).
- `number_to_user:{E164}` (string): `user_id` (existing).
- `session:{session_id}` (string JSON): session object with TTL (existing).
- `memory:{user_id}` (string JSON): compact, structured memory (profile, notes, summary, last_topics, last_contact) (existing; extended).
- `conv:{user_id}` (list): append-only JSON lines `{ts, role, text}` capped to `CONV_MAX=500` entries.

Notes:
- We normalize `id_code` to uppercase to avoid case collisions.
- We cap conversation list to protect storage and privacy. Consider time-based retention later.

## Validation Rules
- `id_code`: regex `^[A-Za-z0-9-]{4,32}$`, normalize to uppercase.
- `name`: 1–80 chars; trim whitespace.
- `number`: optional; if present, E.164-like (basic `^[0-9+]{6,20}$`).

## API Endpoints

All endpoints live under existing prefixes and reuse rate limiting. New endpoints:

1) POST `/v2/auth/register-id`
- Body: `{ "name": string, "id_code": string, "number?": string }`
- Behavior: validate; ensure `id_code` unused; create `user:{user_id}`; set reverse mappings (`idcode_to_user:{id_code}`, optional `number_to_user:{number}`); create session; return `{ user_id, session_id, mode: "text" }`.
- Errors: `409` if `id_code` already taken; `400` if validation fails.

2) POST `/v2/auth/verify-id`
- Body: `{ "id_code": string, "name": string }`
- Behavior: lookup `idcode_to_user:{id_code}`; ensure `user:{id}.name` matches (or set if unset); create session; return `{ user_id, session_id, mode }`.
- Errors: `401` if unknown code or name mismatch; `400` if validation fails.

3) GET `/v2/memory/conversation`
- Query: `user_id` (and optional paging: `start`, `limit`)
- Returns: `{ records: Array<{ts, role, text}> }` (last N by default, e.g., 100).

4) Optional future endpoints
- DELETE `/v2/memory/conversation` (admin/user-driven purge)
- POST `/v2/memory/summarize` (update rolling summary in `memory:{user_id}`)

Existing endpoints remain unchanged and interoperable:
- `/v2/auth/call`, `/v2/auth/verify-name` continue to support phone+name flows.
- `/v2/chat/send` continues to use session history (ephemeral) and `memory:{user_id}`.

## Chat Hook Changes (planned)
- In `routes/chat.py:send`, after updating `history`, also append both the user message and assistant reply to `conv:{user_id}` via a helper with capping:
  - `append_conversation(user_id, role, text)`
  - Cap with `LTRIM` (Redis) to last `CONV_MAX` entries.
- Continue to update lightweight memory deltas: `memory.last_topics`, `memory.last_contact`.

## Redis Helpers (planned)
- Add to `core/redis_store.py`:
  - `append_conversation(user_id: str, role: str, text: str, max_items: int = 500) -> None`
  - `get_conversation(user_id: str, start: int = -100, end: int = -1) -> list`
  - Ensure `MemoryStore` supports analogous list ops for testing (e.g., `rpush`, `lrange`, `ltrim`).

## Error Model
- `400 BAD_REQUEST`: Validation failures.
- `401 UNAUTHORIZED`: Unknown or mismatched identity.
- `409 CONFLICT`: `id_code` already registered.
- Preserve existing `detail.error.code/message` pattern for consistency.

## Security & Privacy
- Rate limit all new endpoints (reuse `core.rate_limit.rate_limit`).
- Never echo full conversation text in logs; only counts/ids.
- Cap stored conversation length; avoid sensitive data in `notes`.
- Future: add purge/export endpoints and access control as needed.

## Config
- `REDIS_URL`: e.g., `rediss://:password@host:port/0` for hosted Redis.
- `CONV_MAX`: optional env to override default cap (e.g., `500`).
- Already present: `SESSION_TTL_SECONDS`, `RATE_LIMIT_PER_MINUTE`.

## Migration & Backfill
- Existing users (phone-number based) can optionally be assigned ID codes by an admin import.
- No schema migration required; keys are new or additive.

## Testing Plan
- Unit tests (pytest + fakeredis):
  - Register/verify by ID code (happy path, duplicates, mismatch).
  - Conversation append and fetch capping behavior.
  - Interop: chat works for sessions created via ID-code auth.

## Rollout Plan
1) Implement helpers and endpoints behind tests.
2) Seed initial users via the provided import script (see below).
3) Deploy; monitor Redis size and rates; adjust `CONV_MAX` as needed.

## Seeding & Tools

Use `scripts/redis_import.py` to import users from CSV or JSONL into Redis.

Example CSV (`docs/seed.sample.csv`):

```
id_code,name,number
ALPHA1234,Alice A,+15551230001
BETA-9999,Bob B,
```

Run:

```
REDIS_URL=rediss://:password@host:port/0 \
  python scripts/redis_import.py --csv docs/seed.sample.csv
```

JSONL alternative (`docs/seed.sample.jsonl`): one JSON object per line with `id_code`, `name`, optional `number`.

Script behavior:
- Validates and normalizes `id_code`.
- Skips duplicates by default; use `--overwrite` to update existing users with the same `id_code`.
- Sets `user:{user_id}` and reverse mappings. Does not create sessions.

