import httpx
import uuid
from typing import Optional, Dict, Any
from app.core.config import settings
from app.services.redis import cache_articles_batch, get_cached_article


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
        result = response.json()

        # Add unique ID to each article and prepare for caching
        articles_to_cache = {}

        if "articles" in result and isinstance(result["articles"], list):
            for article in result["articles"]:
                if isinstance(article, dict):
                    article["id"] = str(uuid.uuid4())
                    articles_to_cache[article["id"]] = article.copy()

        # cache all artilces in redis
        if articles_to_cache:
            await cache_articles_batch(articles_to_cache)
            print(f"Cached {len(articles_to_cache)} articles in Redis.")

        return result


async def fetch_news_by_id(article_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a cached news article by its ID.
    
    Args:
        article_id: The unique identifier for the article
        
    Returns:
        The article data if found in cache, None otherwise
    """
    try:
        article = await get_cached_article(article_id)
        if article:
            print(f"Fetched article with ID {article_id} from cache.")
            return article
        print(f"Article with ID {article_id} not found in cache.")
        return None
    except Exception as e:
        print(f"Error fetching article {article_id}: {e}")
        return None
