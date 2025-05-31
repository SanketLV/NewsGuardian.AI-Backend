from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os

load_dotenv()

gnews_api_key = os.getenv("GNEWS_API_KEY")
api_base_url = os.getenv("API_BASE_URL")
redis_url = os.getenv("REDIS_URL")
redis_articles_ttl = os.getenv("REDIS_ARTICLES_TTL")
allowed_origins = os.getenv("ALLOWED_ORIGINS")


class Settings(BaseSettings):
    GNEWS_API_KEY: str = gnews_api_key or ""
    API_BASE_URL: str = api_base_url or ""

    # Redis Configuration
    REDIS_URL: str = redis_url or ""
    REDIS_ARTICLES_TTL: int = (
        int(redis_articles_ttl) if redis_articles_ttl else 3600
    )  # 1 hour in seconds cache expiry

    # CORS Configuration
    ALLOWED_ORIGINS: str = allowed_origins or ""

    class Config:
        env_file = ".env"


settings = Settings()
