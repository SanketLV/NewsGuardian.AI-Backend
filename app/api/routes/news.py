from fastapi import APIRouter, Query, HTTPException, status
from typing import Optional
from app.models.news import NewsResponse, SingleNewsArticleResponse
from app.services.news_service import fetch_news, fetch_news_by_id
import httpx

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


@router.get("/{artilce_id}", response_model=SingleNewsArticleResponse)
async def get_news_by_id(artilce_id: str):
    try:
        article = await fetch_news_by_id(artilce_id)

        if article:
            return {"article": article, "source": "cache"}

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Article not found",
        )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="API Key invalid or rate limit exceeded",
            )

        raise HTTPException(status_code=e.response.status_code, detail=str(e))
