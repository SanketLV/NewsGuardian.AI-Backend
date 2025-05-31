import redis.asyncio as aioredis
import json
from typing import Optional, Dict, Any
from app.core.config import settings

redis_client: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    """Get Redis client instance."""
    global redis_client
    if redis_client is None:
        try:
            redis_client = await aioredis.from_url(
                settings.REDIS_URL, encoding="utf-8", decode_responses=True
            )
            # Test the connection
            await redis_client.ping()
        except Exception as e:
            print(f"Failed to connect to Redis: {e}")
            raise
    return redis_client


async def close_redis():
    """Close Redis connection."""
    global redis_client
    if redis_client:
        try:
            await redis_client.close()
        except Exception as e:
            print(f"Error closing Redis connection: {e}")
        finally:
            redis_client = None


async def cache_article(article_id: str, article_data: Dict[str, Any]) -> None:
    """Cache an article data in redis."""
    try:
        redis = await get_redis()
        await redis.setex(
            f"article:{article_id}", settings.REDIS_ARTICLES_TTL, json.dumps(article_data)
        )
    except Exception as e:
        print(f"Failed to cache article {article_id}: {e}")
        raise


async def get_cached_article(article_id: str) -> Optional[Dict[str, Any]]:
    """Get cached article data from redis."""
    try:
        redis = await get_redis()
        cached_data = await redis.get(f"article:{article_id}")
        if cached_data:
            return json.loads(cached_data)
        return None
    except json.JSONDecodeError as e:
        print(f"Failed to decode article {article_id}: {e}")
        return None
    except Exception as e:
        print(f"Failed to get article {article_id} from cache: {e}")
        return None


async def cache_articles_batch(articles: Dict[str, Dict[str, Any]]) -> None:
    """Cache multiple articles in redis using pipeline for better performance."""
    if not articles:
        return

    try:
        redis = await get_redis()
        pipe = redis.pipeline()

        for article_id, article_data in articles.items():
            pipe.setex(
                f"article:{article_id}",
                settings.REDIS_ARTICLES_TTL,
                json.dumps(article_data),
            )

        await pipe.execute()
    except Exception as e:
        print(f"Failed to cache articles batch: {e}")
        raise
