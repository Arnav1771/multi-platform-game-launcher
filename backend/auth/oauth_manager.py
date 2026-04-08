```python
import os
import logging
from typing import Dict, Any, Optional
from urllib.parse import urlencode

import httpx
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.status import HTTP_302_FOUND

from backend.config import settings
from backend.database.session import AsyncSession
from backend.exceptions import OAuthError
from backend.models.user import User
from backend.schemas.oauth import OAuthTokenResponse, OAuthUserInfoResponse

# Configure logging
logger = logging.getLogger(__name__)

class OAuthManager:
    """
    Base class for OAuth2 managers.
    Handles the core logic of the OAuth2 authorization code grant flow.
    """
    def __init__(self,
                 client_id: str,
                 client_secret: str,
                 authorize_url: str,
                 token_url: str,
                 userinfo_url: str,
                 redirect_uri: str,
                 scopes: list[str],
                 provider_name: str):
        """
        Initializes the OAuthManager.

        Args:
            client_id: The client ID obtained from the OAuth provider.
            client_secret: The client secret obtained from the OAuth provider.
            authorize_url: The URL for initiating the authorization request.
            token_url: The URL for exchanging the authorization code for an access token.
            userinfo_url: The URL for fetching user information using the access token.
            redirect_uri: The callback URL registered with the OAuth provider.
            scopes: A list of requested scopes.
            provider_name: The name of the OAuth provider (e.g., "google", "epic").
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.authorize_url = authorize_url
        self.token_url = token_url
        self.userinfo_url = userinfo_url
        self.redirect_uri = redirect_uri
        self.scopes = scopes
        self.provider_name = provider_name

    def get_authorization_url(self, state: str) -> str:
        """
        Constructs the authorization URL to redirect the user to the OAuth provider.

        Args:
            state: A unique, opaque value used to maintain state between the request
                   and the callback. It is recommended to use a cryptographically
                   secure random string.

        Returns:
            The full authorization URL.
        """
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(self.scopes),
            "state": state,
        }
        return f"{self.authorize_url}?{urlencode(params)}"

    async def get_access_token(self, code: str, state: str) -> OAuthTokenResponse:
        """
        Exchanges the authorization code for an access token and refresh token.

        Args:
            code: The authorization code received from the OAuth provider.
            state: The state parameter received from the OAuth provider, used for verification.

        Returns:
            An OAuthTokenResponse object containing the access token, token type,
            expires in, refresh token, and scope.

        Raises:
            OAuthError: If the token exchange fails or if the state parameter is invalid.
        """
        if not self.client_id or not self.client_secret:
            logger.error(f"OAuth client ID or secret not configured for {self.provider_name}.")
            raise OAuthError(f"OAuth client ID or secret not configured for {self.provider_name}.")

        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.token_url, data=token_data)
                response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

            token_info = response.json()
            logger.info(f"Successfully obtained access token for {self.provider_name}.")
            return OAuthTokenResponse(**token_info)

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred during token exchange for {self.provider_name}: {e.response.status_code} - {e.response.text}")
            raise OAuthError(f"Failed to exchange authorization code for access token: {e.response.text}")
        except httpx.RequestError as e:
            logger.error(f"Network error occurred during token exchange for {self.provider_name}: {e}")
            raise OAuthError(f"Network error during token exchange: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during token exchange for {self.provider_name}: {e}")
            raise OAuthError(f"An unexpected error occurred during token exchange: {e}")

    async def get_user_info(self, access_token: str) -> OAuthUserInfoResponse:
        """
        Fetches user information from the OAuth provider using the access token.

        Args:
            access_token: The access token obtained from the OAuth provider.

        Returns:
            An OAuthUserInfoResponse object containing user details.

        Raises:
            OAuthError: If fetching user info fails.
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.userinfo_url, headers=headers)
                response.raise_for_status()

            user_info = response.json()
            logger.info(f"Successfully fetched user info from {self.provider_name}.")
            return OAuthUserInfoResponse(**user_info)

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred fetching user info from {self.provider_name}: {e.response.status_code} - {e.response.text}")
            raise OAuthError(f"Failed to fetch user info: {e.response.text}")
        except httpx.RequestError as e:
            logger.error(f"Network error occurred fetching user info from {self.provider_name}: {e}")
            raise OAuthError(f"Network error fetching user info: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred fetching user info from {self.provider_name}: {e}")
            raise OAuthError(f"An unexpected error occurred fetching user info: {e}")

    async def process_callback(self, request: Request, db: AsyncSession) -> User:
        """
        Processes the callback from the OAuth provider after user authorization.
        This method should be implemented by subclasses to handle provider-specific logic.

        Args:
            request: The incoming FastAPI request object.
            db: The asynchronous database session.

        Returns:
            The authenticated User object.

        Raises:
            OAuthError: If the callback processing fails.
        """
        raise NotImplementedError("Subclasses must implement this method.")

class GoogleOAuthManager(OAuthManager):
    """
    OAuth2 manager implementation for Google.
    """
    def __init__(self):
        super().__init__(
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            userinfo_url="https://www.googleapis.com/oauth2/v3/userinfo",
            redirect_uri=f"{settings.APP_URL}/auth/google/callback",
            scopes=["openid", "email", "profile"],
            provider_name="google"
        )

    async def process_callback(self, request: Request, db: AsyncSession) -> User:
        """
        Processes the callback from Google after user authorization.
        Fetches user info and creates or retrieves the user in the database.
        """
        form = await request.form()
        code = form.get("code")
        state = form.get("state")
        error = form.get("error")

        if error:
            error_description = form.get("error_description", "No description provided.")
            logger.error(f"Google OAuth callback error: {error} - {error_description}")
            raise OAuthError(f"Google authentication failed: {error_description}")

        if not code or not state:
            logger.error("Google OAuth callback missing 'code' or 'state' parameter.")
            raise OAuthError("Invalid callback from Google.")

        # TODO: Implement state verification (e.g., compare with session state)
        # For now, we assume the state is valid. In a real application,
        # you would store the state in the user's session and compare it here.

        try:
            token_response = await self.get_access_token(code, state)
            user_info = await self.get_user_info(token_response.access_token)

            # Find or create user in the database
            user = await User.get_by_email(db, user_info.email)
            if not user:
                user = User(
                    email=user_info.email,
                    name=user_info.name,
                    provider=self.provider_name,
                    provider_id=user_info.sub,
                    access_token=token_response.access_token,
                    refresh_token=token_response.refresh_token,
                    token_expires_at=token_response.expires_at,
                )
                db.add(user)
            else:
                # Update existing user's tokens and potentially other info
                user.name = user_info.name
                user.provider = self.provider_name
                user.provider_id = user_info.sub
                user.access_token = token_response.access_token
                user.refresh_token = token_response.refresh_token
                user.token_expires_at = token_response.expires_at
                # Mark user as modified to ensure update in DB
                db.add(user)

            await db.commit()
            await db.refresh(user)
            logger.info(f"User {user.email} authenticated via Google.")
            return user

        except OAuthError as e:
            logger.error(f"OAuth error during Google callback processing: {e}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error during Google callback processing: {e}")
            raise OAuthError(f"An unexpected error occurred during Google authentication: {e}")


class EpicGamesOAuthManager(OAuthManager):
    """
    OAuth2 manager implementation for Epic Games.
    """
    def __init__(self):
        super().__init__(
            client_id=settings.EPIC_CLIENT_ID,
            client_secret=settings.EPIC_CLIENT_SECRET,
            authorize_url="https://www.epicgames.com/id/oauth2/v1/authorize",
            token_url="https://www.epicgames.com/id/oauth2/token",
            userinfo_url="https://api.epicgames.dev/epic/member/v1/profile/basic", # Example, actual endpoint might differ
            redirect_uri=f"{settings.APP_URL}/auth/epic/callback",
            scopes=["basic_profile", "email"], # Scopes might need adjustment based on Epic's API
            provider_name="epic"
        )

    async def get_access_token(self, code: str, state: str) -> OAuthTokenResponse:
        """
        Exchanges the authorization code for an access token and refresh token for Epic Games.
        Epic Games uses 'client_credentials' grant type for some token exchanges,
        but for user authorization, 'authorization_code' is typical.
        This implementation assumes the standard authorization code flow.
        """
        if not self.client_id or not self.client_secret:
            logger.error(f"Epic Games OAuth client ID or secret not configured.")
            raise OAuthError("Epic Games OAuth client ID or secret not configured.")

        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.token_url, data=token_data)
                response.raise_for_status()

            token_info = response.json()
            logger.info(f"Successfully obtained Epic Games access token.")
            return OAuthTokenResponse(**token_info)

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error during Epic Games token exchange: {e.response.status_code} - {e.response.text}")
            raise OAuthError(f"Failed to exchange authorization code for Epic Games access token: {e.response.text}")
        except httpx.RequestError as e:
            logger.error(f"Network error during Epic Games token exchange: {e}")
            raise OAuthError(f"Network error during Epic Games token exchange: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during Epic Games token exchange: {e}")
            raise OAuthError(f"An unexpected error occurred during Epic Games token exchange: {e}")

    async def get_user_info(self, access_token: str) -> OAuthUserInfoResponse:
        """
        Fetches user information from Epic Games using the access token.
        Note: The exact userinfo endpoint and response structure for Epic Games
        can vary and might require specific API keys or permissions.
        This is a placeholder based on common patterns.
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            # Epic Games might require a specific client ID in headers for some API calls
            # "X-Epic-Client-ID": self.client_id,
        }

        try:
            async with httpx.AsyncClient() as client:
                # The userinfo_url might need to be adjusted based on Epic's current API documentation.
                # Sometimes, the user ID is returned in the token response and used to fetch profile.
                response = await client.get(self.userinfo_url, headers=headers)
                response.raise_for_status()

            user_info = response.json()
            logger.info(f"Successfully fetched Epic Games user info.")

            # Epic Games user info structure might be different.
            # This assumes a structure similar to Google's for demonstration.
            # You'll need to adapt this based on the actual Epic Games API response.
            # Example structure might include 'displayName', 'id', 'email' (if scope granted)
            # For now, we'll map to common fields.
            # If 'email' is not directly available, it might need a separate call or a different scope.
            return OAuthUserInfoResponse(
                sub=user_info.get("id", ""), # Epic User ID
                name=user_info.get("displayName", "Epic User"), # Display Name
                email=user_info.get("email", "") # Email might require specific scope
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching Epic Games user info: {e.response.status_code} - {e.response.text}")
            raise OAuthError(f"Failed to fetch Epic Games user info: {e.response.text}")
        except httpx.RequestError as e:
            logger.error(f"Network error fetching Epic Games user info: {e}")
            raise OAuthError(f"Network error fetching Epic Games user info: {e}")
        except Exception as e:
            logger.error(f"Unexpected error fetching Epic Games user info: {e}")
            raise OAuthError(f"An unexpected error occurred fetching Epic Games user info: {e}")

    async def process_callback(self, request: Request, db: AsyncSession) -> User:
        """
        Processes the callback from Epic Games after user authorization.
        Fetches user info and creates or retrieves the user in the database.
        """
        form = await request.form()
        code = form.get("code")
        state = form.get("state")
        error = form.get("error")

        if error:
            error_description = form.get("error_description", "No description provided.")
            logger.error(f"Epic Games OAuth callback error: {error} - {error_description}")
            raise OAuthError(f"Epic Games authentication failed: {error_description}")

        if not code or not state:
            logger.error("Epic Games OAuth callback missing 'code' or 'state' parameter.")
            raise OAuthError("Invalid callback from Epic Games.")

        # TODO: Implement state verification

        try:
            token_response = await self.get_access_token(code, state)
            user_info = await self.get_user_info(token_response.access_token)

            # Find or create user in the database
            # Use provider_id for lookup if email is not guaranteed or reliable
            user = await User.get_by_provider_id(db, self.provider_name, user_info.sub)
            if not user:
                user = User(
                    email=user_info.email or f"{user_info.sub}@{self.provider_name}.com", # Fallback email
                    name=user_info.name,
                    provider=self.provider_name,
                    provider_id=user_info.sub,
                    access_token=token_response.access_token,
                    refresh_token=token_response.refresh_token,
                    token_expires_at=token_response.expires_at,
                )
                db.add(user)
            else:
                # Update existing user's tokens and potentially other info
                user.name = user_info.name
                user.email = user_info.email or user.email # Keep existing email if new one is missing
                user.access_token = token_response.access_token
                user.refresh_token = token_response.refresh_token
                user.token_expires_at = token_response.expires_at
                db.add(user)

            await db.commit()
            await db.refresh(user)
            logger.info(f"User {user.email} authenticated via Epic Games.")
            return user

        except OAuthError as e:
            logger.error(f"OAuth error during Epic Games callback processing: {e}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error during Epic Games callback processing: {e}")
            raise OAuthError(f"An unexpected error occurred during Epic Games authentication: {e}")


class UbisoftOAuthManager(OAuthManager):
    """
    OAuth2 manager implementation for Ubisoft Connect.
    Ubisoft's OAuth flow might be more complex or require specific SDKs.
    This is a conceptual implementation based on standard OAuth2.
    """
    def __init__(self):
        # Ubisoft's specific URLs and scopes need to be confirmed from their developer docs.
        # The userinfo endpoint might be part of a broader profile API.
        super().__init__(
            client_id=settings.UBISOFT_CLIENT_ID,
            client_secret=settings.UBISOFT_CLIENT_SECRET,
            authorize_url="https://connect.ubisoft.com/oauth2/v1/authorize", # Example URL
            token_url="https://connect.ubisoft.com/oauth2/token", # Example URL
            userinfo_url="https://connect.ubisoft.com/api/v1/users/me", # Example URL
            redirect_uri=f"{settings.APP_URL}/auth/ubisoft/callback",
            scopes=["basic_profile", "email"], # Example scopes
            provider_name="ubisoft"
        )

    async def get_access_token(self, code: str, state: str) -> OAuthTokenResponse:
        """
        Exchanges the authorization code for an access token and refresh token for Ubisoft.
        """
        if not self.client_id or not self.client_secret:
            logger.error(f"Ubisoft OAuth client ID or secret not configured.")
            raise OAuthError("Ubisoft OAuth client ID or secret not configured.")

        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.token_url, data=token_data)
                response.raise_for_status()

            token_info = response.json()
            logger.info(f"Successfully obtained Ubisoft access token.")
            return OAuthTokenResponse(**token_info)

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error during Ubisoft token exchange: {e.response.status_code} - {e.response.text}")
            raise OAuthError(f"Failed to exchange authorization code for Ubisoft access token: {e.response.text}")
        except httpx.RequestError as e:
            logger.error(f"Network error during Ubisoft token exchange: {e}")
            raise OAuthError(f"Network error during Ubisoft token exchange: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during Ubisoft token exchange: {e}")
            raise OAuthError(f"An unexpected error occurred during Ubisoft token exchange: {e}")

    async def get_user_info(self, access_token: str) -> OAuthUserInfoResponse:
        """
        Fetches user information from Ubisoft using the access token.
        Requires confirmation of the correct endpoint and response structure.
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.userinfo_url, headers=headers)
                response.raise_for_status()

            user_info = response.json()
            logger.info(f"Successfully fetched Ubisoft user info.")

            # Ubisoft user info structure needs to be verified.
            # This is a placeholder mapping.
            return OAuthUserInfoResponse(
                sub=user_info.get("userId", ""), # Example Ubisoft User ID field
                name=user_info.get("displayName", "Ubisoft User"), # Example display name field
                email=user_info.get("email", "") # Example email field
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching Ubisoft user info: {e.response.status_code} - {e.response.text}")
            raise OAuthError(f"Failed to fetch Ubisoft user info: {e.response.text}")
        except httpx.RequestError as e:
            logger.error(f"Network error fetching Ubisoft user info: {e}")
            raise OAuthError(f"Network error fetching Ubisoft user info: {e}")
        except Exception as e:
            logger.error(f"Unexpected error fetching Ubisoft user info: {e}")
            raise OAuthError(f"An unexpected error occurred fetching Ubisoft user info: {e}")

    async def process_callback(self, request: Request, db: AsyncSession) -> User:
        """
        Processes the callback from Ubisoft after user authorization.
        Fetches user info and creates or retrieves the user in the database.
        """
        form = await request.form()
        code = form.get("code")
        state = form.get("state")
        error = form.get("error")

        if error:
            error_description = form.get("error_description", "No description provided.")
            logger.error(f"Ubisoft OAuth callback error: {error} - {error_description}")
            raise OAuthError(f"Ubisoft authentication failed: {error_description}")

        if not code or not state:
            logger.error("Ubisoft OAuth callback missing 'code' or 'state' parameter.")
            raise OAuthError("Invalid callback from Ubisoft.")

        # TODO: Implement state verification

        try:
            token_response = await self.get_access_token(code, state)
            user_info = await self.get_user_info(token_response.access_token)

            # Find or create user in the database
            user = await User.get_by_provider_id(db, self.provider_name, user_info.sub)
            if not user:
                user = User(
                    email=user_info.email or f"{user_info.sub}@{self.provider_name}.com",
                    name=user_info.name,
                    provider=self.provider_name,
                    provider_id=user_info.sub,
                    access_token=token_response.access_token,
                    refresh_token=token_response.refresh_token,
                    token_expires_at=token_response.expires_at,
                )
                db.add(user)
            else:
                # Update existing user's tokens and potentially other info
                user.name = user_info.name
                user.email = user_info.email or user.email
                user.access_token = token_response.access_token
                user.refresh_token = token_response.refresh_token
                user.token_expires_at = token_response.expires_at
                db.add(user)

            await db.commit()
            await db.refresh(user)
            logger.info(f"User {user.email} authenticated via Ubisoft.")
            return user

        except OAuthError as e:
            logger.error(f"OAuth error during Ubisoft callback processing: {e}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error during Ubisoft callback processing: {e}")
            raise OAuthError(f"An unexpected error occurred during Ubisoft authentication: {e}")


class XboxGamePassOAuthManager(OAuthManager):
    """
    OAuth2 manager implementation for Xbox Game Pass.
    Xbox Live authentication is complex and often involves specific SDKs or
    different authentication flows (e.g., device flow, web flow).
    This is a conceptual placeholder. Direct OAuth2 for user accounts might
    not be publicly available or straightforward for third-party apps.
    """
    def __init__(self):
        # Xbox Live authentication details are often proprietary or require specific partner programs.
        # The URLs and scopes below are illustrative and likely incorrect for direct third-party use.
        super().__init__(
            client_id=settings.XBOX_CLIENT_ID, # Likely requires specific setup via Microsoft Partner Center
            client_secret=settings.XBOX_CLIENT_SECRET,
            authorize_url="https://login.live.com/oauth20_authorize.srf", # Microsoft Live login
            token_url="https://login.live.com/oauth20_token.srf", # Microsoft Live token endpoint
            userinfo_url="https://graph.microsoft.com/v1.0/me", # Microsoft Graph API for user info
            redirect_uri=f"{settings.APP_URL}/auth/xbox/callback",
            scopes=["XboxLive.signin", "offline_access", "user.read"], # Example scopes
            provider_name="xbox"
        )

    async def get_access_token(self, code: str, state: str) -> OAuthTokenResponse:
        """
        Exchanges the authorization code for an access token and refresh token for Xbox.
        This uses the Microsoft Live authentication endpoints.
        """
        if not self.client_id or not self.client_secret:
            logger.error(f"Xbox OAuth client ID or secret not configured.")
            raise OAuthError("Xbox OAuth client ID or secret not configured.")

        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.token_url, data=token_data)
                response.raise_for_status()

            token_info = response.json()
            logger.info(f"Successfully obtained Xbox access token.")
            return OAuthTokenResponse(**token_info)

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error during Xbox token exchange: {e.response.status_code} - {e.response.text}")
            raise OAuthError(f"Failed to exchange authorization code for Xbox access token: {e.response.text}")
        except httpx.RequestError as e:
            logger.error(f"Network error during Xbox token exchange: {e}")
            raise OAuthError(f"Network error during Xbox token exchange: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during Xbox token exchange: {e}")
            raise OAuthError(f"An unexpected error occurred during Xbox token exchange: {e}")

    async def get_user_info(self, access_token: str) -> OAuthUserInfoResponse:
        """
        Fetches user information from Microsoft Graph API using the access token.
        Requires appropriate scopes (e.g., user.read).
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient() as client:
                # Using Microsoft Graph API endpoint for user info
                response = await client.get(self.userinfo_url, headers=headers)
                response.raise_for_status()

            user_info = response.json()
            logger.info(f"Successfully fetched Xbox (Microsoft) user info.")

            # Microsoft Graph API user info structure
            return OAuthUserInfoResponse(
                sub=user_info.get("id", ""), # Microsoft Account ID
                name=user_info.get("displayName", "Xbox User"), # Display Name
                email=user_info.get("userPrincipalName", user_info.get("mail", "")) # Email address
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching Xbox user info: {e.response.status_code} - {e.response.text}")
            raise OAuthError(f"Failed to fetch Xbox user info: {e.response.text}")
        except httpx.RequestError as e:
            logger.error(f"Network error fetching Xbox user info: {e}")
            raise OAuthError(f"Network error fetching Xbox user info: {e}")
        except Exception as e:
            logger.error(f"Unexpected error fetching Xbox user info: {e}")
            raise OAuthError(f"An unexpected error occurred fetching Xbox user info: {e}")

    async def process_callback(self, request: Request, db: AsyncSession) -> User:
        """
        Processes the callback from Microsoft Live after user authorization for Xbox.
        Fetches user info and creates or retrieves the user in the database.
        """
        form = await request.form()
        code = form.get("code")
        state = form.get("state")
        error = form.get("error")

        if error:
            error_description = form.get("error_description", "No description provided.")
            logger.error(f"Xbox OAuth callback error: {error} - {error_description}")
            raise OAuthError(f"Xbox authentication failed: {error_description}")

        if not code or not state:
            logger.error("Xbox OAuth callback missing 'code' or 'state' parameter.")
            raise OAuthError("Invalid callback from Xbox.")

        # TODO: Implement state verification

        try:
            token_response = await self.get_access_token(code, state)
            user_info = await self.get_user_info(token_response.access_token)

            # Find or create user in the database
            user = await User.get_by_provider_id(db, self.provider_name, user_info.sub)
            if not user:
                user = User(
                    email=user_info.email or f"{user_info.sub}@{self.provider_name}.com",
                    name=user_info.name,
                    provider=self.provider_name,
                    provider_id=user_info.sub,
                    access_token=token_response.access_token,
                    refresh_token=token_response.refresh_token,
                    token_expires_at=token_response.expires_at,
                )
                db.add(user)
            else:
                # Update existing user's tokens and potentially other info
                user.name = user_info.name
                user.email = user_info.email or user.email
                user.access_token = token_response.access_token
                user.refresh_token = token_response.refresh_token
                user.token_expires_at = token_response.expires_at
                db.add(user)

            await db.commit()
            await db.refresh(user)
            logger.info(f"User {user.email} authenticated via Xbox.")
            return user

        except OAuthError as e:
            logger.error(f"OAuth error during Xbox callback processing: {e}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error during Xbox callback processing: {e}")
            raise OAuthError(f"An unexpected error occurred during Xbox authentication: {e}")


class GOGOAuthManager(OAuthManager):
    """
    OAuth2 manager implementation for GOG Galaxy.
    GOG's OAuth implementation details might require specific documentation review.
    This is a conceptual placeholder.
    """
    def __init__(self):
        # GOG OAuth endpoints and scopes need to be confirmed from their developer portal.
        super().__init__(
            client_id=settings.GOG_CLIENT_ID,
            client_secret=settings.GOG_CLIENT_SECRET,
            authorize_url="https://auth.gog.com/oauth2/v1/authorize", # Example URL
            token_url="https://auth.gog.com/oauth2/v1/token", # Example URL
            userinfo_url="https://api.gog.com/user/v1/me", # Example URL
            redirect_uri=f"{settings.APP_URL}/auth/gog/callback",
            scopes=["basic_profile", "email"], # Example scopes
            provider_name="gog"
        )

    async def get_access_token(self, code: str, state: str) -> OAuthTokenResponse:
        """
        Exchanges the authorization code for an access token and refresh token for GOG.
        """
        if not self.client_id or not self.client_secret:
            logger.error(f"GOG OAuth client ID or secret not configured.")
            raise OAuthError("GOG OAuth client ID or secret not configured.")

        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.token_url, data=token_data)
                response.raise_for_status()

            token_info = response.json()
            logger.info(f"Successfully obtained GOG access token.")
            return OAuthTokenResponse(**token_info)

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error during GOG token exchange: {e.response.status_code} - {e.response.text}")
            raise OAuthError(f"Failed to exchange authorization code for GOG access token: {e.response.text}")
        except httpx.RequestError as e:
            logger.error(f"Network error during GOG token exchange: {e}")
            raise OAuthError(f"Network error during GOG token exchange: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during GOG token exchange: {e}")
            raise OAuthError(f"An unexpected error occurred during GOG token exchange: {e}")

    async def get_user_info(self, access_token: str) -> OAuthUserInfoResponse:
        """
        Fetches user information from GOG using the access token.
        Requires confirmation of the correct endpoint and response structure.
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.userinfo_url, headers=headers)
                response.raise_for_status()

            user_info = response.json()
            logger.info(f"Successfully fetched GOG user info.")

            # GOG user info structure needs to be verified.
            # This is a placeholder mapping.
            return OAuthUserInfoResponse(
                sub=user_info.get("id", ""), # Example GOG User ID field
                name=user_info.get("nickname", user_info.get("username", "GOG User")), # Example display name field
                email=user_info.get("email", "") # Example email field
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching GOG user info: {e.response.status_code} - {e.response.text}")
            raise OAuthError(f"Failed to fetch GOG user info: {e.response.text}")
        except httpx.RequestError as e:
            logger.error(f"Network error fetching GOG user info: {e}")
            raise OAuthError(f"Network error fetching GOG user info: {e}")
        except Exception as e:
            logger.error(f"Unexpected error fetching GOG user info: {e}")
            raise OAuthError(f"An unexpected error occurred fetching GOG user info: {e}")

    async def process_callback(self, request: Request, db: AsyncSession) -> User:
        """
        Processes the callback from GOG after user authorization.
        Fetches user info and creates or retrieves the user in the database.
        """
        form = await request.form()
        code = form.get("code")
        state = form.get("state")
        error = form.get("error")

        if error:
            error_description = form.get("error_description", "No description provided.")
            logger.error(f"GOG OAuth callback error: {error} - {error_description}")
            raise OAuthError(f"GOG authentication failed: {error_description}")

        if not code or not state:
            logger.error("GOG OAuth callback missing 'code' or 'state' parameter.")
            raise OAuthError("Invalid callback from GOG.")

        # TODO: Implement state verification

        try:
            token_response = await self.get_access_token(code, state)
            user_info = await self.get_user_info(token_response.access_token)

            # Find or create user in the database
            user = await User.get_by_provider_id(db, self.provider_name, user_info.sub)
            if not user:
                user = User(
                    email=user_info.email or f"{user_info.sub}@{self.provider_name}.com",
                    name=user_info.name,
                    provider=self.provider_name,
                    provider_id=user_info.sub,
                    access_token=token_response.access_token,
                    refresh_token=token_response.refresh_token,
                    token_expires_at=token_response.expires_at,
                )
                db.add(user)
            else:
                # Update existing user's tokens and potentially other info
                user.name = user_info.name
                user.email = user_info.email or user.email
                user.access_token = token_response.access_token
                user.refresh_token = token_response.refresh_token
                user.token_expires_at = token_response.expires_at
                db.add(user)

            await db.commit()
            await db.refresh(user)
            logger.info(f"User {user.email} authenticated via GOG.")
            return user

        except OAuthError as e:
            logger.error(f"OAuth error during GOG callback processing: {e}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error during GOG callback processing: {e}")
            raise OAuthError(f"An unexpected error occurred during GOG authentication: {e}")


# Factory function to get the appropriate OAuth manager
def get_oauth_manager(provider: str) -> OAuthManager:
    """
    Returns an instance of the appropriate OAuthManager based on the provider name.

    Args:
        provider: The name of the OAuth provider (e.g., "google", "epic", "ubisoft").

    Returns:
        An instance of a concrete OAuthManager subclass.

    Raises:
        ValueError: If the provider is not supported.
    """
    if provider == "google":
        if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
            logger.warning("Google OAuth is not configured. Skipping.")
            raise ValueError("Google OAuth is not configured.")
        return GoogleOAuthManager()
    elif provider == "epic":
        if not settings.EPIC_CLIENT_ID or not settings.EPIC_CLIENT_SECRET:
            logger.warning("Epic Games OAuth is not configured. Skipping.")
            raise ValueError("Epic Games OAuth is not configured.")
        return EpicGamesOAuthManager()
    elif provider == "ubisoft":
        if not settings.UBISOFT_CLIENT_ID or not settings.UBISOFT_CLIENT_SECRET:
            logger.warning("Ubisoft OAuth is not configured. Skipping.")
            raise ValueError("Ubisoft OAuth is not configured.")
        return UbisoftOAuthManager()
    elif provider == "xbox":
        if not settings.XBOX_CLIENT_ID or not settings.XBOX_CLIENT_SECRET:
            logger.warning("Xbox OAuth is not configured. Skipping.")
            raise ValueError("Xbox OAuth is not configured.")
        return XboxGamePassOAuthManager()
    elif provider == "gog":
        if not settings.GOG_CLIENT_ID or not settings.GOG_CLIENT_SECRET:
            logger.warning("GOG OAuth is not configured. Skipping.")
            raise ValueError("GOG OAuth is not configured.")
        return GOGOAuthManager()
    else:
        logger.error(f"Unsupported OAuth provider: {provider}")
        raise ValueError(f"Unsupported OAuth provider: {provider}")

```