"""
NEXUS Game Launcher — FastAPI Backend
Handles OAuth login + game library fetching for Steam, Epic, GOG, and Xbox.
"""

import os
import re
import urllib.parse
import logging
import secrets
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
BACKEND_URL   = os.getenv("BACKEND_URL",   "http://localhost:8000")
FRONTEND_URL  = os.getenv("FRONTEND_URL",  "https://Arnav1771.github.io/multi-platform-game-launcher")
SECRET_KEY    = os.getenv("SECRET_KEY",    secrets.token_hex(32))
STEAM_API_KEY = os.getenv("STEAM_API_KEY", "")

EPIC_CLIENT_ID     = os.getenv("EPIC_CLIENT_ID", "")
EPIC_CLIENT_SECRET = os.getenv("EPIC_CLIENT_SECRET", "")

GOG_CLIENT_ID     = os.getenv("GOG_CLIENT_ID", "")
GOG_CLIENT_SECRET = os.getenv("GOG_CLIENT_SECRET", "")

MS_CLIENT_ID     = os.getenv("MICROSOFT_CLIENT_ID", "")
MS_CLIENT_SECRET = os.getenv("MICROSOFT_CLIENT_SECRET", "")

# In-memory session store (use Redis / DB in production)
_sessions: dict[str, dict] = {}

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="NEXUS Game Launcher API",
    description=(
        "Unified game library API. Handles OAuth for Steam, Epic, GOG, and Xbox "
        "and returns the authenticated user's actual game library."
    ),
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten to your GitHub Pages domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _redirect_to_frontend(params: dict) -> RedirectResponse:
    qs = urllib.parse.urlencode(params)
    return RedirectResponse(f"{FRONTEND_URL}?{qs}", status_code=302)


def _new_session(data: dict) -> str:
    token = secrets.token_urlsafe(32)
    _sessions[token] = data
    return token


def _get_session(token: str) -> dict:
    s = _sessions.get(token)
    if not s:
        raise HTTPException(401, "Session expired or invalid. Please log in again.")
    return s


# ─────────────────────────────────────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["system"])
async def health():
    return {
        "status": "ok",
        "version": "2.0.0",
        "platforms": {
            "steam":   bool(STEAM_API_KEY),
            "epic":    bool(EPIC_CLIENT_ID and EPIC_CLIENT_SECRET),
            "gog":     bool(GOG_CLIENT_ID and GOG_CLIENT_SECRET),
            "xbox":    bool(MS_CLIENT_ID and MS_CLIENT_SECRET),
        }
    }


# ─────────────────────────────────────────────────────────────────────────────
# ███████╗████████╗███████╗ █████╗ ███╗   ███╗
# ██╔════╝╚══██╔══╝██╔════╝██╔══██╗████╗ ████║
# ███████╗   ██║   █████╗  ███████║██╔████╔██║
# ╚════██║   ██║   ██╔══╝  ██╔══██║██║╚██╔╝██║
# ███████║   ██║   ███████╗██║  ██║██║ ╚═╝ ██║
# ─────────────────────────────────────────────────────────────────────────────

STEAM_OPENID  = "https://steamcommunity.com/openid/login"
STEAM_API     = "https://api.steampowered.com"
STEAM_CDN     = "https://cdn.akamai.steamstatic.com/steam/apps"


@app.get("/auth/steam/login", tags=["steam"])
async def steam_login():
    """Redirect the browser to Steam's OpenID login page."""
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
    """Steam sends the user back here after login. Verify and pass to frontend."""
    params = dict(request.query_params)
    claimed_id = params.get("openid.claimed_id", "")

    match = re.search(r"/openid/id/(\d+)", claimed_id)
    if not match:
        return _redirect_to_frontend({"auth_error": "steam", "reason": "no_steam_id"})
    steam_id = match.group(1)

    # Ask Steam to confirm the login is genuine
    verify = dict(params)
    verify["openid.mode"] = "check_authentication"
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(STEAM_OPENID, data=verify)
        if "is_valid:true" not in r.text:
            return _redirect_to_frontend({"auth_error": "steam", "reason": "verification_failed"})
    except httpx.TimeoutException:
        return _redirect_to_frontend({"auth_error": "steam", "reason": "timeout"})

    token = _new_session({"platform": "steam", "steam_id": steam_id})
    logger.info(f"Steam login OK: {steam_id}")
    return _redirect_to_frontend({"auth": "steam", "token": token, "steam_id": steam_id})


@app.get("/api/games/steam", tags=["steam"])
async def get_steam_games(
    token: str = Query(..., description="Session token from /auth/steam/callback redirect"),
    api_key: str = Query(None, description="Your Steam Web API key (overrides server-side key)"),
):
    """
    Return the authenticated user's Steam game library.

    The caller must pass the session token received after OAuth.
    Optionally override the server's STEAM_API_KEY with their own.
    Get a free key at https://steamcommunity.com/dev/apikey
    """
    session = _get_session(token)
    if session.get("platform") != "steam":
        raise HTTPException(400, "Token is not a Steam session")

    steam_id = session["steam_id"]
    key = api_key or STEAM_API_KEY
    if not key:
        raise HTTPException(
            400,
            detail={
                "error": "Steam API key required",
                "message": (
                    "No Steam API key is configured on the server. "
                    "Pass your own with ?api_key=YOUR_KEY — "
                    "get a free one at https://steamcommunity.com/dev/apikey"
                ),
            },
        )

    async with httpx.AsyncClient(timeout=20) as c:
        try:
            r = await c.get(
                f"{STEAM_API}/IPlayerService/GetOwnedGames/v1/",
                params={
                    "key": key,
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
    games = [
        {
            "id":            g["appid"],
            "title":         g.get("name", f"App {g['appid']}"),
            "platform":      "Steam",
            "installed":     False,
            "playtime_hours": round(g.get("playtime_forever", 0) / 60, 1),
            "cover_url":     f"{STEAM_CDN}/{g['appid']}/library_600x900.jpg",
            "banner_url":    f"{STEAM_CDN}/{g['appid']}/header.jpg",
            "launch_command":f"steam://run/{g['appid']}",
            "store_url":     f"https://store.steampowered.com/app/{g['appid']}",
        }
        for g in sorted(raw, key=lambda x: x.get("name", ""))
    ]

    return {"platform": "Steam", "steam_id": steam_id, "count": len(games), "games": games}


@app.get("/api/user/steam", tags=["steam"])
async def get_steam_profile(
    token: str = Query(...),
    api_key: str = Query(None),
):
    session = _get_session(token)
    steam_id = session["steam_id"]
    key = api_key or STEAM_API_KEY
    if not key:
        raise HTTPException(400, "Steam API key required")

    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(
            f"{STEAM_API}/ISteamUser/GetPlayerSummaries/v2/",
            params={"key": key, "steamids": steam_id},
        )
    players = r.json().get("response", {}).get("players", [])
    if not players:
        raise HTTPException(404, "Steam profile not found or private")
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

EPIC_AUTH_URL   = "https://www.epicgames.com/id/authorize"
EPIC_TOKEN_URL  = "https://api.epicgames.dev/epic/oauth/v2/token"
EPIC_ENTITLE    = "https://api.epicgames.dev/epic/ecom/v3/platforms/EPIC/identities/{account_id}/entitlements"
EPIC_CATALOG    = "https://api.epicgames.dev/epic/ecom/v3/assets/EPIC"


@app.get("/auth/epic/login", tags=["epic"])
async def epic_login():
    """Redirect to Epic Games OAuth. Requires EPIC_CLIENT_ID in .env"""
    if not EPIC_CLIENT_ID:
        raise HTTPException(
            501,
            detail={
                "error": "Epic not configured",
                "steps": [
                    "1. Register at https://dev.epicgames.com/portal",
                    "2. Create an application",
                    "3. Add EPIC_CLIENT_ID and EPIC_CLIENT_SECRET to your .env",
                    "4. Set redirect URI to: " + BACKEND_URL + "/auth/epic/callback",
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
        return _redirect_to_frontend({"auth_error": "epic", "reason": error or "no_code"})

    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(
            EPIC_TOKEN_URL,
            data={
                "grant_type":   "authorization_code",
                "code":          code,
                "redirect_uri":  f"{BACKEND_URL}/auth/epic/callback",
            },
            auth=(EPIC_CLIENT_ID, EPIC_CLIENT_SECRET),
        )
    if r.status_code != 200:
        return _redirect_to_frontend({"auth_error": "epic", "reason": "token_exchange_failed"})

    data = r.json()
    token = _new_session({
        "platform":    "epic",
        "account_id":  data.get("account_id", ""),
        "access_token": data.get("access_token", ""),
        "display_name": data.get("displayName", ""),
    })
    logger.info(f"Epic login OK: {data.get('displayName')}")
    return _redirect_to_frontend({"auth": "epic", "token": token})


@app.get("/api/games/epic", tags=["epic"])
async def get_epic_games(token: str = Query(...)):
    """Return the user's Epic Games entitlements (owned games)."""
    session = _get_session(token)
    if session.get("platform") != "epic":
        raise HTTPException(400, "Token is not an Epic session")

    account_id   = session["account_id"]
    access_token = session["access_token"]

    # Fetch entitlements (all owned items including DLC)
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
            "id":       item.get("id", ""),
            "title":    item.get("displayName") or item.get("entitlementName", "Unknown"),
            "platform": "Epic",
            "installed": False,
            "cover_url": "",   # Epic doesn't return art here; would need catalog API lookup
            "launch_command": f"com.epicgames.launcher://apps/{item.get('catalogItemId', '')}?action=launch",
        }
        for item in items
        if item.get("entitlementType") in ("EXECUTABLE", "AUDIENCE")
    ]

    return {
        "platform": "Epic",
        "account_id": account_id,
        "display_name": session.get("display_name", ""),
        "count": len(games),
        "games": games,
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
                "steps": [
                    "1. Apply for GOG developer access at https://www.gog.com/developer",
                    "2. Add GOG_CLIENT_ID and GOG_CLIENT_SECRET to your .env",
                    "3. Set redirect URI to: " + BACKEND_URL + "/auth/gog/callback",
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
        return _redirect_to_frontend({"auth_error": "gog", "reason": error or "no_code"})

    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(
            GOG_TOKEN_URL,
            data={
                "client_id":     GOG_CLIENT_ID,
                "client_secret": GOG_CLIENT_SECRET,
                "grant_type":    "authorization_code",
                "code":           code,
                "redirect_uri":   f"{BACKEND_URL}/auth/gog/callback",
            },
        )
    if r.status_code != 200:
        return _redirect_to_frontend({"auth_error": "gog", "reason": "token_exchange_failed"})

    data = r.json()
    token = _new_session({
        "platform":      "gog",
        "access_token":  data.get("access_token", ""),
        "refresh_token": data.get("refresh_token", ""),
        "username":      data.get("userId", ""),
    })
    logger.info("GOG login OK")
    return _redirect_to_frontend({"auth": "gog", "token": token})


@app.get("/api/games/gog", tags=["gog"])
async def get_gog_games(
    token: str = Query(...),
    page: int = Query(1, ge=1, le=200),
):
    session = _get_session(token)
    if session.get("platform") != "gog":
        raise HTTPException(400, "Token is not a GOG session")

    access_token = session["access_token"]
    all_games, current_page = [], 1

    async with httpx.AsyncClient(timeout=20) as c:
        while True:
            r = await c.get(
                GOG_LIBRARY,
                params={"mediaType": 1, "sortBy": "title", "page": current_page},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if r.status_code == 401:
                raise HTTPException(401, "GOG session expired. Please log in again.")
            r.raise_for_status()
            data = r.json()

            for p in data.get("products", []):
                img = p.get("image", "")
                all_games.append({
                    "id":       p["id"],
                    "title":    p.get("title", "Unknown"),
                    "platform": "GOG",
                    "installed": False,
                    "cover_url": f"https:{img}_392.jpg" if img else "",
                    "launch_command": f"goggalaxy://openGameView/{p['id']}",
                    "store_url":      f"https://www.gog.com{p.get('url', '')}",
                })

            total_pages = data.get("totalPages", 1)
            if current_page >= total_pages:
                break
            current_page += 1

    return {"platform": "GOG", "count": len(all_games), "games": all_games}


# ─────────────────────────────────────────────────────────────────────────────
# ██╗  ██╗██████╗  ██████╗ ██╗  ██╗
# ╚██╗██╔╝██╔══██╗██╔═══██╗╚██╗██╔╝
#  ╚███╔╝ ██████╔╝██║   ██║ ╚███╔╝
#  ██╔██╗ ██╔══██╗██║   ██║ ██╔██╗
# ██╔╝ ██╗██████╔╝╚██████╔╝██╔╝ ██╗
# ─────────────────────────────────────────────────────────────────────────────

MS_AUTH_BASE  = "https://login.microsoftonline.com/consumers/oauth2/v2.0"
MS_TOKEN_URL  = f"{MS_AUTH_BASE}/token"
XBOX_LIVE_AUTH     = "https://user.auth.xboxlive.com/user/authenticate"
XBOX_LIVE_XSTS     = "https://xsts.auth.xboxlive.com/xsts/authorize"
XBOX_TITLE_HUB     = "https://titlehub.xboxlive.com/users/xuid({xuid})/titles/titlehistory/decoration/Image,detail,GamePass"


@app.get("/auth/xbox/login", tags=["xbox"])
async def xbox_login():
    if not MS_CLIENT_ID:
        raise HTTPException(
            501,
            detail={
                "error": "Xbox not configured",
                "steps": [
                    "1. Register app at https://portal.azure.com → App registrations",
                    "2. Add permission: XboxLive.signin (Microsoft Graph)",
                    "3. Add MICROSOFT_CLIENT_ID and MICROSOFT_CLIENT_SECRET to .env",
                    "4. Set redirect URI to: " + BACKEND_URL + "/auth/xbox/callback",
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
        return _redirect_to_frontend({"auth_error": "xbox", "reason": error or "no_code"})

    # 1. Exchange code for Microsoft access token
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(MS_TOKEN_URL, data={
            "client_id":     MS_CLIENT_ID,
            "client_secret": MS_CLIENT_SECRET,
            "grant_type":    "authorization_code",
            "code":           code,
            "redirect_uri":   f"{BACKEND_URL}/auth/xbox/callback",
            "scope":          "XboxLive.signin XboxLive.offline_access",
        })
    if r.status_code != 200:
        return _redirect_to_frontend({"auth_error": "xbox", "reason": "ms_token_failed"})
    ms_token = r.json().get("access_token", "")

    # 2. Exchange Microsoft token for Xbox Live token
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(XBOX_LIVE_AUTH, json={
            "Properties": {
                "AuthMethod": "RPS",
                "SiteName":   "user.auth.xboxlive.com",
                "RpsTicket":  f"d={ms_token}",
            },
            "RelyingParty": "http://auth.xboxlive.com",
            "TokenType":    "JWT",
        }, headers={"Content-Type": "application/json", "Accept": "application/json"})
    if r.status_code != 200:
        return _redirect_to_frontend({"auth_error": "xbox", "reason": "xbl_auth_failed"})
    xbl = r.json()
    xbl_token   = xbl.get("Token", "")
    user_hash   = xbl.get("DisplayClaims", {}).get("xui", [{}])[0].get("uhs", "")

    # 3. Exchange for XSTS token
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(XBOX_LIVE_XSTS, json={
            "Properties": {
                "SandboxId":  "RETAIL",
                "UserTokens": [xbl_token],
            },
            "RelyingParty": "http://xboxlive.com",
            "TokenType":    "JWT",
        }, headers={"Content-Type": "application/json", "Accept": "application/json"})
    if r.status_code != 200:
        return _redirect_to_frontend({"auth_error": "xbox", "reason": "xsts_failed"})
    xsts = r.json()
    xsts_token = xsts.get("Token", "")
    xuid = xsts.get("DisplayClaims", {}).get("xui", [{}])[0].get("xid", "")

    token = _new_session({
        "platform":   "xbox",
        "xuid":        xuid,
        "xsts_token":  xsts_token,
        "user_hash":   user_hash,
        "gamertag":    xsts.get("DisplayClaims", {}).get("xui", [{}])[0].get("gtg", ""),
    })
    logger.info(f"Xbox login OK: xuid={xuid}")
    return _redirect_to_frontend({"auth": "xbox", "token": token})


@app.get("/api/games/xbox", tags=["xbox"])
async def get_xbox_games(token: str = Query(...)):
    """Return the user's Xbox title history (played games)."""
    session = _get_session(token)
    if session.get("platform") != "xbox":
        raise HTTPException(400, "Token is not an Xbox session")

    xuid       = session["xuid"]
    xsts_token = session["xsts_token"]
    user_hash  = session["user_hash"]
    auth_hdr   = f"XBL3.0 x={user_hash};{xsts_token}"

    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(
            XBOX_TITLE_HUB.format(xuid=xuid),
            headers={
                "Authorization": auth_hdr,
                "x-xbl-contract-version": "2",
                "Accept-Language": "en-US",
            },
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
            "id":       t.get("titleId", ""),
            "title":    t.get("name", "Unknown"),
            "platform": "Xbox",
            "installed": False,
            "playtime_hours": round(t.get("titleHistory", {}).get("minutesPlayed", 0) / 60, 1),
            "cover_url":     cover,
            "launch_command": f"ms-xbl-{t.get('titleId', '')}://",
        })

    return {
        "platform": "Xbox",
        "xuid": xuid,
        "gamertag": session.get("gamertag", ""),
        "count": len(games),
        "games": games,
    }


# ─────────────────────────────────────────────────────────────────────────────
# EA — No public API
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/auth/ea/login", tags=["ea"])
async def ea_login():
    raise HTTPException(
        501,
        detail={
            "error": "EA / EA App not supported",
            "reason": "EA does not provide a public API for accessing game libraries.",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# Combined library — aggregates all connected platforms
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/games", tags=["library"])
async def get_all_games(
    steam_token:  str = Query(None),
    steam_apikey: str = Query(None),
    epic_token:   str = Query(None),
    gog_token:    str = Query(None),
    xbox_token:   str = Query(None),
):
    """
    Aggregate games from all connected platforms into one list.
    Pass the session token for each platform you want to include.
    """
    all_games: list = []
    errors:    list = []

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
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
