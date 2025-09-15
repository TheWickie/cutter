# User Notes

## Making Redis Work

Use the import tool to preload users with alphanumeric ID codes so the backend can recognize callers and attach memory to them.

### Quick Start
- Set `REDIS_URL`: point to your Redis (use `rediss://` for TLS).
  - Example: `REDIS_URL=rediss://:password@host:6379/0`
- Import CSV:
  - `REDIS_URL=... python scripts/redis_import.py --csv docs/seed.sample.csv`
- Import JSONL:
  - `REDIS_URL=... python scripts/redis_import.py --jsonl docs/seed.sample.jsonl`
- Overwrite duplicates:
  - Add `--overwrite` to replace existing `id_code` entries.

### Input Formats
- CSV header: `id_code,name,number`
  - Example row: `ALPHA1234,Alice A,+15551230001`
- JSONL: one JSON object per line
  - Example: `{"id_code":"ALPHA1234","name":"Alice A","number":"+15551230001"}`

Sample files are included:
- `docs/seed.sample.csv`
- `docs/seed.sample.jsonl`

### What The Import Does
- Creates or updates Redis records:
  - `idcode_to_user:{IDCODE} -> user_id`
  - `user:{user_id}` with `name`, `id_code`, optional `number`, timestamps
  - `number_to_user:{number} -> user_id` if `number` provided
- Skips an existing `id_code` unless `--overwrite` is used.
- Does not create chat sessions; it only seeds identity data.

### Validation Rules
- `id_code`: letters/digits/hyphen, 4–32 chars (normalized to uppercase).
- `name`: non-empty (1–80 chars typical).
- `number` (optional): digits/`+`, 6–20 chars.

Tip: If you don’t set `REDIS_URL`, the tool uses an in-memory store and your import will not persist.

### Paths and Script
- Script: `scripts/redis_import.py`
- Run from repo root so relative paths resolve.

