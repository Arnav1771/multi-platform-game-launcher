# TECHSPEC.md — NEXUS Multi-Platform Game Launcher

## Architecture Overview

The project follows a client-server architecture with three delivery targets:

```
┌─────────────────────────────────────────────────────────────┐
│  GitHub Pages (Static)     │  Desktop (Electron)             │
│  docs/index.html           │  frontend/ + electron/           │
│  Pure HTML/CSS/JS SPA      │  React + TypeScript              │
└────────────────────────────┴────────────────────────────────┘
                              │
                     HTTP REST API
                              │
              ┌───────────────▼────────────────┐
              │     FastAPI Backend (Python)    │
              │     backend/main.py             │
              │     Port 8000                   │
              └───────────────┬────────────────┘
                              │ SQLAlchemy ORM
              ┌───────────────▼────────────────┐
              │     PostgreSQL Database         │
              └────────────────────────────────┘
```

---

## Tech Stack

### Backend
| Component | Technology | Version |
|-----------|-----------|---------|
| Language | Python | 3.8+ |
| Web Framework | FastAPI | Latest |
| ORM | SQLAlchemy | Latest |
| Database | PostgreSQL | 14+ |
| ASGI Server | Uvicorn | Latest |
| Auth | OAuth 2.0 / JWT | — |
| Config | python-dotenv + pydantic-settings | — |

### Frontend (Planned React App)
| Component | Technology |
|-----------|-----------|
| Language | TypeScript |
| Framework | React 18 |
| Build Tool | Vite |
| Styling | CSS Modules or styled-components |
| Desktop Wrapper | Electron |

### GitHub Pages UI (`docs/index.html`)
| Component | Technology |
|-----------|-----------|
| Language | Vanilla HTML5 / CSS3 / ES6+ |
| Fonts | Google Fonts (Orbitron, Inter, Rajdhani) |
| Animation | CSS animations + Canvas API (starfield) |
| No dependencies | Zero npm packages required |

### Infrastructure
| Component | Technology |
|-----------|-----------|
| Containerization | Docker + Docker Compose |
| CI/CD | GitHub Actions (recommended) |
| Static Hosting | GitHub Pages |

---

## Data Flow

### Static GitHub Pages UI
```
Browser loads docs/index.html
    → Canvas starfield renders (rAF loop)
    → Loader animation (2.2s)
    → setup() runs:
        - Counts games per platform → updates sidebar
        - Calculates stats → animates counters
        - Renders featured game section
        - renderGrid() → builds game cards
    → User interaction:
        - Filter/search/sort → re-calls renderGrid()
        - Card click → openM(idx) → populates modal DOM
        - Launch/download → toast notification
```

### Live Backend Flow (when deployed)
```
Frontend (React/Electron)
    → GET /api/games           → list all games
    → GET /api/games/{id}      → single game detail
    → POST /api/games/{id}/launch  → trigger game launch
    → GET /health              → liveness check

Platform Auth Flow:
    OAuth provider → redirect → backend callback
    → token stored (encrypted) in PostgreSQL
    → token used for platform API calls
```

---

## API Contracts

### `GET /api/games`
**Response** `200 OK`:
```json
[
  {
    "id": 1,
    "title": "The Witcher 3: Wild Hunt",
    "platform": "GOG",
    "installed": true,
    "launch_command": "/path/to/launcher.exe"
  }
]
```

### `GET /api/games/{game_id}`
**Response** `200 OK`: Single game object (same schema)  
**Response** `404 Not Found`: `{"detail": "Game with ID {id} not found."}`

### `POST /api/games/{game_id}/launch`
**Response** `200 OK`: `{"message": "Simulated launch command sent for {title}"}`  
**Response** `400 Bad Request`: Game not installed  
**Response** `404 Not Found`: Game not found  
**Response** `500 Internal Server Error`: No launch command configured

### `GET /health`
**Response** `200 OK`: `{"status": "ok"}`

---

## `docs/index.html` Component Architecture

```
index.html
├── <canvas id="cv">         — Animated starfield (stars + nebulas)
├── #ldr                      — Loading screen (2.2s, progress bar)
└── #app
    ├── #sb (sidebar)
    │   ├── Platform filter buttons (All/Steam/Epic/GOG/Xbox/Ubisoft)
    │   ├── Status filters (All/Installed/Not Installed)
    │   └── Stats panel (hours, installed count)
    └── #mn (main)
        ├── #hdr (header)
        │   ├── Search input (debounced 180ms)
        │   ├── Sort select (A→Z, Rating, Playtime, Newest)
        │   └── View toggle (Grid ⊞ / List ☰)
        └── #cnt (content)
            ├── #feat       — Featured game hero (particles, 3D art)
            ├── #stats      — 4-column stat cards with animated counters
            ├── #gg         — Game grid (CSS Grid, auto-fill minmax 220px)
            │   └── .gc     — Game card (3D tilt, platform glow on hover)
            └── #mo         — Detail modal (hero gradient, playtime bar)
```

### CSS Variable System
```css
:root {
  --bg / --bg2 / --bg3       /* background layers */
  --glass / --glass-b        /* glassmorphism */
  --primary / --primary-dim  /* purple accent */
  --cyan / --green / --amber /* status colors */
  --sw (240px)               /* sidebar width */
  --hh (64px)                /* header height */
}

/* Per-card platform tokens (set inline) */
--pc   /* platform color */
--pg   /* platform glow rgba */
--cg   /* cover gradient */

/* Per-stat-card tokens (set inline) */
--sc-c /* stat accent color */
--sc-g /* stat glow rgba */
```

---

## Game Data Schema (Embedded in docs/index.html)

```javascript
{
  id: number,
  t: string,          // title
  sub: string,        // subtitle
  p: string,          // platform: "Steam" | "Epic" | "GOG" | "Xbox" | "Ubisoft"
  g: string,          // genre
  yr: number,         // year
  dev: string,        // developer
  rat: number,        // rating (0-10)
  inst: boolean,      // installed
  h: number,          // hours played
  sz: string,         // size ("50 GB")
  mh: number,         // max hours for progress bar
  tags: string[],     // up to 4 tags
  desc: string,       // description
  gr: string,         // CSS gradient for cover art
  ar: string          // emoji art character
}
```

---

## Database Schema (Planned)

```sql
-- platforms
CREATE TABLE platforms (
  id SERIAL PRIMARY KEY,
  name VARCHAR(50) UNIQUE NOT NULL,  -- 'steam','epic','gog','xbox','ubisoft'
  display_name VARCHAR(100),
  access_token TEXT,
  refresh_token TEXT,
  token_expires_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- games
CREATE TABLE games (
  id SERIAL PRIMARY KEY,
  title VARCHAR(255) NOT NULL,
  platform_id INTEGER REFERENCES platforms(id),
  external_id VARCHAR(255),          -- platform-specific game ID
  installed BOOLEAN DEFAULT FALSE,
  install_path TEXT,
  launch_command TEXT,
  cover_art_url TEXT,
  genre VARCHAR(100),
  developer VARCHAR(255),
  publisher VARCHAR(255),
  release_year INTEGER,
  playtime_minutes INTEGER DEFAULT 0,
  rating DECIMAL(3,1),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- game_tags
CREATE TABLE game_tags (
  game_id INTEGER REFERENCES games(id),
  tag VARCHAR(50),
  PRIMARY KEY (game_id, tag)
);
```

---

## Environment Setup

### Prerequisites
- Python 3.8+
- Node.js 18+
- PostgreSQL 14+
- Docker (optional)

### Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Create .env from template
cp ../.env.example .env
# Edit .env with your DATABASE_URL and platform credentials

# Start server
uvicorn main:app --reload --port 8000
```

### GitHub Pages Setup (Static UI)
1. Push `docs/index.html` to `main` branch
2. Repo Settings → Pages → Source: `main` / `/docs`
3. Save — site live at `https://Arnav1771.github.io/multi-platform-game-launcher/`

### Docker Setup
```bash
docker-compose up --build
# Backend: http://localhost:8000
# API docs: http://localhost:8000/docs
```

---

## Deployment Notes

### GitHub Pages
- Source: `/docs` folder on `main` branch
- No build step — `docs/index.html` is self-contained
- Google Fonts loaded from CDN (requires internet)
- Recommended: add `.nojekyll` file to `docs/` to skip Jekyll processing

### Backend (Production)
- Run behind nginx or a cloud gateway (Railway, Fly.io, Render)
- Set `DEBUG=false` in production `.env`
- Use `DATABASE_URL` pointing to a managed PostgreSQL instance
- Enable HTTPS — update CORS origins to the production frontend domain
- Store platform OAuth tokens encrypted at rest (AES-256)

### CI/CD (Recommended GitHub Actions)
```yaml
# .github/workflows/pages.yml
on:
  push:
    branches: [main]
    paths: ['docs/**']
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/configure-pages@v4
      - uses: actions/upload-pages-artifact@v3
        with: { path: './docs' }
      - uses: actions/deploy-pages@v4
```
