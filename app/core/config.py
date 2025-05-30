from pydantic_settings import BaseSettings
from typing import Optional
from dotenv import load_dotenv
import os

load_dotenv()

gnews_api_key = os.getenv("GNEWS_API_KEY")


class Settings(BaseSettings):
    GNEWS_API_KEY: str = gnews_api_key or ""
    API_BASE_URL: str = "https://gnews.io/api/v4"

    class Config:
        env_file = ".env"


settings = Settings()
