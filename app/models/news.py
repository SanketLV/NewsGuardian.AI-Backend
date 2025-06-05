from pydantic import BaseModel
from typing import List, Optional, Any, Dict


class Source(BaseModel):
    name: str
    url: Optional[str] = None


class Article(BaseModel):
    id: str
    title: str
    description: str
    content: Optional[str] = None
    url: str
    image: Optional[str] = None
    publishedAt: str
    source: Source
    content_source: Optional[str] = "api"  # "api" or "scraped"


class NewsResponse(BaseModel):
    totalArticles: int
    articles: List[Article]


class ArticleMetadata(BaseModel):
    content_stats: Optional[Dict[str, Any]] = None
    source_info: Optional[Dict[str, Any]] = None
    publication_info: Optional[Dict[str, Any]] = None
    content_enhancement: Optional[Dict[str, Any]] = None
    scraping_error: Optional[str] = None


class SingleNewsArticleResponse(BaseModel):
    article: Article
    source: str
    enhanced: bool = False
    metadata: Optional[ArticleMetadata] = None
