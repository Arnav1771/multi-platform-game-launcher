"""
NEXUS Game Launcher — Vercel Serverless Backend
All sessions are Fernet-encrypted tokens stored in the browser — zero server-side
state. Works perfectly on Vercel's stateless serverless runtime.
"""

import base64
import hashlib
import json
import os
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Optional

import httpx
from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

load_dotenv()

# ── Config ─────────────────────────────────────────────────────────────────────
# VERCEL_URL is injected automatically by Vercel (e.g. "nexus-launcher.vercel.app")
_VERCEL_HOST = os.getenv("VERCEL_URL", "")
_VERCEL_BASE = f"https://{_VERCEL_HOST}" if _VERCEL_HOST else ""

SECRET_KEY   = os.getenv("SECRET_KEY",   "please-set-a-random-secret-key-in-env")
BACKEND_URL  = os.getenv("BACKEND_URL",  _VERCEL_BASE or "http://localhost:8000")
FRONTEND_URL = os.getenv("FRONTEND_URL", _VERCEL_BASE or "http://localhost:8000")

STEAM_API_KEY = os.getenv("STEAM_API_KEY", "")

EPIC_CLIENT_ID     = os.getenv("EPIC_CLIENT_ID",     "")
EPIC_CLIENT_SECRET = os.getenv("EPIC_CLIENT_SECRET", "")

GOG_CLIENT_ID     = os.getenv("GOG_CLIENT_ID",     "")
GOG_CLIENT_SECRET = os.getenv("GOG_CLIENT_SECRET", "")

MS_CLIENT_ID     = os.getenv("MICROSOFT_CLIENT_ID",     "")
MS_CLIENT_SECRET = os.getenv("MICROSOFT_CLIENT_SECRET", "")

SESSION_TTL = 60 * 60 * 8  # 8 hours

# ── Stateless encrypted sessions ───────────────────────────────────────────────
# Sessions are Fernet-encrypted JSON blobs stored in the browser (localStorage).
# The server never writes to disk — works on any stateless/serverless host.

def _fernet() -> Fernet:
    """Derive a stable 32-byte Fernet key from SECRET_KEY."""
    raw_key = hashlib.sha256(SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(raw_key))


def new_session(data: dict) -> str:
    """Encrypt session data into a URL-safe string token."""
    payload = json.dumps({**data, "_exp": time.time() + SESSION_TTL})
    return _fernet().encrypt(payload.encode()).decode()


def get_session(token: str) -> dict:
    """Decrypt and validate a session token. Raises 401 on failure."""
    try:
        payload = json.loads(_fernet().decrypt(token.encode()).decode())
    except (InvalidToken, Exception):
        raise HTTPException(
            status_code=401,
            detail="Invalid session token — it may have been tampered with or is from a previous deployment. Please log in again.",
        )
    if payload.get("_exp", 0) < time.time():
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
    return payload


# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="NEXUS Game Launcher API",
    description=(
        "Unified game library API. Handles OAuth for Steam, Epic, GOG, and Xbox "
        "and returns your actual game library. No personal data is stored on disk."
    ),
    version="2.2.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _redirect_frontend(**params) -> RedirectResponse:
    return RedirectResponse(
        f"{FRONTEND_URL}?{urllib.parse.urlencode(params)}",
        status_code=302,
    )


def _require(client_id: str, platform: str, steps: list[str]):
    if not client_id:
        raise HTTPException(
            status_code=501,
            detail={
                "error": f"{platform} is not configured on this server",
                "setup_steps": steps,
            },
        )


# ──────────────────────────────────────────────────────────────────────────────
# Health
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["system"])
async def health():
    return {
        "status": "ok",
        "version": "2.2.0",
        "host": BACKEND_URL,
        "configured": {
            "steam":   bool(STEAM_API_KEY),
            "epic":    bool(EPIC_CLIENT_ID and EPIC_CLIENT_SECRET),
            "gog":     bool(GOG_CLIENT_ID  and GOG_CLIENT_SECRET),
            "xbox":    bool(MS_CLIENT_ID   and MS_CLIENT_SECRET),
        },
    }


# ──────────────────────────────────────────────────────────────────────────────
# STEAM
# ──────────────────────────────────────────────────────────────────────────────

_STEAM_OPENID = "https://steamcommunity.com/openid/login"
_STEAM_API    = "https://api.steampowered.com"
_STEAM_CDN    = "https://cdn.akamai.steamstatic.com/steam/apps"


@app.get("/auth/steam/login", tags=["steam"])
async def steam_login():
    """Kick off Steam OpenID login. No credentials needed — it's free."""
    params = {
        "openid.ns":         "http://specs.openid.net/auth/2.0",
        "openid.mode":       "checkid_setup",
        "openid.return_to":  f"{BACKEND_URL}/auth/steam/callback",
        "openid.realm":      BACKEND_URL,
        "openid.identity":   "http://specs.openid.net/auth/2.0/identifier_select",
        "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select",
    }
    return RedirectResponse(f"{_STEAM_OPENID}?{urllib.parse.urlencode(params)}")


@app.get("/auth/steam/callback", tags=["steam"])
async def steam_callback(request: Request):
    params    = dict(request.query_params)
    claimed   = params.get("openid.claimed_id", "")
    match     = re.search(r"/openid/id/(\d+)", claimed)
    if not match:
        return _redirect_frontend(auth_error="steam", reason="no_steam_id")
    steam_id = match.group(1)

    # Ask Steam to verify the login
    verify = {**params, "openid.mode": "check_authentication"}
    try:
        async with httpx.AsyncClient(timeout=12) as c:
            r = await c.post(_STEAM_OPENID, data=verify)
        if "is_valid:true" not in r.text:
            return _redirect_frontend(auth_error="steam", reason="verification_failed")
    except httpx.TimeoutException:
        return _redirect_frontend(auth_error="steam", reason="steam_timeout")

    token = new_session({"platform": "steam", "steam_id": steam_id})
    return _redirect_frontend(auth="steam", token=token, steam_id=steam_id)


@app.get("/api/games/steam", tags=["steam"])
async def get_steam_games(
    token: str = Query(..., description="Session token from /auth/steam/callback"),
    api_key: str = Query(None, description="Steam Web API key — free at steamcommunity.com/dev/apikey"),
):
    """
    Return the user's Steam game library.

    With an API key → full library via Steam Web API (public & private profiles).
    Without an API key → public profile XML fallback (profile must be set to Public).
    """
    session  = get_session(token)
    if session.get("platform") != "steam":
        raise HTTPException(400, "Not a Steam session.")

    steam_id = session["steam_id"]
    key      = api_key or STEAM_API_KEY

    if key:
        return await _steam_via_api(steam_id, key)
    return await _steam_via_xml(steam_id)


async def _steam_via_api(steam_id: str, api_key: str) -> dict:
    async with httpx.AsyncClient(timeout=25) as c:
        try:
            r = await c.get(
                f"{_STEAM_API}/IPlayerService/GetOwnedGames/v1/",
                params={
                    "key":                    api_key,
                    "steamid":                steam_id,
                    "include_appinfo":        1,
                    "include_played_free_games": 0,
                },
            )
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(e.response.status_code, f"Steam API error: {e.response.text[:300]}")
        except httpx.TimeoutException:
            raise HTTPException(504, "Steam API timed out — try again.")

    raw = r.json().get("response", {}).get("games", [])
    if not raw:
        raise HTTPException(
            403,
            detail={
                "error": "Steam library is empty or set to private.",
                "fix":   "Visit steamcommunity.com/my/edit/settings and set Game Details to Public.",
            },
        )

    return {
        "platform": "Steam",
        "steam_id": steam_id,
        "source":   "api",
        "count":    len(raw),
        "games": sorted(
            [
                {
                    "id":             g["appid"],
                    "title":          g.get("name", f"App {g['appid']}"),
                    "platform":       "Steam",
                    "playtime_hours": round(g.get("playtime_forever", 0) / 60, 1),
                    "cover_url":      f"{_STEAM_CDN}/{g['appid']}/library_600x900.jpg",
                    "banner_url":     f"{_STEAM_CDN}/{g['appid']}/header.jpg",
                    "launch_command": f"steam://run/{g['appid']}",
                    "store_url":      f"https://store.steampowered.com/app/{g['appid']}",
                }
                for g in raw
            ],
            key=lambda g: g["title"],
        ),
    }


async def _steam_via_xml(steam_id: str) -> dict:
    """Fallback: public Steam profile XML — no API key required."""
    url = f"https://steamcommunity.com/profiles/{steam_id}/games?tab=all&xml=1"
    async with httpx.AsyncClient(timeout=25, follow_redirects=True) as c:
        try:
            r = await c.get(url)
            r.raise_for_status()
        except Exception as e:
            raise HTTPException(502, f"Could not load your Steam profile: {e}")

    try:
        root = ET.fromstring(r.text)
    except ET.ParseError:
        raise HTTPException(
            403,
            detail={
                "error": "Steam profile is private or XML parsing failed.",
                "fix": (
                    "Set your Steam game list to Public at steamcommunity.com/my/edit/settings, "
                    "or provide a Steam API key (free at steamcommunity.com/dev/apikey)."
                ),
            },
        )

    games = []
    for g in root.findall(".//game"):
        app_id  = (g.findtext("appID") or "").strip()
        name    = (g.findtext("name")  or f"App {app_id}").strip()
        hours_s = (g.findtext("hoursOnRecord") or "0").replace(",", "")
        logo    = (g.findtext("logo") or "").strip()
        try:
            hours = round(float(hours_s), 1)
        except ValueError:
            hours = 0.0
        if not app_id:
            continue
        games.append({
            "id":             app_id,
            "title":          name,
            "platform":       "Steam",
            "playtime_hours": hours,
            "cover_url":      logo or f"{_STEAM_CDN}/{app_id}/capsule_231x87.jpg",
            "banner_url":     f"{_STEAM_CDN}/{app_id}/header.jpg",
            "launch_command": f"steam://run/{app_id}",
            "store_url":      f"https://store.steampowered.com/app/{app_id}",
        })

    games.sort(key=lambda g: g["title"])
    return {"platform": "Steam", "steam_id": steam_id, "source": "public_xml", "count": len(games), "games": games}


@app.get("/api/user/steam", tags=["steam"])
async def get_steam_profile(token: str = Query(...), api_key: str = Query(None)):
    session  = get_session(token)
    steam_id = session["steam_id"]
    key      = api_key or STEAM_API_KEY

    if not key:
        return {"platform": "Steam", "steam_id": steam_id, "username": f"Steam user {steam_id[-6:]}"}

    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(
            f"{_STEAM_API}/ISteamUser/GetPlayerSummaries/v2/",
            params={"key": key, "steamids": steam_id},
        )
    players = r.json().get("response", {}).get("players", [])
    if not players:
        raise HTTPException(404, "Steam profile not found or private.")
    p = players[0]
    return {
        "platform":    "Steam",
        "steam_id":    steam_id,
        "username":    p.get("personaname", ""),
        "avatar":      p.get("avatarfull",  ""),
        "profile_url": p.get("profileurl",  ""),
    }


# ──────────────────────────────────────────────────────────────────────────────
# EPIC GAMES
# ──────────────────────────────────────────────────────────────────────────────

_EPIC_AUTH    = "https://www.epicgames.com/id/authorize"
_EPIC_TOKEN   = "https://api.epicgames.dev/epic/oauth/v2/token"
_EPIC_ENTITLE = "https://api.epicgames.dev/epic/ecom/v3/platforms/EPIC/identities/{account_id}/entitlements"


@app.get("/auth/epic/login", tags=["epic"])
async def epic_login():
    _require(EPIC_CLIENT_ID, "Epic Games", [
        "1. Register at https://dev.epicgames.com/portal",
        "2. Create an Application",
        f"3. Add redirect URI: {BACKEND_URL}/auth/epic/callback",
        "4. Set EPIC_CLIENT_ID and EPIC_CLIENT_SECRET in your Vercel environment variables",
    ])
    params = {
        "client_id":     EPIC_CLIENT_ID,
        "redirect_uri":  f"{BACKEND_URL}/auth/epic/callback",
        "response_type": "code",
        "scope":         "basic_profile friends_list openid presence",
    }
    return RedirectResponse(f"{_EPIC_AUTH}?{urllib.parse.urlencode(params)}")


@app.get("/auth/epic/callback", tags=["epic"])
async def epic_callback(code: str = Query(None), error: str = Query(None)):
    if error or not code:
        return _redirect_frontend(auth_error="epic", reason=error or "no_code")

    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(
            _EPIC_TOKEN,
            data={
                "grant_type":  "authorization_code",
                "code":         code,
                "redirect_uri": f"{BACKEND_URL}/auth/epic/callback",
            },
            auth=(EPIC_CLIENT_ID, EPIC_CLIENT_SECRET),
        )
    if r.status_code != 200:
        return _redirect_frontend(auth_error="epic", reason="token_exchange_failed")

    data  = r.json()
    token = new_session({
        "platform":     "epic",
        "account_id":   data.get("account_id",  ""),
        "access_token": data.get("access_token", ""),
        "display_name": data.get("displayName",  ""),
    })
    return _redirect_frontend(auth="epic", token=token)


@app.get("/api/games/epic", tags=["epic"])
async def get_epic_games(token: str = Query(...)):
    session = get_session(token)
    if session.get("platform") != "epic":
        raise HTTPException(400, "Not an Epic session.")

    account_id   = session["account_id"]
    access_token = session["access_token"]

    async with httpx.AsyncClient(timeout=25) as c:
        r = await c.get(
            _EPIC_ENTITLE.format(account_id=account_id),
            headers={"Authorization": f"Bearer {access_token}"},
            params={"start": 0, "count": 1000},
        )
    if r.status_code == 401:
        raise HTTPException(401, "Epic session expired. Please log in again.")
    r.raise_for_status()

    raw   = r.json() if isinstance(r.json(), list) else r.json().get("data", [])
    games = [
        {
            "id":             item.get("id", ""),
            "title":          item.get("displayName") or item.get("entitlementName", "Unknown"),
            "platform":       "Epic",
            "playtime_hours": 0,
            "cover_url":      "",
            "launch_command": f"com.epicgames.launcher://apps/{item.get('catalogItemId', '')}?action=launch",
        }
        for item in raw
        if item.get("entitlementType") in ("EXECUTABLE", "AUDIENCE")
    ]
    return {
        "platform":     "Epic",
        "account_id":   account_id,
        "display_name": session.get("display_name", ""),
        "count":        len(games),
        "games":        games,
    }


# ──────────────────────────────────────────────────────────────────────────────
# GOG
# ──────────────────────────────────────────────────────────────────────────────

_GOG_AUTH    = "https://auth.gog.com/auth"
_GOG_TOKEN   = "https://auth.gog.com/token"
_GOG_LIBRARY = "https://embed.gog.com/account/getFilteredProducts"


@app.get("/auth/gog/login", tags=["gog"])
async def gog_login():
    _require(GOG_CLIENT_ID, "GOG", [
        "1. Apply at https://www.gog.com/developer",
        f"2. Set redirect URI: {BACKEND_URL}/auth/gog/callback",
        "3. Set GOG_CLIENT_ID and GOG_CLIENT_SECRET in your Vercel environment variables",
    ])
    params = {
        "client_id":     GOG_CLIENT_ID,
        "redirect_uri":  f"{BACKEND_URL}/auth/gog/callback",
        "response_type": "code",
        "layout":        "client2",
    }
    return RedirectResponse(f"{_GOG_AUTH}?{urllib.parse.urlencode(params)}")


@app.get("/auth/gog/callback", tags=["gog"])
async def gog_callback(code: str = Query(None), error: str = Query(None)):
    if error or not code:
        return _redirect_frontend(auth_error="gog", reason=error or "no_code")

    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(_GOG_TOKEN, data={
            "client_id":     GOG_CLIENT_ID,
            "client_secret": GOG_CLIENT_SECRET,
            "grant_type":    "authorization_code",
            "code":           code,
            "redirect_uri":   f"{BACKEND_URL}/auth/gog/callback",
        })
    if r.status_code != 200:
        return _redirect_frontend(auth_error="gog", reason="token_exchange_failed")

    data  = r.json()
    token = new_session({
        "platform":      "gog",
        "access_token":  data.get("access_token",  ""),
        "refresh_token": data.get("refresh_token", ""),
    })
    return _redirect_frontend(auth="gog", token=token)


@app.get("/api/games/gog", tags=["gog"])
async def get_gog_games(token: str = Query(...)):
    session = get_session(token)
    if session.get("platform") != "gog":
        raise HTTPException(400, "Not a GOG session.")

    access_token = session["access_token"]
    all_games, page = [], 1

    async with httpx.AsyncClient(timeout=25) as c:
        while True:
            r = await c.get(
                _GOG_LIBRARY,
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
                    "playtime_hours": 0,
                    "cover_url":      f"https:{img}_392.jpg" if img else "",
                    "launch_command": f"goggalaxy://openGameView/{p['id']}",
                    "store_url":      f"https://www.gog.com{p.get('url', '')}",
                })

            if page >= data.get("totalPages", 1):
                break
            page += 1

    return {"platform": "GOG", "count": len(all_games), "games": all_games}


# ──────────────────────────────────────────────────────────────────────────────
# XBOX
# ──────────────────────────────────────────────────────────────────────────────

_MS_AUTH   = "https://login.microsoftonline.com/consumers/oauth2/v2.0"
_XBL_AUTH  = "https://user.auth.xboxlive.com/user/authenticate"
_XBL_XSTS  = "https://xsts.auth.xboxlive.com/xsts/authorize"
_TITLE_HUB = "https://titlehub.xboxlive.com/users/xuid({xuid})/titles/titlehistory/decoration/Image,detail"


@app.get("/auth/xbox/login", tags=["xbox"])
async def xbox_login():
    _require(MS_CLIENT_ID, "Xbox", [
        "1. Register at https://portal.azure.com → App registrations → New registration",
        "2. Add API permission: XboxLive.signin (Microsoft Graph → Delegated)",
        f"3. Add redirect URI: {BACKEND_URL}/auth/xbox/callback  (type: Web)",
        "4. Set MICROSOFT_CLIENT_ID and MICROSOFT_CLIENT_SECRET in Vercel environment variables",
    ])
    params = {
        "client_id":     MS_CLIENT_ID,
        "redirect_uri":  f"{BACKEND_URL}/auth/xbox/callback",
        "response_type": "code",
        "scope":         "XboxLive.signin XboxLive.offline_access",
        "response_mode": "query",
    }
    return RedirectResponse(f"{_MS_AUTH}/authorize?{urllib.parse.urlencode(params)}")


@app.get("/auth/xbox/callback", tags=["xbox"])
async def xbox_callback(code: str = Query(None), error: str = Query(None)):
    if error or not code:
        return _redirect_frontend(auth_error="xbox", reason=error or "no_code")

    # 1 — Microsoft auth code → access token
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(f"{_MS_AUTH}/token", data={
            "client_id":     MS_CLIENT_ID,
            "client_secret": MS_CLIENT_SECRET,
            "grant_type":    "authorization_code",
            "code":           code,
            "redirect_uri":   f"{BACKEND_URL}/auth/xbox/callback",
            "scope":          "XboxLive.signin XboxLive.offline_access",
        })
    if r.status_code != 200:
        return _redirect_frontend(auth_error="xbox", reason="ms_token_failed")
    ms_token = r.json().get("access_token", "")

    # 2 — Microsoft token → Xbox Live token
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(
            _XBL_AUTH,
            json={
                "Properties": {
                    "AuthMethod": "RPS",
                    "SiteName":   "user.auth.xboxlive.com",
                    "RpsTicket":  f"d={ms_token}",
                },
                "RelyingParty": "http://auth.xboxlive.com",
                "TokenType":    "JWT",
            },
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
    if r.status_code != 200:
        return _redirect_frontend(auth_error="xbox", reason="xbl_failed")
    xbl       = r.json()
    xbl_token = xbl["Token"]
    user_hash = xbl["DisplayClaims"]["xui"][0]["uhs"]

    # 3 — Xbox Live token → XSTS token
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(
            _XBL_XSTS,
            json={
                "Properties": {"SandboxId": "RETAIL", "UserTokens": [xbl_token]},
                "RelyingParty": "http://xboxlive.com",
                "TokenType":    "JWT",
            },
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
    if r.status_code != 200:
        return _redirect_frontend(auth_error="xbox", reason="xsts_failed")
    xsts = r.json()
    xui  = xsts["DisplayClaims"]["xui"][0]

    token = new_session({
        "platform":   "xbox",
        "xuid":        xui.get("xid",  ""),
        "xsts_token":  xsts["Token"],
        "user_hash":   user_hash,
        "gamertag":    xui.get("gtg",  ""),
    })
    return _redirect_frontend(auth="xbox", token=token)


@app.get("/api/games/xbox", tags=["xbox"])
async def get_xbox_games(token: str = Query(...)):
    session = get_session(token)
    if session.get("platform") != "xbox":
        raise HTTPException(400, "Not an Xbox session.")

    xuid       = session["xuid"]
    xsts_token = session["xsts_token"]
    user_hash  = session["user_hash"]

    async with httpx.AsyncClient(timeout=25) as c:
        r = await c.get(
            _TITLE_HUB.format(xuid=xuid),
            headers={
                "Authorization":           f"XBL3.0 x={user_hash};{xsts_token}",
                "x-xbl-contract-version": "2",
                "Accept-Language":         "en-US",
            },
        )
    if r.status_code == 401:
        raise HTTPException(401, "Xbox session expired. Please log in again.")
    r.raise_for_status()

    titles = r.json().get("titles", [])
    games  = []
    for t in titles:
        imgs  = t.get("imageList") or t.get("images", [])
        cover = next(
            (i.get("url") for i in imgs if i.get("purpose") in ("BrandedKeyArt", "BoxArt")),
            "",
        )
        games.append({
            "id":             t.get("titleId", ""),
            "title":          t.get("name",    "Unknown"),
            "platform":       "Xbox",
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


# ──────────────────────────────────────────────────────────────────────────────
# EA — no public API
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/auth/ea/login", tags=["ea"])
async def ea_login():
    raise HTTPException(
        501,
        detail={
            "error":  "EA / EA App does not have a public game library API.",
            "reason": "EA has not released third-party developer access for game library data.",
        },
    )


# ──────────────────────────────────────────────────────────────────────────────
# Combined library — all connected platforms in one call
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/api/games", tags=["library"])
async def get_all_games(
    steam_token:  Optional[str] = Query(None),
    steam_apikey: Optional[str] = Query(None),
    epic_token:   Optional[str] = Query(None),
    gog_token:    Optional[str] = Query(None),
    xbox_token:   Optional[str] = Query(None),
):
    """Aggregate the game libraries of all connected platforms."""
    all_games: list = []
    errors:    list = []

    async def _try(coro, platform: str):
        try:
            result = await coro
            all_games.extend(result.get("games", []))
        except Exception as e:
            errors.append({"platform": platform, "error": str(e)})

    if steam_token:
        await _try(get_steam_games(steam_token, steam_apikey), "Steam")
    if epic_token:
        await _try(get_epic_games(epic_token), "Epic")
    if gog_token:
        await _try(get_gog_games(gog_token), "GOG")
    if xbox_token:
        await _try(get_xbox_games(xbox_token), "Xbox")

    return {"total": len(all_games), "games": all_games, "errors": errors}
