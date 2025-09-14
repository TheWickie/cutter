# Cutter Voice Pilot – Backend

This directory contains the server‑side code for the Cutter Voice Pilot.  The
backend is responsible for issuing short‑lived tokens that allow the browser
to establish a WebRTC connection with OpenAI’s realtime API.  It also enforces
CORS policies and basic rate limiting.

## Quick start

Follow these steps to get a development version of the backend running:

1. **Create and activate a virtual environment**:

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows use: .\.venv\Scripts\activate
   ```

2. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure your environment**:

   Copy the provided `.env.example` to `.env` and fill in your own
   OpenAI API key and any other settings:

   ```bash
   cp .env.example .env
   ```

   Then edit `.env` and set `OPENAI_API_KEY` to your secret key.  Adjust
   `ALLOWED_ORIGINS` to include any development hosts that should be
   permitted to call the API.

4. **Run the server**:

   Start the FastAPI application with Uvicorn:

   ```bash
   uvicorn app:app --host "${APP_HOST}" --port "${APP_PORT}" --reload
   ```

   By default the service binds to `0.0.0.0:8080`.  The `--reload` flag
   automatically restarts the server when you modify Python files.

## CORS and origin allow list

The backend restricts which origins may request session tokens via the
`POST /session` endpoint.  Set `ALLOWED_ORIGINS` in `.env` to a comma‑separated
list of fully qualified URLs (for example: `https://localhost,https://127.0.0.1`).
Requests from any other origin will result in a **403** error.

## Rate limiting

To prevent abuse, the backend implements a simple per‑IP rate limiter.  Each
client IP may request up to 10 sessions per 60‑second window.  Excess requests
return a **429** error.  For more robust production deployments you should
consider a distributed rate‑limiting strategy.

## Troubleshooting

- **Mic permission errors**: The frontend cannot access the microphone unless
  the user grants permission.  Ensure your browser prompts for mic access and
  that permission is granted.
- **CORS errors**: If you see “Origin not allowed”, update `ALLOWED_ORIGINS`
  in your `.env` to include the page’s URL.
- **HTTPS**: Browsers often require HTTPS to access audio devices.  The
  development server uses HTTP, but localhost is typically exempt.  For a
  production deployment, run behind an HTTPS proxy such as Nginx or Caddy.

## ElevenLabs TTS (optional)

This backend currently relies solely on OpenAI’s realtime API for speech
synthesis and recognition.  If you wish to integrate another TTS provider
(for example, ElevenLabs) in the future, you can include your API key in the
.env file under `ELEVENLABS_API_KEY` and modify `app.py` accordingly.  At
present, the backend does not use this key.