"""
NEXUS Game Launcher — FastAPI Backend
Handles OAuth login + game library fetching for Steam, Epic, GOG, and Xbox.
Deploy to Render: see render.yaml in the repo root.
"""

import json
import os
import re
import secrets
import time
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
BACKEND_URL  = os.getenv("BACKEND_URL",  "http://localhost:8000")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://Arnav1771.github.io/multi-platform-game-launcher")
SECRET_KEY   = os.getenv("SECRET_KEY",   secrets.token_hex(32))

STEAM_API_KEY = os.getenv("STEAM_API_KEY", "")

EPIC_CLIENT_ID     = os.getenv("EPIC_CLIENT_ID", "")
EPIC_CLIENT_SECRET = os.getenv("EPIC_CLIENT_SECRET", "")

GOG_CLIENT_ID     = os.getenv("GOG_CLIENT_ID", "")
GOG_CLIENT_SECRET = os.getenv("GOG_CLIENT_SECRET", "")

MS_CLIENT_ID     = os.getenv("MICROSOFT_CLIENT_ID", "")
MS_CLIENT_SECRET = os.getenv("MICROSOFT_CLIENT_SECRET", "")

# Session TTL: 8 hours
SESSION_TTL = 60 * 60 * 8

# ── Session store (file-backed so Render sleep doesn't wipe tokens) ──────────
_SESSION_PATH = Path(os.getenv("SESSION_FILE", "/tmp/nexus_sessions.json"))

def _load_sessions() -> dict:
    try:
        if _SESSION_PATH.exists():
            data = json.loads(_SESSION_PATH.read_text())
            now = time.time()
            # Evict expired sessions
            return {k: v for k, v in data.items() if v.get("_exp", 0) > now}
    except Exception:
        pass
    return {}

def _save_sessions(s: dict) -> None:
    try:
        _SESSION_PATH.write_text(json.dumps(s))
    except Exception:
        pass

def new_session(data: dict) -> str:
    token = secrets.token_urlsafe(32)
    sessions = _load_sessions()
    sessions[token] = {**data, "_exp": time.time() + SESSION_TTL}
    _save_sessions(sessions)
    return token

def get_session(token: str) -> dict:
    sessions = _load_sessions()
    s = sessions.get(token)
    if not s or s.get("_exp", 0) < time.time():
        raise HTTPException(401, "Session expired or invalid. Please log in again.")
    return s

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="NEXUS Game Launcher API",
    description=(
        "Personal game library aggregator. Handles OAuth for Steam, Epic, GOG, and Xbox "
        "and returns the user's own game library. No user data is stored beyond the current session."
    ),
    version="2.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def redirect_to_frontend(**params) -> RedirectResponse:
    qs = urllib.parse.urlencode(params)
    return RedirectResponse(f"{FRONTEND_URL}?{qs}", status_code=302)


# ─────────────────────────────────────────────────────────────────────────────
# Health / status
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["system"])
async def health():
    return {
        "status": "ok",
        "version": "2.1.0",
        "configured": {
            "steam":   bool(STEAM_API_KEY),
            "epic":    bool(EPIC_CLIENT_ID and EPIC_CLIENT_SECRET),
            "gog":     bool(GOG_CLIENT_ID and GOG_CLIENT_SECRET),
            "xbox":    bool(MS_CLIENT_ID and MS_CLIENT_SECRET),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# ███████╗████████╗███████╗ █████╗ ███╗   ███╗
# ██╔════╝╚══██╔══╝██╔════╝██╔══██╗████╗ ████║
# ███████╗   ██║   █████╗  ███████║██╔████╔██║
# ╚════██║   ██║   ██╔══╝  ██╔══██║██║╚██╔╝██║
# ███████║   ██║   ███████╗██║  ██║██║ ╚═╝ ██║
# ─────────────────────────────────────────────────────────────────────────────

STEAM_OPENID = "https://steamcommunity.com/openid/login"
STEAM_API    = "https://api.steampowered.com"
STEAM_CDN    = "https://cdn.akamai.steamstatic.com/steam/apps"


@app.get("/auth/steam/login", tags=["steam"])
async def steam_login():
    """Redirect to Steam OpenID. No credentials needed — it's free."""
    params = {
        "openid.ns":         "http://specs.openid.net/auth/2.0",
        "openid.mode":       "checkid_setup",
        "openid.return_to":  f"{BACKEND_URL}/auth/steam/callback",
        "openid.realm":      BACKEND_URL,
        "openid.identity":   "http://specs.openid.net/auth/2.0/identifier_select",
        "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select",
    }
    return RedirectResponse(f"{STEAM_OPENID}?{urllib.parse.urlencode(params)}")


@app.get("/auth/steam/callback", tags=["steam"])
async def steam_callback(request: Request):
    params = dict(request.query_params)
    claimed_id = params.get("openid.claimed_id", "")
    match = re.search(r"/openid/id/(\d+)", claimed_id)
    if not match:
        return redirect_to_frontend(auth_error="steam", reason="no_steam_id")
    steam_id = match.group(1)

    # Verify with Steam
    verify = {**params, "openid.mode": "check_authentication"}
    try:
        async with httpx.AsyncClient(timeout=12) as c:
            r = await c.post(STEAM_OPENID, data=verify)
        if "is_valid:true" not in r.text:
            return redirect_to_frontend(auth_error="steam", reason="verification_failed")
    except httpx.TimeoutException:
        return redirect_to_frontend(auth_error="steam", reason="timeout")

    token = new_session({"platform": "steam", "steam_id": steam_id})
    return redirect_to_frontend(auth="steam", token=token, steam_id=steam_id)


@app.get("/api/games/steam", tags=["steam"])
async def get_steam_games(
    token: str = Query(...),
    api_key: str = Query(None, description="Steam Web API key — free at steamcommunity.com/dev/apikey"),
):
    """
    Fetch the user's Steam library.
    - With an API key: uses the official Steam Web API (all games, accurate hours).
    - Without an API key: falls back to the public Steam profile XML (public profiles only).
    """
    session = get_session(token)
    if session.get("platform") != "steam":
        raise HTTPException(400, "Not a Steam session")

    steam_id = session["steam_id"]
    key = api_key or STEAM_API_KEY

    if key:
        return await _steam_games_via_api(steam_id, key)
    else:
        return await _steam_games_via_xml(steam_id)


async def _steam_games_via_api(steam_id: str, api_key: str) -> dict:
    """Official Steam Web API — requires a free API key."""
    async with httpx.AsyncClient(timeout=20) as c:
        try:
            r = await c.get(
                f"{STEAM_API}/IPlayerService/GetOwnedGames/v1/",
                params={
                    "key": api_key,
                    "steamid": steam_id,
                    "include_appinfo": 1,
                    "include_played_free_games": 0,
                },
            )
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(e.response.status_code, f"Steam API error: {e.response.text[:200]}")
        except httpx.TimeoutException:
            raise HTTPException(504, "Steam API timed out")

    raw = r.json().get("response", {}).get("games", [])
    if not raw:
        # Profile may be private
        raise HTTPException(
            403,
            detail={
                "error": "Steam library is private",
                "fix": "Set your Steam game details to Public at steamcommunity.com/my/edit/settings",
            },
        )

    games = [
        {
            "id":             g["appid"],
            "title":          g.get("name", f"App {g['appid']}"),
            "platform":       "Steam",
            "installed":      False,
            "playtime_hours": round(g.get("playtime_forever", 0) / 60, 1),
            "cover_url":      f"{STEAM_CDN}/{g['appid']}/library_600x900.jpg",
            "banner_url":     f"{STEAM_CDN}/{g['appid']}/header.jpg",
            "launch_command": f"steam://run/{g['appid']}",
            "store_url":      f"https://store.steampowered.com/app/{g['appid']}",
        }
        for g in sorted(raw, key=lambda x: x.get("name", ""))
    ]
    return {"platform": "Steam", "steam_id": steam_id, "source": "api", "count": len(games), "games": games}


async def _steam_games_via_xml(steam_id: str) -> dict:
    """
    Public XML fallback — no API key needed.
    Only works if the user's Steam game list is set to Public.
    """
    url = f"https://steamcommunity.com/profiles/{steam_id}/games?tab=all&xml=1"
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as c:
        try:
            r = await c.get(url)
            r.raise_for_status()
        except Exception as e:
            raise HTTPException(502, f"Could not fetch public Steam profile: {e}")

    try:
        root = ET.fromstring(r.text)
    except ET.ParseError:
        raise HTTPException(
            403,
            detail={
                "error": "Steam profile is private or returned invalid data",
                "fix": (
                    "Either set your Steam game list to Public at "
                    "steamcommunity.com/my/edit/settings, "
                    "or provide a Steam API key for reliable access."
                ),
            },
        )

    games = []
    for game in root.findall(".//game"):
        app_id_el = game.find("appID")
        name_el   = game.find("name")
        hours_el  = game.find("hoursOnRecord")
        logo_el   = game.find("logo")
        if app_id_el is None or name_el is None:
            continue
        app_id = app_id_el.text or ""
        hours_str = (hours_el.text or "0").replace(",", "")
        try:
            hours = round(float(hours_str), 1)
        except ValueError:
            hours = 0.0
        games.append({
            "id":             app_id,
            "title":          name_el.text or f"App {app_id}",
            "platform":       "Steam",
            "installed":      False,
            "playtime_hours": hours,
            "cover_url":      logo_el.text or f"{STEAM_CDN}/{app_id}/capsule_231x87.jpg",
            "banner_url":     f"{STEAM_CDN}/{app_id}/header.jpg",
            "launch_command": f"steam://run/{app_id}",
            "store_url":      f"https://store.steampowered.com/app/{app_id}",
        })

    games.sort(key=lambda g: g["title"])
    return {"platform": "Steam", "steam_id": steam_id, "source": "public_xml", "count": len(games), "games": games}


@app.get("/api/user/steam", tags=["steam"])
async def get_steam_profile(token: str = Query(...), api_key: str = Query(None)):
    session = get_session(token)
    steam_id = session["steam_id"]
    key = api_key or STEAM_API_KEY
    if not key:
        return {"platform": "Steam", "steam_id": steam_id, "username": f"Steam user {steam_id[-4:]}"}

    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{STEAM_API}/ISteamUser/GetPlayerSummaries/v2/", params={"key": key, "steamids": steam_id})
    players = r.json().get("response", {}).get("players", [])
    if not players:
        raise HTTPException(404, "Profile not found or private")
    p = players[0]
    return {
        "platform":    "Steam",
        "steam_id":    steam_id,
        "username":    p.get("personaname", ""),
        "avatar":      p.get("avatarfull", ""),
        "profile_url": p.get("profileurl", ""),
    }


# ─────────────────────────────────────────────────────────────────────────────
# ███████╗██████╗ ██╗ ██████╗
# ██╔════╝██╔══██╗██║██╔════╝
# █████╗  ██████╔╝██║██║
# ██╔══╝  ██╔═══╝ ██║██║
# ███████╗██║     ██║╚██████╗
# ─────────────────────────────────────────────────────────────────────────────

EPIC_AUTH_URL  = "https://www.epicgames.com/id/authorize"
EPIC_TOKEN_URL = "https://api.epicgames.dev/epic/oauth/v2/token"
EPIC_ENTITLE   = "https://api.epicgames.dev/epic/ecom/v3/platforms/EPIC/identities/{account_id}/entitlements"


@app.get("/auth/epic/login", tags=["epic"])
async def epic_login():
    if not EPIC_CLIENT_ID:
        raise HTTPException(
            501,
            detail={
                "error": "Epic Games not configured",
                "setup": [
                    "1. Register at https://dev.epicgames.com/portal",
                    "2. Create an Application",
                    "3. Set redirect URI to: " + BACKEND_URL + "/auth/epic/callback",
                    "4. Add EPIC_CLIENT_ID + EPIC_CLIENT_SECRET to Render environment variables",
                ],
            },
        )
    params = {
        "client_id":     EPIC_CLIENT_ID,
        "redirect_uri":  f"{BACKEND_URL}/auth/epic/callback",
        "response_type": "code",
        "scope":         "basic_profile friends_list openid presence",
    }
    return RedirectResponse(f"{EPIC_AUTH_URL}?{urllib.parse.urlencode(params)}")


@app.get("/auth/epic/callback", tags=["epic"])
async def epic_callback(code: str = Query(None), error: str = Query(None)):
    if error or not code:
        return redirect_to_frontend(auth_error="epic", reason=error or "no_code")

    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(
            EPIC_TOKEN_URL,
            data={
                "grant_type":  "authorization_code",
                "code":         code,
                "redirect_uri": f"{BACKEND_URL}/auth/epic/callback",
            },
            auth=(EPIC_CLIENT_ID, EPIC_CLIENT_SECRET),
        )
    if r.status_code != 200:
        return redirect_to_frontend(auth_error="epic", reason="token_exchange_failed")

    data = r.json()
    token = new_session({
        "platform":     "epic",
        "account_id":   data.get("account_id", ""),
        "access_token": data.get("access_token", ""),
        "display_name": data.get("displayName", ""),
    })
    return redirect_to_frontend(auth="epic", token=token)


@app.get("/api/games/epic", tags=["epic"])
async def get_epic_games(token: str = Query(...)):
    session = get_session(token)
    if session.get("platform") != "epic":
        raise HTTPException(400, "Not an Epic session")

    account_id   = session["account_id"]
    access_token = session["access_token"]

    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(
            EPIC_ENTITLE.format(account_id=account_id),
            headers={"Authorization": f"Bearer {access_token}"},
            params={"start": 0, "count": 1000},
        )
    if r.status_code == 401:
        raise HTTPException(401, "Epic session expired. Please log in again.")
    r.raise_for_status()

    items = r.json() if isinstance(r.json(), list) else r.json().get("data", [])
    games = [
        {
            "id":             item.get("id", ""),
            "title":          item.get("displayName") or item.get("entitlementName", "Unknown"),
            "platform":       "Epic",
            "installed":      False,
            "playtime_hours": 0,
            "cover_url":      "",
            "launch_command": f"com.epicgames.launcher://apps/{item.get('catalogItemId', '')}?action=launch",
        }
        for item in items
        if item.get("entitlementType") in ("EXECUTABLE", "AUDIENCE")
    ]
    return {
        "platform":     "Epic",
        "account_id":   account_id,
        "display_name": session.get("display_name", ""),
        "count":        len(games),
        "games":        games,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  ██████╗  ██████╗  ██████╗
# ██╔════╝ ██╔═══██╗██╔════╝
# ██║  ███╗██║   ██║██║  ███╗
# ██║   ██║██║   ██║██║   ██║
# ╚██████╔╝╚██████╔╝╚██████╔╝
# ─────────────────────────────────────────────────────────────────────────────

GOG_AUTH_URL  = "https://auth.gog.com/auth"
GOG_TOKEN_URL = "https://auth.gog.com/token"
GOG_LIBRARY   = "https://embed.gog.com/account/getFilteredProducts"


@app.get("/auth/gog/login", tags=["gog"])
async def gog_login():
    if not GOG_CLIENT_ID:
        raise HTTPException(
            501,
            detail={
                "error": "GOG not configured",
                "setup": [
                    "1. Apply at https://www.gog.com/developer",
                    "2. Set redirect URI to: " + BACKEND_URL + "/auth/gog/callback",
                    "3. Add GOG_CLIENT_ID + GOG_CLIENT_SECRET to Render environment variables",
                ],
            },
        )
    params = {
        "client_id":     GOG_CLIENT_ID,
        "redirect_uri":  f"{BACKEND_URL}/auth/gog/callback",
        "response_type": "code",
        "layout":        "client2",
    }
    return RedirectResponse(f"{GOG_AUTH_URL}?{urllib.parse.urlencode(params)}")


@app.get("/auth/gog/callback", tags=["gog"])
async def gog_callback(code: str = Query(None), error: str = Query(None)):
    if error or not code:
        return redirect_to_frontend(auth_error="gog", reason=error or "no_code")

    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(GOG_TOKEN_URL, data={
            "client_id":     GOG_CLIENT_ID,
            "client_secret": GOG_CLIENT_SECRET,
            "grant_type":    "authorization_code",
            "code":           code,
            "redirect_uri":   f"{BACKEND_URL}/auth/gog/callback",
        })
    if r.status_code != 200:
        return redirect_to_frontend(auth_error="gog", reason="token_exchange_failed")

    data = r.json()
    token = new_session({
        "platform":      "gog",
        "access_token":  data.get("access_token", ""),
        "refresh_token": data.get("refresh_token", ""),
    })
    return redirect_to_frontend(auth="gog", token=token)


@app.get("/api/games/gog", tags=["gog"])
async def get_gog_games(token: str = Query(...)):
    session = get_session(token)
    if session.get("platform") != "gog":
        raise HTTPException(400, "Not a GOG session")

    access_token = session["access_token"]
    all_games, page = [], 1

    async with httpx.AsyncClient(timeout=20) as c:
        while True:
            r = await c.get(
                GOG_LIBRARY,
                params={"mediaType": 1, "sortBy": "title", "page": page},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if r.status_code == 401:
                raise HTTPException(401, "GOG session expired. Please log in again.")
            r.raise_for_status()
            data = r.json()

            for p in data.get("products", []):
                img = p.get("image", "")
                all_games.append({
                    "id":             p["id"],
                    "title":          p.get("title", "Unknown"),
                    "platform":       "GOG",
                    "installed":      False,
                    "playtime_hours": 0,
                    "cover_url":      f"https:{img}_392.jpg" if img else "",
                    "launch_command": f"goggalaxy://openGameView/{p['id']}",
                    "store_url":      f"https://www.gog.com{p.get('url', '')}",
                })

            if page >= data.get("totalPages", 1):
                break
            page += 1

    return {"platform": "GOG", "count": len(all_games), "games": all_games}


# ─────────────────────────────────────────────────────────────────────────────
# ██╗  ██╗██████╗  ██████╗ ██╗  ██╗
# ╚██╗██╔╝██╔══██╗██╔═══██╗╚██╗██╔╝
#  ╚███╔╝ ██████╔╝██║   ██║ ╚███╔╝
#  ██╔██╗ ██╔══██╗██║   ██║ ██╔██╗
# ██╔╝ ██╗██████╔╝╚██████╔╝██╔╝ ██╗
# ─────────────────────────────────────────────────────────────────────────────

MS_AUTH_BASE = "https://login.microsoftonline.com/consumers/oauth2/v2.0"
XBL_AUTH     = "https://user.auth.xboxlive.com/user/authenticate"
XBL_XSTS     = "https://xsts.auth.xboxlive.com/xsts/authorize"
TITLE_HUB    = "https://titlehub.xboxlive.com/users/xuid({xuid})/titles/titlehistory/decoration/Image,detail"


@app.get("/auth/xbox/login", tags=["xbox"])
async def xbox_login():
    if not MS_CLIENT_ID:
        raise HTTPException(
            501,
            detail={
                "error": "Xbox not configured",
                "setup": [
                    "1. Register at https://portal.azure.com → App registrations",
                    "2. Add permission: XboxLive.signin",
                    "3. Set redirect URI to: " + BACKEND_URL + "/auth/xbox/callback",
                    "4. Add MICROSOFT_CLIENT_ID + MICROSOFT_CLIENT_SECRET to Render env vars",
                ],
            },
        )
    params = {
        "client_id":     MS_CLIENT_ID,
        "redirect_uri":  f"{BACKEND_URL}/auth/xbox/callback",
        "response_type": "code",
        "scope":         "XboxLive.signin XboxLive.offline_access",
        "response_mode": "query",
    }
    return RedirectResponse(f"{MS_AUTH_BASE}/authorize?{urllib.parse.urlencode(params)}")


@app.get("/auth/xbox/callback", tags=["xbox"])
async def xbox_callback(code: str = Query(None), error: str = Query(None)):
    if error or not code:
        return redirect_to_frontend(auth_error="xbox", reason=error or "no_code")

    # Step 1: Microsoft auth code → access token
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(f"{MS_AUTH_BASE}/token", data={
            "client_id":     MS_CLIENT_ID,
            "client_secret": MS_CLIENT_SECRET,
            "grant_type":    "authorization_code",
            "code":           code,
            "redirect_uri":   f"{BACKEND_URL}/auth/xbox/callback",
            "scope":          "XboxLive.signin XboxLive.offline_access",
        })
    if r.status_code != 200:
        return redirect_to_frontend(auth_error="xbox", reason="ms_token_failed")
    ms_token = r.json().get("access_token", "")

    # Step 2: Microsoft token → Xbox Live token
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(XBL_AUTH, json={
            "Properties": {"AuthMethod": "RPS", "SiteName": "user.auth.xboxlive.com", "RpsTicket": f"d={ms_token}"},
            "RelyingParty": "http://auth.xboxlive.com",
            "TokenType": "JWT",
        }, headers={"Content-Type": "application/json", "Accept": "application/json"})
    if r.status_code != 200:
        return redirect_to_frontend(auth_error="xbox", reason="xbl_failed")
    xbl = r.json()
    xbl_token = xbl.get("Token", "")
    user_hash = xbl.get("DisplayClaims", {}).get("xui", [{}])[0].get("uhs", "")

    # Step 3: Xbox Live token → XSTS token
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(XBL_XSTS, json={
            "Properties": {"SandboxId": "RETAIL", "UserTokens": [xbl_token]},
            "RelyingParty": "http://xboxlive.com",
            "TokenType": "JWT",
        }, headers={"Content-Type": "application/json", "Accept": "application/json"})
    if r.status_code != 200:
        return redirect_to_frontend(auth_error="xbox", reason="xsts_failed")
    xsts = r.json()
    xsts_token = xsts.get("Token", "")
    xui = xsts.get("DisplayClaims", {}).get("xui", [{}])[0]

    token = new_session({
        "platform":   "xbox",
        "xuid":        xui.get("xid", ""),
        "xsts_token":  xsts_token,
        "user_hash":   user_hash,
        "gamertag":    xui.get("gtg", ""),
    })
    return redirect_to_frontend(auth="xbox", token=token)


@app.get("/api/games/xbox", tags=["xbox"])
async def get_xbox_games(token: str = Query(...)):
    session = get_session(token)
    if session.get("platform") != "xbox":
        raise HTTPException(400, "Not an Xbox session")

    xuid       = session["xuid"]
    xsts_token = session["xsts_token"]
    user_hash  = session["user_hash"]
    auth_hdr   = f"XBL3.0 x={user_hash};{xsts_token}"

    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(
            TITLE_HUB.format(xuid=xuid),
            headers={"Authorization": auth_hdr, "x-xbl-contract-version": "2", "Accept-Language": "en-US"},
        )
    if r.status_code == 401:
        raise HTTPException(401, "Xbox session expired. Please log in again.")
    r.raise_for_status()

    titles = r.json().get("titles", [])
    games = []
    for t in titles:
        imgs = t.get("imageList") or t.get("images", [])
        cover = next((i.get("url") for i in imgs if i.get("purpose") in ("BrandedKeyArt", "BoxArt")), "")
        games.append({
            "id":             t.get("titleId", ""),
            "title":          t.get("name", "Unknown"),
            "platform":       "Xbox",
            "installed":      False,
            "playtime_hours": round(t.get("titleHistory", {}).get("minutesPlayed", 0) / 60, 1),
            "cover_url":      cover,
            "launch_command": f"ms-xbl-{t.get('titleId', '')}://",
        })

    return {
        "platform": "Xbox",
        "xuid":     xuid,
        "gamertag": session.get("gamertag", ""),
        "count":    len(games),
        "games":    games,
    }


# ─────────────────────────────────────────────────────────────────────────────
# EA — no public API
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/auth/ea/login", tags=["ea"])
async def ea_login():
    raise HTTPException(501, detail={
        "error": "EA / EA App does not have a public game library API",
        "reason": "EA has not released developer API access for third-party launchers.",
    })


# ─────────────────────────────────────────────────────────────────────────────
# Combined library
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/games", tags=["library"])
async def get_all_games(
    steam_token:  str = Query(None),
    steam_apikey: str = Query(None),
    epic_token:   str = Query(None),
    gog_token:    str = Query(None),
    xbox_token:   str = Query(None),
):
    all_games, errors = [], []

    if steam_token:
        try:
            r = await get_steam_games(steam_token, steam_apikey)
            all_games.extend(r["games"])
        except Exception as e:
            errors.append({"platform": "Steam", "error": str(e)})

    if epic_token:
        try:
            r = await get_epic_games(epic_token)
            all_games.extend(r["games"])
        except Exception as e:
            errors.append({"platform": "Epic", "error": str(e)})

    if gog_token:
        try:
            r = await get_gog_games(gog_token)
            all_games.extend(r["games"])
        except Exception as e:
            errors.append({"platform": "GOG", "error": str(e)})

    if xbox_token:
        try:
            r = await get_xbox_games(xbox_token)
            all_games.extend(r["games"])
        except Exception as e:
            errors.append({"platform": "Xbox", "error": str(e)})

    return {"total": len(all_games), "games": all_games, "errors": errors}


# ─────────────────────────────────────────────────────────────────────────────
# Dev runner
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True)
