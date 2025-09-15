## Unreleased
- Restore `/session` endpoint providing OpenAI realtime client tokens for the web frontend.
- Fixed backend returning object for `client_secret`; now extracts token value so frontend sends valid Authorization header.

## 2025-09-15 — Voice handshake fix + health check
- Fixed Realtime session creation: added required `OpenAI-Beta: realtime=v1` header.
- Implemented `/v2/health` (Redis + Realtime readiness).
- Tightened CORS via `ALLOWED_ORIGINS`.
- Frontend SDP POST now includes Realtime beta header and better error display.
- Added header badge for voice readiness.
- Removed stub `...` placeholders across FE/BE.

## 2.0.0 — Redis Memory + v2 API
- Added Redis-backed user and session storage.
- New FastAPI app with routes under `/v2/*` for auth, chat, voice and memory.
- Guardrails loaded from `guardrails/na_uk_policy.md` and exposed via endpoint.
- Web frontend helper `web/js/cutter-client.js` for WordPress integration.
- Legacy `/session` route deprecated.
