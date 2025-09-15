# Redis Import – PowerShell Examples

Run these from the repo root. Ensure Python is installed and your Redis URL is correct.

## Set the Redis URL

```powershell
$env:REDIS_URL = "rediss://:password@host:6379/0"
```

For non‑TLS Redis:

```powershell
$env:REDIS_URL = "redis://localhost:6379/0"
```

## Import from CSV

```powershell
python scripts/redis_import.py --csv docs/seed.sample.csv
```

## Import from JSONL

```powershell
python scripts/redis_import.py --jsonl docs/seed.sample.jsonl
```

## Overwrite existing id_code entries

```powershell
python scripts/redis_import.py --csv docs/seed.sample.csv --overwrite
```

## Common tips
- Run `python --version` to confirm Python is on PATH.
- If you’re using a virtual environment, activate it first.
- Unset the variable for the current session with: `$env:REDIS_URL = $null`.

