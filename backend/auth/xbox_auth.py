```python
import os
import logging
import requests
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from dotenv import load_dotenv
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

XBOX_CLIENT_ID = os.getenv("XBOX_CLIENT_ID")
XBOX_CLIENT_SECRET = os.getenv("XBOX_CLIENT_SECRET")
XBOX_REDIRECT_URI = os.getenv("XBOX_REDIRECT_URI")

if not all([XBOX_CLIENT_ID, XBOX_CLIENT_SECRET, XBOX_REDIRECT_URI]):
    logger.error("XBOX_CLIENT_ID, XBOX_CLIENT_SECRET, and XBOX_REDIRECT_URI must be set in environment variables.")
    # In a real application, you might want to raise an exception or exit here
    # For this example, we'll allow it to proceed but it will fail later.

XBOX_AUTH_URL = "https://login.live.com/oauth20_authorize.srf"
XBOX_TOKEN_URL = "https://login.live.com/oauth20_token.srf"
XBOX_USER_INFO_URL = "https://graph.microsoft.com/v1.0/me" # Using Microsoft Graph API for user info

router = APIRouter()

class XboxAuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str
    user_id: str
    display_name: Optional[str] = None
    email: Optional[str] = None

class XboxTokenRequest(BaseModel):
    code: str

@router.get("/xbox/login")
async def xbox_login():
    """
    Initiates the Xbox OAuth 2.0 flow by redirecting the user to the Xbox login page.
    """
    if not all([XBOX_CLIENT_ID, XBOX_REDIRECT_URI]):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Xbox authentication is not configured properly. Please check server configuration."
        )

    params = {
        "client_id": XBOX_CLIENT_ID,
        "response_type": "code",
        "scope": "XboxLive.signin offline_access", # Requesting sign-in and offline access
        "redirect_uri": XBOX_REDIRECT_URI,
        "prompt": "select_account" # Ensures user is prompted to select an account
    }
    auth_url = f"{XBOX_AUTH_URL}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
    return {"redirect_url": auth_url}

@router.post("/xbox/token", response_model=XboxAuthResponse)
async def xbox_token(request: XboxTokenRequest):
    """
    Exchanges the authorization code received from Xbox for an access token and refresh token.
    Also fetches basic user information.
    """
    if not all([XBOX_CLIENT_ID, XBOX_CLIENT_SECRET, XBOX_REDIRECT_URI]):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Xbox authentication is not configured properly. Please check server configuration."
        )

    data = {
        "grant_type": "authorization_code",
        "code": request.code,
        "redirect_uri": XBOX_REDIRECT_URI,
        "client_id": XBOX_CLIENT_ID,
        "client_secret": XBOX_CLIENT_SECRET,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    try:
        token_response = requests.post(XBOX_TOKEN_URL, data=data, headers=headers)
        token_response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        token_data = token_response.json()

        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in")
        token_type = token_data.get("token_type", "Bearer")

        if not access_token:
            logger.error(f"Failed to obtain access token from Xbox: {token_response.text}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to obtain access token from Xbox."
            )

        # Fetch user info using the obtained access token
        user_info_headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        user_info_response = requests.get(XBOX_USER_INFO_URL, headers=user_info_headers)
        user_info_response.raise_for_status()
        user_info = user_info_response.json()

        user_id = user_info.get("id") # Microsoft Graph ID is a good unique identifier
        display_name = user_info.get("displayName")
        email = user_info.get("userPrincipalName") # Often used as email

        if not user_id:
            logger.error(f"Failed to retrieve user ID from Microsoft Graph API: {user_info}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to retrieve user information from Xbox."
            )

        return XboxAuthResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            token_type=token_type,
            user_id=user_id,
            display_name=display_name,
            email=email
        )

    except requests.exceptions.RequestException as e:
        logger.error(f"Error during Xbox token exchange or user info retrieval: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Xbox API response: {e.response.text}")
            error_detail = f"Xbox API error: {e.response.status_code} - {e.response.text}"
        else:
            error_detail = "Network or connection error with Xbox API."
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail
        )
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected internal server error occurred during Xbox authentication."
        )

# Note: In a production environment, you would typically:
# 1. Store refresh tokens securely (e.g., in a database associated with user accounts).
# 2. Implement logic to use refresh tokens to obtain new access tokens when they expire.
# 3. Handle token revocation and error scenarios more robustly.
# 4. Integrate with your user management system (e.g., SQLAlchemy models for users).
```