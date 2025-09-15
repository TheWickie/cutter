## Unreleased
- Restore `/session` endpoint providing OpenAI realtime client tokens for the web frontend.

## 2.0.0 — Redis Memory + v2 API
- Added Redis-backed user and session storage.
- New FastAPI app with routes under `/v2/*` for auth, chat, voice and memory.
- Guardrails loaded from `guardrails/na_uk_policy.md` and exposed via endpoint.
- Web frontend helper `web/js/cutter-client.js` for WordPress integration.
- Legacy `/session` route deprecated.
