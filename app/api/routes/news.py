from fastapi import APIRouter, Query, HTTPException, status
from typing import Optional
from app.models.news import NewsResponse, SingleNewsArticleResponse
from app.services.news_service import (
    fetch_news,
    fetch_news_by_id,
    scrape_full_article_content,
    _generate_article_metadata,
)
import httpx
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/news", tags=["news"])


@router.get("/", response_model=NewsResponse)
async def get_news(
    q: Optional[str] = Query(None, description="Search Query keywords"),
    lang: str = Query("en", description="Language of the news articles"),
    country: Optional[str] = Query(
        None, description="Country where news was published"
    ),
    max_results: int = Query(
        10, description="Number of news articles to return", ge=1, le=100
    ),
    category: Optional[str] = Query(
        None, description="news category for top headlines"
    ),
):
    try:
        return await fetch_news(
            query=q,
            language=lang,
            country=country,
            max_results=max_results,
            category=category,
        )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="API Key invalid or rate limit exceeded",
            )

        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Error fetching news: {str(e)}",
        )


@router.get("/{article_id}", response_model=SingleNewsArticleResponse)
async def get_news_by_id(
    article_id: str,
    full_content: bool = Query(
        True, description="Whether to scrape fulll article content"
    ),
    include_metadata: bool = Query(
        True, description="Whether to include additional metadata"
    ),
):
    """
    Get detailed information about a specific news article by ID.

    This endpoint retrieves a single news article and optionally enhances it with:
    - Full scraped content from the original URL
    - Additional metadata like content source, word count, reading time
    - Content analysis information
    """
    try:
        article = await fetch_news_by_id(article_id)

        if not article:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Article with ID '{article_id}' not found",
            )

        # Initialize response data
        response_data = {
            "article": article,
            "source": "cache",
            "enhanced": False,
            "metadata": {},
        }

        # Enhance with full content if requested
        if full_content and article.get("url"):
            logger.info(f"Attempting to scrape full content for article: {article_id}")

            try:
                # Scrape full content from the original URL
                full_scraped_content = await scrape_full_article_content(article["url"])

                if full_scraped_content:
                    original_content_length = len(article.get("content", ""))
                    scraped_content_length = len(full_scraped_content)

                    # Only replace if scraped content is significantly longer
                    if scraped_content_length > original_content_length:
                        article["content"] = full_scraped_content
                        article["content_source"] = "scraped"
                        response_data["enhanced"] = True

                        logger.info(
                            f"Successfully enhanced article {article_id} with scraped content"
                        )

                        # Add enhancement metadata
                        if include_metadata:
                            response_data["metadata"]["content_enhancement"] = {
                                "original_length": original_content_length,
                                "scraped_length": scraped_content_length,
                                "improvement_ratio": round(
                                    scraped_content_length
                                    / max(original_content_length, 1),
                                    2,
                                ),
                            }
                        else:
                            article["content_source"] = "api"
                            logger.warning(
                                f"Scrapped content for {article_id} was not better than original content"
                            )
                    else:
                        article["content_source"] = "api"
                        logger.warning(
                            f"Failed to scrape meaningfull content for article {article_id}"
                        )
            except Exception as scraping_error:
                logger.error(
                    f"Error scraping content for article {article_id}: {str(scraping_error)}"
                )
                article["content_source"] = "api"

                if include_metadata:
                    response_data["metadata"]["scraping_error"] = str(scraping_error)
        else:
            article["content_source"] = "api"

        # Add additional metadata if requested
        if include_metadata:
            metadata = await _generate_article_metadata(article)
            response_data["metadata"].update(metadata)

        # Update the article in the response
        response_data["article"] = article

        return response_data
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="API Key invalid or rate limit exceeded",
            ) from e
        raise HTTPException(
            status_code=e.response.status_code, detail=f"External API error: {str(e)}"
        ) from e
    except Exception as e:
        logger.error(
            f"Unexpected error in get_news_by_id for article {article_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while fetching the article",
        ) from e
