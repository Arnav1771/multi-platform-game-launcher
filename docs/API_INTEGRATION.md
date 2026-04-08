# API Integration Guide

This document outlines the process and considerations for integrating with various platform APIs within the Multi-Platform Game Launcher. The launcher aims to provide a unified experience for managing games across Steam, Epic Games, GOG, Xbox Game Pass, and Ubisoft+.

## 1. General Integration Principles

All API integrations will adhere to the following principles:

*   **Authentication:** Securely handle API keys, OAuth tokens, and other credentials using environment variables. Never hardcode sensitive information.
*   **Rate Limiting:** Respect API rate limits to avoid being blocked. Implement exponential backoff and retry mechanisms for transient errors.
*   **Error Handling:** Implement robust error handling for API requests, including network errors, authentication failures, and platform-specific error codes.
*   **Data Normalization:** Standardize data formats returned by different APIs (e.g., game titles, IDs, ownership status) into a common internal representation.
*   **Asynchronous Operations:** Utilize asynchronous programming (e.g., `asyncio` in Python) for API calls to maintain UI responsiveness and efficient resource utilization.
*   **Caching:** Implement caching strategies for frequently accessed or slow-to-retrieve data to improve performance and reduce API load.
*   **Logging:** Comprehensive logging of API requests, responses, and errors for debugging and monitoring.

## 2. Platform-Specific Integrations

### 2.1. Steam

**API:** Steam Web API, Steamworks SDK (for local game detection)

**Authentication:**
*   **API Key:** Obtain from the Steamworks developer portal. Store as `STEAM_API_KEY` environment variable.
*   **User Authentication (Optional for advanced features):** Steam OpenID or OAuth 2.0. This is complex and often not required for basic library management.

**Key Endpoints/Functionality:**
*   `ISteamUser/GetPlayerSummaries`: Get user profile information.
*   `IPlayerService/GetOwnedGames`: Retrieve a list of games owned by a user.
*   `ISteamApps/GetAppList`: Get a list of all Steam applications.
*   `ISteamApps/GetAppInfo`: Get detailed information about a specific application.

**Integration Notes:**
*   Steam's Web API is generally RESTful.
*   Local game detection often relies on scanning common installation directories and checking registry entries or specific game files (e.g., `steam_appid.txt`).

### 2.2. Epic Games Store

**API:** Epic Games Store API (unofficial, reverse-engineered)

**Authentication:**
*   **OAuth 2.0:** Requires user login flow to obtain access and refresh tokens. Store tokens securely.
*   **Client Credentials:** For public data access.

**Key Endpoints/Functionality:**
*   Endpoints for fetching owned games, game details, and store information. These are subject to change due to the unofficial nature of the API.

**Integration Notes:**
*   This integration is the most challenging due to the lack of official public documentation and potential for API changes.
*   Requires careful reverse engineering and maintenance.
*   User authentication is crucial for accessing owned game libraries.

### 2.3. GOG (Good Old Games)

**API:** GOG GALAXY SDK (for local game detection), GOG API (unofficial, for web data)

**Authentication:**
*   **GOG Account:** User login via OAuth 2.0 is typically required for accessing library data.
*   **API Key (for web data):** May be required for certain unofficial endpoints.

**Key Endpoints/Functionality:**
*   **GOG GALAXY:** Provides APIs for integrating with the GALAXY client, which can expose local game installations.
*   **Unofficial Web API:** Endpoints for game metadata, ownership status.

**Integration Notes:**
*   Similar to Epic, direct API access for library data can be complex and rely on unofficial methods.
*   GOG GALAXY's presence on the user's system can be leveraged for more reliable local game detection.

### 2.4. Xbox Game Pass (PC)

**API:** Microsoft Store API, Xbox Live APIs

**Authentication:**
*   **Microsoft Account:** OAuth 2.0 flow for user authentication. Requires specific scopes for accessing game library information.
*   **Client ID/Secret:** For accessing certain public Microsoft Store data.

**Key Endpoints/Functionality:**
*   APIs related to the Microsoft Store and Xbox Live services to retrieve owned titles and game details.

**Integration Notes:**
*   Requires understanding Microsoft's identity platform (Azure AD) and OAuth flows.
*   Accessing Game Pass titles specifically might involve querying entitlements associated with the authenticated user's subscription.

### 2.5. Ubisoft+

**API:** Ubisoft Connect API (unofficial, reverse-engineered)

**Authentication:**
*   **Ubisoft Account:** OAuth 2.0 flow for user authentication.

**Key Endpoints/Functionality:**
*   Endpoints to retrieve owned games, subscription status, and game metadata.

**Integration Notes:**
*   Similar to Epic and GOG, this integration relies on reverse-engineered APIs and requires ongoing maintenance.
*   User authentication is essential for accessing personal game libraries.

## 3. Backend API Integration Layer (FastAPI)

The backend will expose a unified API for the frontend, abstracting the complexities of individual platform integrations.

### 3.1. Environment Variables

Ensure the following environment variables are set:

```bash
# General
DATABASE_URL="postgresql://user:password@host:port/dbname"
SECRET_KEY="your-super-secret-key" # For JWT signing, etc.
LOG_LEVEL="INFO"

# Platform Specific
STEAM_API_KEY="your_steam_api_key"
EPIC_CLIENT_ID="your_epic_client_id"
EPIC_CLIENT_SECRET="your_epic_client_secret"
GOG_CLIENT_ID="your_gog_client_id"
GOG_CLIENT_SECRET="your_gog_client_secret"
MICROSOFT_CLIENT_ID="your_microsoft_client_id"
MICROSOFT_CLIENT_SECRET="your_microsoft_client_secret"
UBISOFT_CLIENT_ID="your_ubisoft_client_id"
UBISOFT_CLIENT_SECRET="your_ubisoft_client_secret"

# OAuth Redirect URIs
FRONTEND_URL="http://localhost:3000" # Or your frontend's URL
```

### 3.2. Core Modules

*   **`api_integrations/`:** Directory containing platform-specific integration modules.
    *   `steam_integration.py`
    *   `epic_integration.py`
    *   `gog_integration.py`
    *   `xbox_integration.py`
    *   `ubisoft_integration.py`
    *   `base_integration.py` (Abstract base class for common methods)
*   **`models/`:** SQLAlchemy models for storing user data, game libraries, credentials, etc.
*   **`schemas/`:** Pydantic schemas for request/response validation.
*   **`services/`:** Business logic, including orchestrating API calls and data normalization.
*   **`routers/`:** FastAPI route definitions.

### 3.3. Example: `api_integrations/base_integration.py`

```python
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

class BaseAPIIntegration(ABC):
    """Abstract base class for all platform API integrations."""

    def __init__(self, user_id: Optional[int] = None):
        self.user_id = user_id
        self.client = httpx.AsyncClient(timeout=10.0) # Default timeout

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Returns the name of the platform (e.g., 'steam', 'epic')."""
        pass

    @property
    @abstractmethod
    def base_url(self) -> str:
        """The base URL for the platform's API."""
        pass

    @abstractmethod
    async def get_owned_games(self) -> List[Dict[str, Any]]:
        """Fetches the list of owned games for the authenticated user."""
        pass

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        auth: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Helper method to make HTTP requests with error handling and logging."""
        url = f"{self.base_url}{endpoint}"
        request_headers = headers or {}
        request_params = params or {}
        request_json = json or {}

        try:
            response = await self.client.request(
                method=method.upper(),
                url=url,
                params=request_params,
                json=request_json,
                headers=request_headers,
                auth=auth,
            )
            response.raise_for_status()  # Raise HTTPStatusError for bad responses (4xx or 5xx)

            logger.debug(f"API Request: {method.upper()} {url} | Params: {request_params} | Response Status: {response.status_code}")
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text} for URL {url}")
            # Consider more specific error handling based on status codes (e.g., 401, 403, 429)
            raise  # Re-raise the exception to be handled by the caller
        except httpx.RequestError as e:
            logger.error(f"An error occurred while requesting {url}: {e}")
            raise  # Re-raise the exception
        except Exception as e:
            logger.error(f"An unexpected error occurred during API request to {url}: {e}")
            raise

    async def close(self):
        """Close the underlying HTTP client."""
        await self.client.aclose()

    # Add common methods like refresh_token, handle_oauth if applicable
```

### 3.4. Example: `api_integrations/steam_integration.py`

```python
import logging
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from httpx import AsyncHTTPClient

from .base_integration import BaseAPIIntegration

logger = logging.getLogger(__name__)

load_dotenv() # Load environment variables from .env file

class SteamIntegration(BaseAPIIntegration):
    """Integration with the Steam Web API."""

    platform_name: str = "steam"
    base_url: str = "https://api.steampowered.com/"

    def __init__(self, user_id: Optional[int] = None):
        super().__init__(user_id)
        self.api_key = os.getenv("STEAM_API_KEY")
        if not self.api_key:
            logger.warning("STEAM_API_KEY not found in environment variables. Steam integration may be limited.")

    async def _get_steam_id(self, user_profile_id: str) -> Optional[str]:
        """
        Fetches the SteamID64 from a custom profile URL or vanity URL.
        This is a simplified example; a full implementation might need more robust lookup.
        """
        if not self.api_key:
            logger.error("Cannot resolve SteamID: STEAM_API_KEY is missing.")
            return None

        try:
            response_data = await self._make_request(
                method="GET",
                endpoint="ISteamUser/ResolveVanityURL/v1/",
                params={"key": self.api_key, "vanityurl": user_profile_id},
            )
            if response_data.get("response", {}).get("success") == 1:
                return response_data["response"]["steamid"]
            else:
                logger.warning(f"Could not resolve vanity URL '{user_profile_id}'.")
                return None
        except Exception as e:
            logger.error(f"Error resolving Steam vanity URL for {user_profile_id}: {e}")
            return None

    async def get_owned_games(self, steam_id: str) -> List[Dict[str, Any]]:
        """
        Fetches the list of owned games for a given SteamID64.
        Requires STEAM_API_KEY to be set.
        """
        if not self.api_key:
            logger.error("Cannot fetch owned games: STEAM_API_KEY is missing.")
            return []

        try:
            response_data = await self._make_request(
                method="GET",
                endpoint="IPlayerService/GetOwnedGames/v1/",
                params={
                    "key": self.api_key,
                    "steamid": steam_id,
                    "include_appinfo": 1, # Include basic app details
                    "include_played_free_games": 1,
                },
            )
            # The response structure might vary, adjust parsing as needed
            games = response_data.get("response", {}).get("games", [])
            logger.info(f"Fetched {len(games)} owned games for SteamID {steam_id}")
            return games
        except Exception as e:
            logger.error(f"Error fetching owned games for SteamID {steam_id}: {e}")
            return []

    async def get_app_details(self, app_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """
        Fetches detailed information for a list of Steam App IDs.
        Uses the ISteamApps/GetAppList/v2 endpoint and then individual lookups or a batch endpoint if available.
        Note: Steam doesn't have a direct batch endpoint for GetAppInfo. This might involve multiple calls or a different approach.
        For simplicity, this example assumes fetching details one by one or using a cached app list.
        A more efficient approach would be to fetch the full app list once and cache it.
        """
        if not self.api_key:
            logger.error("Cannot fetch app details: STEAM_API_KEY is missing.")
            return {}

        app_details_map = {}
        # Steam doesn't have a direct batch GetAppInfo endpoint.
        # A common strategy is to fetch the full app list once and cache it,
        # or use the storefront API which can fetch multiple details at once.
        # Example using storefront API (unofficial but widely used):
        # https://store.steampowered.com/api/appdetails?appids=APPID1,APPID2,...
        try:
            app_ids_str = ",".join(map(str, app_ids))
            storefront_url = f"https://store.steampowered.com/api/appdetails?appids={app_ids_str}"
            async with AsyncHTTPClient() as client:
                response = await client.get(storefront_url)
                response.raise_for_status()
                data = response.json()

                for app_id, details in data.items():
                    if details and details.get("success"):
                        app_details_map[int(app_id)] = details["data"]
                    else:
                        logger.warning(f"Failed to get details for Steam App ID: {app_id}")
            logger.info(f"Fetched details for {len(app_details_map)} Steam App IDs.")
            return app_details_map
        except Exception as e:
            logger.error(f"Error fetching Steam app details for app IDs {app_ids}: {e}")
            return {}

    # Add methods for local game detection if needed (e.g., scanning registry/folders)

```

### 3.5. Example: `routers/game_routers.py`

```python
import logging
from typing import List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..services import game_service
from ..schemas import GameSchema # Assuming GameSchema is defined elsewhere

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/games", tags=["Games"])

@router.get(
    "/",
    response_model=List[GameSchema],
    summary="Get all managed games",
    description="Retrieves a unified list of all games across all integrated platforms.",
)
async def get_all_managed_games(
    db: Session = Depends(get_db),
    platform: Optional[str] = Query(None, description="Filter by platform (e.g., steam, epic)"),
    owned: Optional[bool] = Query(None, description="Filter by ownership status"),
):
    """
    Endpoint to fetch all games managed by the launcher.
    Supports filtering by platform and ownership status.
    """
    try:
        # game_service.get_all_games would orchestrate calls to individual platform integrations
        # and merge/normalize the results.
        games = await game_service.get_all_games(db, platform=platform, owned=owned)
        return games
    except Exception as e:
        logger.error(f"Error fetching all managed games: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while fetching games.")

@router.post(
    "/sync",
    status_code=202, # Accepted
    summary="Initiate game library synchronization",
    description="Triggers asynchronous synchronization of game libraries from all connected platforms.",
)
async def sync_game_libraries(
    db: Session = Depends(get_db),
    #