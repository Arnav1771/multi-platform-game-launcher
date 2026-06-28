# NEXUS — Deployment Reference

Every hosting provider that works, partially works, or doesn't work — with exact steps for each.

---

## Quick Comparison

| Provider | Frontend | Backend | Free Tier | One-Click | Best For |
|----------|----------|---------|-----------|-----------|----------|
| **Vercel** | ✅ | ✅ | ✅ | ✅ | Full-stack, easiest |
| **Netlify** | ✅ | ✅ | ✅ | ✅ | Full-stack alternative |
| **Railway** | ✅ | ✅ | ✅ ($5 credit) | ✅ | Full control |
| **Render** | ✅ (via GitHub Pages) | ✅ | ✅ (spins down) | ✅ | Backend only |
| **Fly.io** | ❌ | ✅ | ✅ (3 VMs) | ❌ | Always-on backend |
| **Heroku** | ❌ | ✅ | ❌ (paid only) | ❌ | Legacy projects |
| **DigitalOcean** | ❌ | ✅ | ❌ ($5/mo) | ✅ | Production |
| **Koyeb** | ❌ | ✅ | ✅ | ✅ | Free backend alt. |
| **Google Cloud Run** | ❌ | ✅ | ✅ (1M req/mo) | ❌ | Scalable backend |
| **AWS Lambda** | ❌ | ✅ | ✅ (1M req/mo) | ❌ | AWS ecosystem |
| **Azure Container** | ❌ | ✅ | ✅ (limited) | ❌ | Azure ecosystem |
| **GitHub Pages** | ✅ | ❌ | ✅ | ✅ | Frontend only |
| **Cloudflare Pages** | ✅ | ❌ | ✅ | ✅ | Frontend only |
| **Firebase Hosting** | ✅ | ❌* | ✅ | ❌ | Frontend only |
| **Cloudflare Workers** | ❌ | ❌ | — | — | No Python runtime |
| **Netlify Edge** | ❌ | ❌ | — | — | Deno only |

> **Session note:** Providers marked full-stack use **Fernet-encrypted stateless sessions** (`api/index.py`).
> Backend-only providers use **file-backed sessions** (`backend/main.py`) stored in `/tmp`.

---

## ✅ VERCEL — Recommended (Full-Stack)

**Free tier:** Yes — 100GB bandwidth, 100 serverless function executions/day  
**Session type:** Fernet encrypted (stateless — `api/index.py`)  
**Config file:** `vercel.json` ✅ already in repo  
**Same domain:** Yes — frontend and backend share `*.vercel.app`

### Deploy

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/Arnav1771/multi-platform-game-launcher)

Or from CLI:
```bash
npm i -g vercel
vercel --prod
```

### Environment Variables (Vercel Dashboard → Settings → Environment Variables)

| Variable | Value | Required |
|----------|-------|----------|
| `SECRET_KEY` | `openssl rand -hex 32` | **Yes** |
| `STEAM_API_KEY` | From [steamcommunity.com/dev/apikey](https://steamcommunity.com/dev/apikey) | Recommended |
| `EPIC_CLIENT_ID` | From [dev.epicgames.com/portal](https://dev.epicgames.com/portal) | Epic only |
| `EPIC_CLIENT_SECRET` | — | Epic only |
| `GOG_CLIENT_ID` | From [gog.com/developer](https://www.gog.com/developer) | GOG only |
| `GOG_CLIENT_SECRET` | — | GOG only |
| `MICROSOFT_CLIENT_ID` | From [portal.azure.com](https://portal.azure.com) | Xbox only |
| `MICROSOFT_CLIENT_SECRET` | — | Xbox only |

> `BACKEND_URL` and `FRONTEND_URL` are **auto-detected** from `VERCEL_URL` — do not set them manually.

### OAuth Redirect URIs (add to each platform's developer portal)
```
https://YOUR-PROJECT.vercel.app/auth/steam/callback
https://YOUR-PROJECT.vercel.app/auth/epic/callback
https://YOUR-PROJECT.vercel.app/auth/gog/callback
https://YOUR-PROJECT.vercel.app/auth/xbox/callback
```

### How it works
Vercel reads `vercel.json` and:
- Serves `docs/index.html` for all non-API paths (frontend)
- Routes `/api/*`, `/auth/*`, `/health` to `api/index.py` (Python 3.12 serverless)
- Frontend uses same-origin relative URLs — no CORS config needed

### Limitations
- Serverless functions time out at 60s (free plan)
- No persistent disk — sessions are encrypted in the token itself (already handled)
- 100 function executions/day on Hobby plan (upgrade to Pro for more)

---

## ✅ NETLIFY — Full-Stack Alternative

**Free tier:** Yes — 100GB bandwidth, 125k function executions/month  
**Session type:** Fernet encrypted (stateless)  
**Config file:** Needs `netlify.toml` (create it, see below)  
**Same domain:** Yes — frontend and functions on `*.netlify.app`

### Create `netlify.toml`
```toml
[build]
  publish = "docs"
  command = "echo 'No build step'"

[functions]
  directory = "netlify/functions"
  node_bundler = "esbuild"

[[redirects]]
  from = "/health"
  to = "/.netlify/functions/api"
  status = 200

[[redirects]]
  from = "/auth/*"
  to = "/.netlify/functions/api"
  status = 200

[[redirects]]
  from = "/api/*"
  to = "/.netlify/functions/api"
  status = 200

[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200
```

### Create `netlify/functions/api.py`
```python
# Netlify Python functions use the same pattern as Vercel
# Copy api/index.py → netlify/functions/api.py
# Netlify uses the same ASGI interface
```
Netlify supports Python functions via the `python3.12` runtime.
Copy `api/index.py` to `netlify/functions/api.py` — no other changes needed.

### Deploy
```bash
npm i -g netlify-cli
netlify deploy --prod
```

Or connect your GitHub repo at [app.netlify.com](https://app.netlify.com).

### Environment Variables
Same as Vercel. Set in **Site Settings → Environment Variables**.

### OAuth Redirect URIs
```
https://YOUR-SITE.netlify.app/auth/steam/callback
https://YOUR-SITE.netlify.app/auth/epic/callback
https://YOUR-SITE.netlify.app/auth/gog/callback
https://YOUR-SITE.netlify.app/auth/xbox/callback
```

---

## ✅ RAILWAY — Full-Stack or Backend Only

**Free tier:** $5 credit/month (enough for light use)  
**Session type:** File-backed (`backend/main.py`) — Railway has a persistent filesystem  
**Config file:** Auto-detected from repo structure  
**Same domain:** No — frontend and backend get separate URLs (use GitHub Pages for frontend)

### Deploy Backend

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template?template=https://github.com/Arnav1771/multi-platform-game-launcher)

Or from CLI:
```bash
npm i -g @railway/cli
railway login
railway init
railway up
```

### Service Configuration (Railway Dashboard)
- **Root Directory:** `backend`
- **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Build Command:** `pip install -r requirements.txt`

### Environment Variables
```
BACKEND_URL=https://YOUR-APP.up.railway.app
FRONTEND_URL=https://Arnav1771.github.io/multi-platform-game-launcher
SECRET_KEY=<random 32 char hex>
STEAM_API_KEY=<your key>
# + Epic/GOG/Microsoft keys as needed
```

### OAuth Redirect URIs
```
https://YOUR-APP.up.railway.app/auth/steam/callback
https://YOUR-APP.up.railway.app/auth/epic/callback
```

### Frontend
Deploy to GitHub Pages from the `docs/` folder. Set Backend URL in ⚙ Settings.

---

## ✅ RENDER — Backend Only

**Free tier:** Yes — spins down after 15 minutes of inactivity (first request ~30s cold start)  
**Session type:** File-backed (`backend/main.py`) — writes to `/tmp/nexus_sessions.json`  
**Config file:** `render.yaml` ✅ already in repo  
**Same domain:** No — use GitHub Pages for frontend

### Deploy

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/Arnav1771/multi-platform-game-launcher)

### After Deploy
1. Copy your service URL: `https://nexus-game-launcher.onrender.com`
2. In Render dashboard → **Environment** tab, set `BACKEND_URL` to your service URL
3. Open the GitHub Pages UI → ⚙ Settings → set Backend URL to your Render URL
4. Sign in to a platform — your real library loads

### Environment Variables
Defined in `render.yaml` (edit the file or set in dashboard):
```
BACKEND_URL=https://nexus-game-launcher.onrender.com
FRONTEND_URL=https://Arnav1771.github.io/multi-platform-game-launcher
SECRET_KEY=<auto-generated by render.yaml>
STEAM_API_KEY=<your key>
```

### Cold Start Warning
Free Render services sleep after 15 min of inactivity. The first request after sleeping takes ~30 seconds. Upgrade to Render Starter ($7/mo) to prevent this.

---

## ✅ FLY.IO — Always-On Backend

**Free tier:** 3 shared-CPU VMs, 256MB RAM — always running (no cold starts)  
**Session type:** File-backed (`backend/main.py`)  
**Config file:** Needs `fly.toml` (create it, see below)

### Create `fly.toml`
```toml
app = "nexus-game-launcher"
primary_region = "iad"

[build]
  dockerfile = "Dockerfile"

[env]
  PORT = "8080"

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = false
  auto_start_machines = true
  min_machines_running = 1

[[vm]]
  memory = "256mb"
  cpu_kind = "shared"
  cpus = 1
```

### Create `Dockerfile` (at repo root)
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### Deploy
```bash
# Install flyctl: https://fly.io/docs/hands-on/install-flyctl/
fly auth login
fly launch --name nexus-game-launcher --no-deploy
fly secrets set SECRET_KEY=$(openssl rand -hex 32)
fly secrets set STEAM_API_KEY=your_key_here
fly secrets set BACKEND_URL=https://nexus-game-launcher.fly.dev
fly secrets set FRONTEND_URL=https://Arnav1771.github.io/multi-platform-game-launcher
fly deploy
```

### OAuth Redirect URIs
```
https://nexus-game-launcher.fly.dev/auth/steam/callback
```

---

## ✅ KOYEB — Free Backend Alternative

**Free tier:** 1 Nano service (512MB RAM, 0.1 CPU) — always running  
**Session type:** File-backed  
**Config file:** Auto-detects Python from `backend/requirements.txt`

### Deploy
1. Go to [app.koyeb.com](https://app.koyeb.com) → Create Service → GitHub
2. Select this repo
3. Set **Root directory:** `backend`
4. Set **Run command:** `uvicorn main:app --host 0.0.0.0 --port 8000`
5. Add environment variables in Koyeb dashboard

---

## ✅ HEROKU — Backend (Paid, No Free Tier)

**Free tier:** ❌ Removed in 2022. Cheapest plan is $5/month (Eco Dyno)  
**Session type:** File-backed  
**Config file:** Needs `Procfile`

### Create `Procfile`
```
web: cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT
```

### Create `runtime.txt`
```
python-3.12.0
```

### Deploy
```bash
heroku login
heroku create nexus-game-launcher
heroku config:set SECRET_KEY=$(openssl rand -hex 32)
heroku config:set STEAM_API_KEY=your_key
heroku config:set BACKEND_URL=https://nexus-game-launcher.herokuapp.com
heroku config:set FRONTEND_URL=https://Arnav1771.github.io/multi-platform-game-launcher
git push heroku main
```

---

## ✅ DIGITALOCEAN APP PLATFORM

**Free tier:** ❌ Static sites free, but backend (App) starts at $5/month  
**Session type:** File-backed  
**Config file:** Auto-detects Python

### Deploy via DigitalOcean App Platform
1. [cloud.digitalocean.com/apps](https://cloud.digitalocean.com/apps) → Create App → GitHub
2. Select repo, set source directory to `backend/`
3. Set **Run command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Add environment variables

---

## ✅ GOOGLE CLOUD RUN — Scalable Backend

**Free tier:** 2 million requests/month, 360k CPU-seconds/month  
**Session type:** File-backed (ephemeral, but fine for quick OAuth flows)  
**Config file:** Needs `Dockerfile`

### Deploy
```bash
# Requires Google Cloud SDK: https://cloud.google.com/sdk
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Build and push container
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/nexus-launcher ./

# Deploy to Cloud Run
gcloud run deploy nexus-launcher \
  --image gcr.io/YOUR_PROJECT_ID/nexus-launcher \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "SECRET_KEY=xxx,STEAM_API_KEY=xxx,BACKEND_URL=https://nexus-launcher-xxx-uc.a.run.app"
```

> Uses the `Dockerfile` created for the Fly.io section above.

---

## ✅ AWS LAMBDA + API GATEWAY

**Free tier:** 1 million requests/month forever  
**Session type:** Fernet encrypted (Lambda is stateless like Vercel)  
**Config file:** Needs `serverless.yml` or SAM template  

### Using AWS SAM (Serverless Application Model)
```bash
pip install aws-sam-cli
```

Create `template.yaml`:
```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Resources:
  NexusApi:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: api/
      Handler: index.handler
      Runtime: python3.12
      Timeout: 30
      Events:
        Api:
          Type: HttpApi
          Properties:
            Path: /{proxy+}
            Method: ANY
      Environment:
        Variables:
          SECRET_KEY: !Ref SecretKey
          STEAM_API_KEY: !Ref SteamApiKey
```

```bash
sam build
sam deploy --guided
```

### Mangum adapter needed
```bash
pip install mangum
```

Add to `api/index.py`:
```python
from mangum import Mangum
handler = Mangum(app)  # AWS Lambda handler
```

---

## ✅ AZURE CONTAINER APPS

**Free tier:** 180k vCPU-seconds/month, 360k GiB-seconds/month  
**Session type:** File-backed  
**Config file:** Needs `Dockerfile`

### Deploy
```bash
# Install Azure CLI: https://docs.microsoft.com/cli/azure/install-azure-cli
az login
az group create --name nexus-rg --location eastus
az acr create --name nexusregistry --resource-group nexus-rg --sku Basic
az acr build --registry nexusregistry --image nexus-launcher .
az containerapp create \
  --name nexus-launcher \
  --resource-group nexus-rg \
  --image nexusregistry.azurecr.io/nexus-launcher \
  --ingress external --target-port 8080 \
  --env-vars SECRET_KEY=xxx STEAM_API_KEY=xxx
```

---

## ✅ GITHUB PAGES — Frontend Only

**Free tier:** Yes — unlimited for public repos  
**Backend:** ❌ No server-side code — use with any backend provider above  
**Config file:** Already configured — `docs/index.html` served from `/docs` folder

### Enable
1. Repo → **Settings** → **Pages**
2. Source: **Deploy from a branch**
3. Branch: `main` / Folder: `/docs`
4. Save → live at `https://Arnav1771.github.io/multi-platform-game-launcher`

### After enabling
Open the site → ⚙ Settings → set Backend URL to whichever backend provider you deployed.

---

## ✅ CLOUDFLARE PAGES — Frontend Only

**Free tier:** Yes — unlimited bandwidth, 500 builds/month  
**Backend:** ❌ Cloudflare Workers don't support Python  
**Config file:** Not needed

### Deploy
1. [dash.cloudflare.com/pages](https://dash.cloudflare.com/pages) → Create project → Connect GitHub
2. Select this repo
3. **Build settings:**
   - Build command: *(leave empty)*
   - Build output directory: `docs`
4. Deploy

### After enabling
Open the site → ⚙ Settings → set Backend URL to your chosen backend provider.

---

## ✅ FIREBASE HOSTING — Frontend Only

**Free tier:** Yes — 10GB storage, 360MB/day transfer  
**Backend:** ❌ (Firebase Cloud Functions are Node.js/Python but complex to set up)  
**Config file:** Needs `firebase.json`

### Deploy
```bash
npm i -g firebase-tools
firebase login
firebase init hosting
# Output directory: docs
# Configure as SPA: Yes
firebase deploy
```

---

## ❌ CLOUDFLARE WORKERS — Not Supported

**Reason:** Cloudflare Workers support only JavaScript, TypeScript, and WebAssembly. Python (FastAPI) does not run on Workers.

**Alternative:** Use Cloudflare Pages for the frontend + Vercel/Render/Railway for the backend.

---

## ❌ NETLIFY EDGE FUNCTIONS — Not Supported

**Reason:** Netlify Edge Functions run on Deno (JavaScript/TypeScript only). Python is not supported.

**Alternative:** Use regular Netlify Functions (serverless, not edge) — Python IS supported there. See the Netlify section above.

---

## ❌ VERCEL EDGE FUNCTIONS — Not Supported

**Reason:** Vercel Edge Functions are JavaScript/TypeScript/WebAssembly only. Python is not supported at the edge.

**Note:** Regular Vercel **Serverless Functions** DO support Python (`api/index.py`) — that's what this project uses. The limitation is only for Edge runtime.

---

## Environment Variables Reference

All providers need these. Generate `SECRET_KEY` with: `openssl rand -hex 32`

```bash
# Required on all deployments
SECRET_KEY=                  # Random 32+ char string — NEVER share this

# Strongly recommended
STEAM_API_KEY=               # Free — steamcommunity.com/dev/apikey

# Set by Vercel automatically — only set manually on other providers
BACKEND_URL=                 # Full URL of your backend (e.g. https://nexus.onrender.com)
FRONTEND_URL=                # Full URL of your frontend (e.g. GitHub Pages URL)

# Optional — only needed if you want Epic/GOG/Xbox login
EPIC_CLIENT_ID=              # dev.epicgames.com/portal
EPIC_CLIENT_SECRET=
GOG_CLIENT_ID=               # gog.com/developer
GOG_CLIENT_SECRET=
MICROSOFT_CLIENT_ID=         # portal.azure.com → App registrations
MICROSOFT_CLIENT_SECRET=
```

---

## OAuth Redirect URI Cheat Sheet

When registering your app on each platform's developer portal, use these callback URLs.
Replace `YOUR_BACKEND_URL` with your actual deployed backend URL.

```
Steam:   YOUR_BACKEND_URL/auth/steam/callback
Epic:    YOUR_BACKEND_URL/auth/epic/callback
GOG:     YOUR_BACKEND_URL/auth/gog/callback
Xbox:    YOUR_BACKEND_URL/auth/xbox/callback
```

On Vercel, `YOUR_BACKEND_URL` = your Vercel project URL (e.g. `https://nexus-game-launcher.vercel.app`).

---

## Choosing the Right Provider

```
Just want it working fast?
  └─ Vercel ✅ (vercel.json already configured, one-click)

Want it always on with no cold starts?
  └─ Fly.io ✅ (free 3 VMs, always running)

Want to keep everything on one platform you know?
  ├─ AWS ecosystem → Lambda + API Gateway
  ├─ Google ecosystem → Cloud Run
  └─ Azure ecosystem → Container Apps

Want free forever?
  └─ Vercel Hobby (generous free tier) or Google Cloud Run (1M req/mo)

Don't want to manage a server at all?
  └─ Vercel or Netlify (fully managed serverless)
```
