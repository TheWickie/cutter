# Cutter v2 Backend

Redis-backed FastAPI service providing text and optional voice chat for the Cutter project.

## Setup

1. Create and activate a virtual environment
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
2. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```
3. Configure environment
   ```bash
   cp .env.example .env
   ```
   Fill in the values (OpenAI key, Redis URL, helplines, etc.).
4. Run the server
   ```bash
   uvicorn main:app --reload
   ```

## Environment Variables
- `OPENAI_API_KEY`
- `OPENAI_CHAT_MODEL`
- `REDIS_URL` (use rediss:// for TLS)
- `ALLOWED_ORIGINS`
- `VOICE_ALLOWED`
- `NA_HELPLINE_UK`
- `EMERGENCY_UK`
- `SESSION_TTL_SECONDS`
- `RATE_LIMIT_PER_MINUTE`
- `LOG_LEVEL`

## Redis
The service stores sessions and user memory in Redis. Use Redis Cloud or another managed instance. For local development the tests use `fakeredis`.

## Tests
Run the test suite with:
```bash
pytest
```

## Deployment
On Render, set `main:app` as the entry point and configure environment variables in the dashboard. Provide a TLS Redis URL and OpenAI key.

## Frontend
`web/js/cutter-client.js` offers minimal helpers for the WordPress frontend to call the API.
