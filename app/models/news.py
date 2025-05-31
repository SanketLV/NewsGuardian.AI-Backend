from pydantic import BaseModel
from typing import List, Optional, Literal


class Source(BaseModel):
    name: str
    url: str


class Article(BaseModel):
    id: str
    title: str
    description: str
    content: Optional[str] = None
    url: str
    image: Optional[str] = None
    publishedAt: str
    source: Source


class NewsResponse(BaseModel):
    totalArticles: int
    articles: List[Article]


class SingleNewsArticleResponse(BaseModel):
    article: Article
    Source: Literal["cache", "api"] = "cache"
