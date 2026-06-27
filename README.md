# NEXUS — Multi-Platform Game Launcher

Connect your **Steam, Epic Games, GOG, or Xbox** account and see your entire game library in one place.

> **Privacy:** Your OAuth tokens are stored only in your own browser (localStorage). The server holds an encrypted session token (8 hours) to proxy API calls — no credentials or personal data are ever written to disk or a database.

---

## Deploy Options

### Option A — Vercel (Recommended — frontend + backend together, free)

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/Arnav1771/multi-platform-game-launcher)

Vercel deploys frontend (`docs/`) and backend (`api/index.py`) **on the same domain** — no CORS, no backend URL to configure. After deploy:

1. In Vercel dashboard → **Settings → Environment Variables**, add:
   - `SECRET_KEY` → any random string (e.g. output of `openssl rand -hex 32`)
   - `STEAM_API_KEY` → your free key from [steamcommunity.com/dev/apikey](https://steamcommunity.com/dev/apikey)
   - Platform credentials for Epic/GOG/Xbox (see below — optional)
2. Open your Vercel URL → click **Sign In with Steam** → your real library loads instantly

### Option B — Render (backend) + GitHub Pages (frontend, free)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/Arnav1771/multi-platform-game-launcher)

1. Click the button above
2. Log in to Render (free account)
3. Render reads `render.yaml` and creates the service automatically
4. After deploy, copy the service URL (e.g. `https://nexus-game-launcher.onrender.com`)
5. Go to your Render dashboard → **Environment** tab and set:
   - `BACKEND_URL` → your Render service URL
   - `STEAM_API_KEY` → your free key from [steamcommunity.com/dev/apikey](https://steamcommunity.com/dev/apikey)
6. Open the GitHub Pages UI → click **⚙ Settings** → paste your Render URL
7. Click **Sign In with Steam** — your real game library loads!

---

## Platform Setup

### Steam ✅ (easiest — works without API key for public profiles)
- Login: Free, no registration needed (Steam OpenID)
- API key: Optional. Get one free at [steamcommunity.com/dev/apikey](https://steamcommunity.com/dev/apikey)
- Without API key: works if your Steam game list is set to **Public** in privacy settings
- Set `STEAM_API_KEY` in Render env vars for reliable access

### Epic Games
1. Register at [dev.epicgames.com/portal](https://dev.epicgames.com/portal)
2. Create an Application
3. Add redirect URI: `https://nexus-game-launcher.onrender.com/auth/epic/callback`
4. Copy Client ID & Secret → set as `EPIC_CLIENT_ID` and `EPIC_CLIENT_SECRET` in Render

### GOG
1. Apply at [gog.com/developer](https://www.gog.com/developer)
2. Set redirect URI: `https://nexus-game-launcher.onrender.com/auth/gog/callback`
3. Set `GOG_CLIENT_ID` and `GOG_CLIENT_SECRET` in Render

### Xbox
1. Register at [portal.azure.com](https://portal.azure.com) → App registrations → New registration
2. Set redirect URI: `https://nexus-game-launcher.onrender.com/auth/xbox/callback`
3. Add permission: **XboxLive.signin** (under Microsoft Graph → Delegated)
4. Set `MICROSOFT_CLIENT_ID` and `MICROSOFT_CLIENT_SECRET` in Render

### EA / Origin
EA does not provide a public API for third-party game library access. Not supported.

---

## Local Development

```bash
# Backend
cp .env.example .env
# Edit .env — set BACKEND_URL=http://localhost:8000 and add your API keys

cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# API docs: http://localhost:8000/docs
```

Open `docs/index.html` in a browser → click **⚙ Settings** → set Backend URL to `http://localhost:8000`.

---

## Architecture

```
Browser (GitHub Pages)          Render (FastAPI)
       │                               │
       │  click "Sign in with Steam"   │
       │──────── redirect ────────────►│ /auth/steam/login
       │                               │──► Steam OpenID
       │◄── redirect with token ───────│ /auth/steam/callback (verifies)
       │                               │
       │  GET /api/games/steam?token=X │
       │──────────────────────────────►│
       │                               │──► Steam Web API (your games)
       │◄── your real game library ────│
       │                               │
```

Sessions expire after 8 hours. No account data is ever written to disk — only a temporary session ID.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Vanilla HTML/CSS/JS, deployed on GitHub Pages |
| Backend | Python 3.11, FastAPI, httpx |
| Hosting | Render (free tier) |
| Auth | Steam OpenID 2.0, OAuth 2.0 (Epic, GOG, Xbox) |
| Storage | None (sessions in `/tmp`, cleared on restart) |
