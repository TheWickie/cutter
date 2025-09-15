# Redis Setup – Simple Step‑by‑Step (for humans)

This guide helps you get Redis working for Cutter, add a user with a display name and a passphrase, and verify it via the web chat.

## 1) Create a Redis database
- Go to your Redis provider (Redis Cloud, Upstash, Render, etc.).
- Press “Create Database” (or similar).
- Choose free or small paid plan.
- Copy the connection URL. It looks like:
  - `rediss://:PASSWORD@HOST:PORT/0`

## 2) Put the URL into your environment
Pick how you run the backend.

- Render (or other hosting):
  - Open your service > Environment.
  - Add `REDIS_URL` with the value you copied.
  - Save and redeploy.

- Local (Windows PowerShell):
  - In your repo folder, run:
    - `$env:REDIS_URL = "rediss://:PASSWORD@HOST:PORT/0"`
    - Start the app (e.g., `uvicorn main:app --reload`).

## 3) Prepare a seed file with your user
You can use CSV or JSONL. CSV is simplest.

- Open `docs/seed.sample.csv` in a text editor and add a row with your info:
  - Columns (now supported): `name,id_code,number,display_name,passphrase`
  - Example:
    - `Cris R,ALPHA1234,,Cris R,My secret pass`

Notes:
- `id_code` and `number` can be empty for this feature.
- `display_name` is what you will say in chat (e.g., “Cris R”).
- `passphrase` is what you will type after the bot asks.

## 4) Import the user into Redis
- In the repo folder, run one of:
  - Windows PowerShell:
    - `$env:REDIS_URL = "rediss://:PASSWORD@HOST:PORT/0"`
    - `python scripts/redis_import.py --csv docs/seed.sample.csv --overwrite`
  - macOS/Linux:
    - `REDIS_URL=rediss://:PASSWORD@HOST:PORT/0 python scripts/redis_import.py --csv docs/seed.sample.csv --overwrite`

If it worked, you’ll see `imported user_id=...`.

## 5) Test in the web chat
- Open the Cutter web page.
- Type: `Hello, I'm Cris R` (use your display name).
- The assistant should ask: “What’s your passphrase please?”
- Enter your passphrase from the CSV.
- If it matches, you’ll see: “Thanks, Cris. I’ve opened your notes.”

## Troubleshooting
- “Doesn’t recognise name”: Check `display_name` spelling and that you re‑imported.
- “Passphrase didn’t match”: Re‑run the import with `--overwrite` and correct passphrase.
- “Still not working”: Ensure `REDIS_URL` is set in your hosting environment and the app was redeployed.

That’s it. If you want me to add more sample rows or a tiny screen‑share checklist, say so.

