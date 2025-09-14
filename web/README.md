# Cutter Voice Pilot – Web Frontend

This directory contains the client‑side portion of the Cutter Voice Pilot.  It
provides a simple interface for initiating a voice call with the NA Interim
Sponsor assistant via OpenAI’s realtime API.

## Running the frontend

To view the frontend during development, you can serve the files in this
directory with any static file server.  For example, using Python 3:

```bash
cd web
python -m http.server 5500
```

Then open your browser at [`http://localhost:5500`](http://localhost:5500) to
see the page.  If your backend is running on `localhost:8080` as per the
default settings, the page will be able to fetch session tokens.

> **Note:** Many browsers require HTTPS to access audio devices.  For local
> development on `localhost`, HTTP is permitted.  For remote or production
> use, serve the site over HTTPS using a certificate.

## Files

- **index.html** – The main HTML document containing the markup and layout.
- **style.css** – Styles for the page, including the call button, status
  indicators, transcript card and crisis notes.
- **app.js** – JavaScript that manages the call lifecycle: obtaining a session
  token, negotiating WebRTC with OpenAI and updating the UI.

## Important considerations

- **No analytics or tracking.**  This frontend does not set cookies, use
  analytics scripts or track users.  It exists solely to facilitate
  communication with the assistant.
- **Privacy and safeguarding.**  The page displays crisis contact numbers and
  emphasises that the assistant does not replace human sponsors or
  emergency services.
- **Session tokens** are short‑lived.  A new session must be requested each
  time a call is initiated.

Please see the top‑level README.md for instructions on running both the
backend and frontend together and for further guidance on cost management and
deployment considerations.