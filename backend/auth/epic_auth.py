```python
import os
import logging
import requests
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from starlette import status
from urllib.parse import urlencode

from backend.database import get_db
from backend.models.user import User
from backend.schemas.user import UserCreate
from backend.utils.auth import create_access_token, create_refresh_token, verify_token
from backend.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

EPIC_CLIENT_ID = os.environ.get("EPIC_CLIENT_ID")
EPIC_CLIENT_SECRET = os.environ.get("EPIC_CLIENT_SECRET")
EPIC_REDIRECT_URI = os.environ.get("EPIC_REDIRECT_URI", "http://localhost:8000/auth/epic/callback")
EPIC_AUTH_URL = "https://www.epicgames.com/id/oauth2/authorize"
EPIC_TOKEN_URL = "https://api.epicgames.dev/epic/oauth/v1/token"
EPIC_USERINFO_URL = "https://api.epicgames.dev/epic/user/v1/accounts/me"

if not all([EPIC_CLIENT_ID, EPIC_CLIENT_SECRET]):
    logger.warning("EPIC_CLIENT_ID or EPIC_CLIENT_SECRET not set. Epic Games OAuth will not function.")

@router.get("/login/epic")
async def epic_login():
    """Initiates the Epic Games OAuth2 login flow."""
    if not all([EPIC_CLIENT_ID, EPIC_CLIENT_SECRET]):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Epic Games OAuth is not configured.",
        )

    params = {
        "client_id": EPIC_CLIENT_ID,
        "redirect_uri": EPIC_REDIRECT_URI,
        "response_type": "code",
        "scope": "basic_profile openid",
    }
    auth_url = f"{EPIC_AUTH_URL}?{urlencode(params)}"
    return RedirectResponse(auth_url, status_code=status.HTTP_302_FOUND)

@router.get("/auth/epic/callback")
async def epic_callback(code: str, db: Session = Depends(get_db)):
    """Handles the callback from Epic Games after user authorization."""
    if not all([EPIC_CLIENT_ID, EPIC_CLIENT_SECRET]):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Epic Games OAuth is not configured.",
        )

    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": EPIC_CLIENT_ID,
        "client_secret": EPIC_CLIENT_SECRET,
        "redirect_uri": EPIC_REDIRECT_URI,
    }

    try:
        response = requests.post(EPIC_TOKEN_URL, data=token_data)
        response.raise_for_status()
        token_info = response.json()
        access_token = token_info.get("access_token")
        id_token = token_info.get("id_token") # Although not strictly required by Epic's docs for userinfo, it's good practice to handle it.

        if not access_token:
            logger.error(f"Failed to retrieve access token from Epic Games: {response.text}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to obtain access token from Epic Games.",
            )

        # Fetch user info using the access token
        headers = {"Authorization": f"Bearer {access_token}"}
        user_info_response = requests.get(EPIC_USERINFO_URL, headers=headers)
        user_info_response.raise_for_status()
        user_info = user_info_response.json()

        epic_user_id = user_info.get("id")
        display_name = user_info.get("displayName")
        email = user_info.get("email") # Email might not always be available depending on scopes and user consent

        if not epic_user_id:
            logger.error(f"Could not retrieve Epic User ID from user info: {user_info}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not retrieve Epic User ID.",
            )

        # Check if user exists, create if not
        user = db.query(User).filter(User.epic_id == epic_user_id).first()

        if not user:
            logger.info(f"Epic user not found, creating new user for Epic ID: {epic_user_id}")
            new_user_data = UserCreate(
                epic_id=epic_user_id,
                username=display_name or f"epic_user_{epic_user_id[:8]}",
                email=email,
                hashed_password=None # Epic users authenticate via OAuth, no password needed
            )
            user = User(**new_user_data.dict())
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info(f"New user created with ID: {user.id}")
        else:
            logger.info(f"Epic user found: {user.id} (Epic ID: {epic_user_id})")
            # Optionally update user details if they change on Epic's side
            if user.username != display_name or user.email != email:
                user.username = display_name or user.username
                user.email = email or user.email
                db.commit()
                db.refresh(user)
                logger.info(f"Updated user {user.id} details.")

        # Generate JWT tokens
        access_token_jwt = create_access_token(subject=str(user.id), provider="epic")
        refresh_token_jwt = create_refresh_token(subject=str(user.id), provider="epic")

        # Set tokens in cookies for the frontend
        response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        response.set_cookie(key="access_token", value=access_token_jwt, httponly=True, secure=settings.HTTPS_ONLY, samesite="lax")
        response.set_cookie(key="refresh_token", value=refresh_token_jwt, httponly=True, secure=settings.HTTPS_ONLY, samesite="lax")

        return response

    except requests.exceptions.RequestException as e:
        logger.error(f"Error during Epic Games OAuth request: {e}")
        if e.response is not None:
            logger.error(f"Epic Games API response: {e.response.text}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error communicating with Epic Games API: {e}",
        )
    except Exception as e:
        logger.exception(f"An unexpected error occurred during Epic Games callback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during authentication.",
        )

@router.get("/refresh_epic_token")
async def refresh_epic_token(request: Request, db: Session = Depends(get_db)):
    """
    This endpoint is a placeholder.
    In a real application, you would handle token refresh logic here.
    Epic Games' token refresh mechanism might require using the refresh token
    obtained during the initial authorization flow.
    """
    # This is a simplified example. A full implementation would involve:
    # 1. Getting the refresh token from cookies or a secure store.
    # 2. Making a POST request to EPIC_TOKEN_URL with grant_type='refresh_token'
    #    and the refresh token.
    # 3. Updating the user's session or issuing new JWTs upon successful refresh.
    # 4. Handling potential errors like expired refresh tokens.

    # For now, we'll just raise a NotImplementedError or return a message.
    logger.warning("Epic Games token refresh endpoint called but not fully implemented.")
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Epic Games token refresh is not yet implemented.",
    )

# Example of how you might protect a route using Epic authentication
# This requires a valid JWT access token with 'provider=epic' in the payload.
@router.get("/profile/epic")
async def get_epic_profile(current_user: User = Depends(verify_token)):
    """
    Example endpoint protected by Epic Games authentication.
    Requires a valid JWT access token issued for an Epic Games authenticated user.
    """
    if current_user.epic_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This profile is only accessible via Epic Games authentication.",
        )

    return {
        "message": f"Welcome, {current_user.username}! You are authenticated via Epic Games.",
        "user_id": current_user.id,
        "epic_id": current_user.epic_id,
        "username": current_user.username,
        "email": current_user.email
    }
```