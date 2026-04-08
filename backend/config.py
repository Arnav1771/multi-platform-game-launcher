import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Load environment variables from a .env file if it exists
load_dotenv()

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """
    # Database configuration
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://user:password@host:port/database")
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", 10))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", 20))

    # JWT configuration
    SECRET_KEY: str = os.getenv("SECRET_KEY", "a_very_secret_key_for_development_only")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

    # OAuth configuration (example for Google)
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI: str = os.getenv("GOOGLE_REDIRECT_URI", "/auth/google/callback")

    # Other configurations
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Game launcher specific paths (example)
    STEAM_LIBRARY_PATHS: list[str] = os.getenv("STEAM_LIBRARY_PATHS", "").split(',')
    EPIC_GAMES_INSTALL_DIR: str = os.getenv("EPIC_GAMES_INSTALL_DIR", "")
    GOG_GALAXY_INSTALL_DIR: str = os.getenv("GOG_GALAXY_INSTALL_DIR", "")
    UBISOFT_CONNECT_INSTALL_DIR: str = os.getenv("UBISOFT_CONNECT_INSTALL_DIR", "")

    class Config:
        # Use env_file to specify the .env file if not in the root directory
        # env_file = ".env"
        # Use env_file_encoding for encoding
        # env_file_encoding = "utf-8"
        pass

# Instantiate the settings object
settings = Settings()

# Basic logging configuration
import logging

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# Example of how to use settings
if __name__ == "__main__":
    logger.info("Configuration loaded successfully.")
    logger.debug(f"Database URL: {settings.DATABASE_URL}")
    logger.debug(f"Secret Key: {'*' * len(settings.SECRET_KEY)}") # Mask secret key
    logger.debug(f"Access Token Expiry (minutes): {settings.ACCESS_TOKEN_EXPIRE_MINUTES}")
    logger.debug(f"Debug mode: {settings.DEBUG}")
    logger.debug(f"Steam Library Paths: {settings.STEAM_LIBRARY_PATHS}")
    logger.debug(f"Epic Games Install Dir: {settings.EPIC_GAMES_INSTALL_DIR}")
    logger.debug(f"GOG Galaxy Install Dir: {settings.GOG_GALAXY_INSTALL_DIR}")
    logger.debug(f"Ubisoft Connect Install Dir: {settings.UBISOFT_CONNECT_INSTALL_DIR}")
```