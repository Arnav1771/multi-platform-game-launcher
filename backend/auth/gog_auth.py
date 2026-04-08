```python
import os
import logging
import httpx
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from backend.database import SessionLocal
from backend.config import settings
from backend.auth.utils import (
    create_access_token,
    create_refresh_token,
    get_user_by_email,
    create_user,
    UserCreateSchema,
    UserSchema,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# GOG OAuth2 Configuration
GOG_CLIENT_ID = os.environ.get("GOG_CLIENT_ID")
GOG_CLIENT_SECRET = os.environ.get("GOG_CLIENT_SECRET")
GOG_REDIRECT_URI = os.environ.get("GOG_REDIRECT_URI", "http://localhost:8000/auth/gog/callback")
GOG_AUTH_URL = "https://auth.gog.com/oauth2/authorize"
GOG_TOKEN_URL = "https://auth.gog.com/oauth2/token"
GOG_USERINFO_URL = "https://api.gog.com/user/v1/me"

if not all([GOG_CLIENT_ID, GOG_CLIENT_SECRET]):
    logger.warning("GOG_CLIENT_ID or GOG_CLIENT_SECRET not set. GOG OAuth will not be available.")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class GogUserInfo(BaseModel):
    id: str
    email: str
    username: Optional[str] = None
    public: Optional[bool] = None
    links: Optional[dict] = None


@router.get("/auth/gog/login")
async def gog_login():
    """Initiates the GOG OAuth2 login flow."""
    if not all([GOG_CLIENT_ID, GOG_CLIENT_SECRET]):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GOG OAuth is not configured.",
        )

    params = {
        "client_id": GOG_CLIENT_ID,
        "redirect_uri": GOG_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",  # Requesting basic user info
    }
    auth_url = httpx.URL(GOG_AUTH_URL)
    auth_url = auth_url.copy_with(params=params)
    return RedirectResponse(url=str(auth_url))


@router.get("/auth/gog/callback")
async def gog_callback(code: str, db: Session = Depends(get_db)):
    """Handles the callback from GOG after user authorization."""
    if not all([GOG_CLIENT_ID, GOG_CLIENT_SECRET]):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GOG OAuth is not configured.",
        )

    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": GOG_REDIRECT_URI,
        "client_id": GOG_CLIENT_ID,
        "client_secret": GOG_CLIENT_SECRET,
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(GOG_TOKEN_URL, data=token_data)
            response.raise_for_status()  # Raise an exception for bad status codes
            token_response = response.json()
            access_token = token_response.get("access_token")
            id_token = token_response.get("id_token") # GOG might return an id_token

            if not access_token:
                logger.error(f"GOG OAuth callback failed: No access token received. Response: {token_response}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to obtain access token from GOG.",
                )

        # Fetch user info using the access token
        headers = {"Authorization": f"Bearer {access_token}"}
        async with httpx.AsyncClient() as client:
            user_info_response = await client.get(GOG_USERINFO_URL, headers=headers)
            user_info_response.raise_for_status()
            user_info = GogUserInfo(**user_info_response.json())

    except httpx.HTTPStatusError as e:
        logger.error(f"GOG OAuth HTTP error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error communicating with GOG API: {e.response.text}",
        )
    except httpx.RequestError as e:
        logger.error(f"GOG OAuth request error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not connect to GOG API: {e}",
        )
    except Exception as e:
        logger.error(f"An unexpected error occurred during GOG callback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during GOG authentication.",
        )

    # Find or create user in our database
    user = get_user_by_email(db, user_info.email)
    if not user:
        # GOG might not provide a username, use email as fallback
        username = user_info.username if user_info.username else user_info.email
        try:
            user_create_data = UserCreateSchema(
                email=user_info.email,
                username=username,
                hashed_password="", # No password for OAuth users
                is_oauth_user=True,
                oauth_provider="gog",
                oauth_id=user_info.id,
            )
            user = create_user(db, user_create_data)
            logger.info(f"New GOG user created: {user.email}")
        except Exception as e:
            logger.error(f"Failed to create GOG user in DB: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user account.",
            )
    elif not user.is_oauth_user or user.oauth_provider != "gog" or user.oauth_id != user_info.id:
         # If user exists but is not a GOG OAuth user or linked to a different GOG account
         # This scenario might require more complex handling, e.g., prompting the user to link accounts.
         # For simplicity here, we'll assume it's an error or requires manual intervention.
         logger.warning(f"User {user.email} exists but is not linked to this GOG account or is not an OAuth user.")
         # Option 1: Treat as error
         # raise HTTPException(
         #     status_code=status.HTTP_409_CONFLICT,
         #     detail="This email is already registered with a different authentication method or GOG account.",
         # )
         # Option 2: Update existing user if they are not an OAuth user, or link if they are a different OAuth provider
         if not user.is_oauth_user:
             user.is_oauth_user = True
             user.oauth_provider = "gog"
             user.oauth_id = user_info.id
             db.commit()
             db.refresh(user)
             logger.info(f"Updated existing user {user.email} to be a GOG OAuth user.")
         else:
              raise HTTPException(
                 status_code=status.HTTP_409_CONFLICT,
                 detail="This email is already linked to another OAuth provider or GOG account.",
             )


    # Generate JWT tokens
    access_token = create_access_token(data={"sub": user.email})
    refresh_token = create_refresh_token(data={"sub": user.email})

    # Redirect to the frontend with tokens (or set cookies)
    # This is a common pattern, but consider security implications (e.g., XSS)
    # A more secure approach might involve setting HttpOnly cookies.
    frontend_url = settings.FRONTEND_URL or "http://localhost:3000"
    response = RedirectResponse(
        url=f"{frontend_url}/auth/callback?access_token={access_token}&refresh_token={refresh_token}&provider=gog"
    )
    # Example of setting HttpOnly cookies (more secure)
    # response.set_cookie("access_token", access_token, httponly=True, samesite="lax", secure=settings.HTTPS_ENABLED)
    # response.set_cookie("refresh_token", refresh_token, httponly=True, samesite="lax", secure=settings.HTTPS_ENABLED)

    return response
```