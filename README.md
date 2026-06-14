# Fat Loss Tracker Web App

A private web app for tracking weight, calories, protein, steps, cardio, measurements, and workouts.

## What it saves

- Daily weight
- Calories
- Protein
- Steps
- Cardio minutes
- Workout exercises
- Measurements
- Fat loss targets

## Run on your PC

1. Install Python 3.11 or newer.
2. Open Terminal or PowerShell in this folder.
3. Run:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

4. Open this on your PC:

```text
http://127.0.0.1:5000
```

## Access from your phone on home WiFi

1. Find your PC local IP address.

On Windows PowerShell:

```bash
ipconfig
```

Look for IPv4 Address, example `192.168.1.25`.

2. On your phone browser, open:

```text
http://192.168.1.25:5000
```

Your PC and phone need to be on the same WiFi.

## Access from anywhere

Best simple option: deploy it to Render, Railway, Fly.io, or a small VPS.

For Render:

1. Upload this folder to a GitHub repo.
2. Create a new Render Web Service.
3. Use this start command:

```bash
gunicorn app:app
```

4. Add this environment variable:

```text
SECRET_KEY=make-a-long-random-password-here
```

5. Use a persistent disk or external database so your SQLite file does not reset.
6. Open the public Render URL on your phone.
7. Create your first login.

## Better production setup

For long term use, switch SQLite to Postgres on Render, Railway, Supabase, or Neon.
SQLite is fine locally. Cloud hosting works better with Postgres.
