import httpx
from typing import Optional, Dict, Any
from app.core.config import settings


async def fetch_news(
    query: Optional[str] = None,
    language: str = "en",
    country: Optional[str] = None,
    max_results: int = 10,
    category: Optional[str] = None,
) -> Dict[str, Any]:
    base_url = settings.API_BASE_URL

    # Determine which endpoint to use
    if category:
        endpoint = f"{base_url}/top-headlines"
        params = {"category": category}
    elif query:
        endpoint = f"{base_url}/search"
        params = {"q": query}
    else:
        endpoint = f"{base_url}/top-headlines"
        params = {}

    # Add common parameters
    params["lang"] = language
    params["max"] = str(max_results)
    params["apikey"] = settings.GNEWS_API_KEY

    # Add Optional Parameters
    if country:
        params["country"] = country

    async with httpx.AsyncClient() as client:
        response = await client.get(endpoint, params=params)
        response.raise_for_status()
        return response.json()
