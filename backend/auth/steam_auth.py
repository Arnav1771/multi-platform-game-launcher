from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import RedirectResponse
from urllib.parse import urlencode
import os
import logging
import aiohttp
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from database import SessionLocal
from models import User
from utils.security import create_access_token
from datetime import timedelta

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# Steam OpenID configuration
STEAM_API_KEY = os.getenv("STEAM_API_KEY")
STEAM_RETURN_URL = os.getenv("STEAM_RETURN_URL", "http://localhost:8000/auth/steam/callback")
STEAM_OPENID_URL = "https://steamcommunity.com/openid/login"

async def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/auth/steam/login")
async def steam_login():
    """Initiates the Steam OpenID login process."""
    params = {
        "openid.ns": "http://specs.openid.net/auth/2.0",
        "openid.mode": "checkid_setup",
        "openid.return_to": STEAM_RETURN_URL,
        "openid.realm": os.getenv("STEAM_REALM", "http://localhost:8000"),
        "openid.identity": "http://specs.openid.net/auth/2.0/identifier_select",
        "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select",
    }
    query_string = urlencode(params)
    login_url = f"{STEAM_OPENID_URL}?{query_string}"
    return RedirectResponse(url=login_url)

@router.get("/auth/steam/callback")
async def steam_callback(request: Request, db: Session = Depends(get_db)):
    """Handles the Steam OpenID callback and user authentication."""
    if not STEAM_API_KEY:
        logger.error("STEAM_API_KEY is not set. Cannot authenticate with Steam.")
        raise HTTPException(status_code=500, detail="Steam API key not configured.")

    openid_response = request.query_params

    # Verify the OpenID response
    params = {
        "openid.ns": "http://specs.openid.net/auth/2.0",
        "openid.assoc_handle": openid_response.get("openid.assoc_handle"),
        "openid.signed": openid_response.get("openid.signed"),
        "openid.sig": openid_response.get("openid.sig"),
        "openid.ns": "http://specs.openid.net/auth/2.0",
        "openid.mode": "check_authentication",
        "openid.op_endpoint": openid_response.get("openid.op_endpoint"),
        "openid.claimed_id": openid_response.get("openid.claimed_id"),
        "openid.identity": openid_response.get("openid.identity"),
        "openid.return_to": openid_response.get("openid.return_to"),
        "openid.response_nonce": openid_response.get("openid.response_nonce"),
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(STEAM_OPENID_URL, data=params) as response:
                if response.status != 200:
                    logger.error(f"Steam OpenID verification failed with status: {response.status}")
                    raise HTTPException(status_code=500, detail="Steam OpenID verification failed.")
                
                verification_text = await response.text()
                if "is_valid:true" not in verification_text:
                    logger.error(f"Steam OpenID verification returned invalid: {verification_text}")
                    raise HTTPException(status_code=401, detail="Steam OpenID verification failed.")

        except aiohttp.ClientError as e:
            logger.error(f"Network error during Steam OpenID verification: {e}")
            raise HTTPException(status_code=500, detail="Error communicating with Steam.")

    # Extract Steam ID
    claimed_id = openid_response.get("openid.claimed_id")
    if not claimed_id:
        logger.error("Missing openid.claimed_id in Steam callback.")
        raise HTTPException(status_code=400, detail="Invalid Steam callback data.")

    try:
        # Steam ID is usually in the format: https://steamcommunity.com/openid/id/<STEAM_ID>
        steam_id = claimed_id.split("/")[-1]
        if not steam_id.isdigit():
            raise ValueError("Steam ID is not a valid number.")
    except (IndexError, ValueError) as e:
        logger.error(f"Could not parse Steam ID from claimed_id: {claimed_id}. Error: {e}")
        raise HTTPException(status_code=400, detail="Could not parse Steam ID.")

    # Check if user exists or create new user
    user = db.query(User).filter(User.steam_id == steam_id).first()

    if not user:
        # Fetch user profile from Steam API (optional, but good for getting display name)
        user_profile_url = f"https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v1/?key={STEAM_API_KEY}&steamids={steam_id}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(user_profile_url) as profile_response:
                    if profile_response.status == 200:
                        profile_data = await profile_response.json()
                        if profile_data and "response" in profile_data and "players" in profile_data["response"]:
                            player_info = profile_data["response"]["players"][0]
                            user = User(
                                steam_id=steam_id,
                                username=player_info.get("personaname", f"SteamUser_{steam_id}"),
                                avatar_url=player_info.get("avatarmedium"),
                            )
                            db.add(user)
                            db.commit()
                            db.refresh(user)
                            logger.info(f"New user created with Steam ID: {steam_id}")
                        else:
                            logger.warning(f"Could not fetch Steam profile for new user {steam_id}. Creating with default username.")
                            user = User(
                                steam_id=steam_id,
                                username=f"SteamUser_{steam_id}",
                            )
                            db.add(user)
                            db.commit()
                            db.refresh(user)
                    else:
                        logger.warning(f"Failed to fetch Steam profile for new user {steam_id} (status: {profile_response.status}). Creating with default username.")
                        user = User(
                            steam_id=steam_id,
                            username=f"SteamUser_{steam_id}",
                        )
                        db.add(user)
                        db.commit()
                        db.refresh(user)
        except aiohttp.ClientError as e:
            logger.error(f"Network error fetching Steam profile for {steam_id}: {e}. Creating with default username.")
            user = User(
                steam_id=steam_id,
                username=f"SteamUser_{steam_id}",
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        except Exception as e:
            logger.error(f"Unexpected error fetching Steam profile for {steam_id}: {e}. Creating with default username.")
            user = User(
                steam_id=steam_id,
                username=f"SteamUser_{steam_id}",
            )
            db.add(user)
            db.commit()
            db.refresh(user)

    # Generate JWT token
    access_token_expires = timedelta(minutes=30) # Token expires in 30 minutes
    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username, "steam_id": user.steam_id},
        expires_delta=access_token_expires
    )

    # Redirect to frontend with token
    # Assuming frontend is running on a different port and handles token storage
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    response = RedirectResponse(url=f"{frontend_url}/auth/callback?token={access_token}")
    return response
```