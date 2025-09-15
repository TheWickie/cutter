# Example Makefile targets for Redis import (copy to project root if desired)

REDIS_URL ?=

.PHONY: import-csv import-jsonl import-overwrite

import-csv:
	@if [ -z "$(REDIS_URL)" ]; then echo "REDIS_URL is required"; exit 1; fi
	REDIS_URL=$(REDIS_URL) python scripts/redis_import.py --csv docs/seed.sample.csv

import-jsonl:
	@if [ -z "$(REDIS_URL)" ]; then echo "REDIS_URL is required"; exit 1; fi
	REDIS_URL=$(REDIS_URL) python scripts/redis_import.py --jsonl docs/seed.sample.jsonl

import-overwrite:
	@if [ -z "$(REDIS_URL)" ]; then echo "REDIS_URL is required"; exit 1; fi
	REDIS_URL=$(REDIS_URL) python scripts/redis_import.py --csv docs/seed.sample.csv --overwrite

# Usage:
#   make import-csv REDIS_URL=rediss://:password@host:6379/0
#   make import-jsonl REDIS_URL=redis://localhost:6379/0
#   make import-overwrite REDIS_URL=...

