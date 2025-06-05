import httpx
import uuid
import logging
import re
import asyncio
import datetime
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from typing import Optional, Dict, Any, List
from app.core.config import settings
from app.services.redis import cache_articles_batch, get_cached_article

logger = logging.getLogger(__name__)


class UniversalArticleScraper:
    def __init__(self):
        self.timeout = 30.0
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    async def scrape_article_content(self, url: str) -> Optional[str]:
        """Scrape full article content from any news URL using multiple strategies."""
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout, headers=self.headers
            ) as client:
                response = await client.get(url)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, "html.parser")

                # Remove unwanted elements
                self._clean_soup(soup)

                # Try multiple extraction strategies
                content = (
                    self._extract_by_json_ld(soup)
                    or self._extract_by_meta_tags(soup)
                    or self._extract_by_semantic_tags(soup)
                    or self._extract_by_common_selectors(soup)
                    or self._extract_by_paragraph_density(soup)
                )

                if content:
                    # Clean and format the content
                    content = self._clean_content(content)
                    return content if len(content) > 100 else None

                return None
        except Exception as e:
            logger.error(f"Error scrapping article from {url}: {str(e)}")
            return None

    def _clean_soup(self, soup: BeautifulSoup):
        """Remove unwanted elements from the soup."""
        unwanted_tags = [
            "script",
            "style",
            "nav",
            "header",
            "footer",
            "aside",
            "advertisement",
            "ads",
            "social",
            "share",
            "comment",
            "related",
            "sidebar",
            "menu",
        ]

        unwanted_classes = [
            "ad",
            "ads",
            "advertisement",
            "social",
            "share",
            "sharing",
            "comment",
            "comments",
            "related",
            "sidebar",
            "navigation",
            "nav",
            "menu",
            "footer",
            "header",
            "promo",
            "newsletter",
        ]

        # Remove by tag name
        for tag in unwanted_tags:
            for element in soup.find_all(tag):
                element.decompose()

        # Remove by class name patterns
        for class_patterns in unwanted_classes:
            for element in soup.find_all(class_=re.compile(class_patterns, re.I)):
                element.decompose()

    def _extract_by_json_ld(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract content from JSON-LD script tags."""
        try:
            import json

            scripts = soup.find_all("script", type="application/ld+json")

            for script in scripts:
                try:
                    script_text = script.get_text()
                    if not script_text:
                        continue

                    data = json.loads(script_text)
                    if isinstance(data, list):
                        data = data[0]

                    # Look for article content in various JSON-LD properties
                    content_fields = ["articleBody", "text", "description", "content"]

                    for field in content_fields:
                        if field in data and data[field]:
                            content = data[field]
                            if len(content) > 200:
                                return content
                except json.JSONDecodeError:
                    continue
        except Exception as e:
            logger.debug(f"Error extracting content from JSON-LD: {str(e)}")
        return None

    def _extract_by_meta_tags(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract content from meta tags as fallback"""
        meta_selectors = [
            "meta[name='description']",
            "meta[property='og:description']",
            "meta[property='article:content']",
        ]

        for selector in meta_selectors:
            meta = soup.select_one(selector)
            if meta and meta.get("content"):
                content = str(meta.get("content"))
                if len(content) > 200:
                    return content
        return None

    def _extract_by_semantic_tags(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract content using semantic HTML5 tags"""
        semantic_selectors = [
            "article",
            "main article",
            '[role="main"] article',
            "main",
            '[role="main]',
        ]

        for selector in semantic_selectors:
            container = soup.select_one(selector)
            if container:
                paragraphs = container.find_all("p")
                if len(paragraphs) >= 3:
                    content = self._extract_paragraphs(paragraphs)
                    if len(content) > 200:
                        return content

        return None

    def _extract_by_common_selectors(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract content using common CSS selectors"""
        common_selectors = [
            # Article content containers
            ".article-content p, .article-body p, .post-content p",
            ".entry-xontent p, .content p, .story-content p",
            ".article p, .post p, .story p",
            # Generic content containers
            ".content-body p, .main-content p, .page-content p",
            ".text-content p, .editorial-content p",
            # ID-based selectors
            "#article-content p, #post-content p, #story-content p",
            "#content p, #main-content p",
            # Data attribute selectors
            '[data-component="text-block"] p',
            '[data-module="ArticleBody"] p',
            # Fallback to any substantial paragraph collection
            "div p",
        ]

        for selector in common_selectors:
            elements = soup.select(selector)
            if len(elements) >= 3:
                content = self._extract_paragraphs(elements)
                if len(content) > 200:
                    return content

        return None

    def _extract_by_paragraph_density(self, soup: BeautifulSoup) -> Optional[str]:
        """Find the container with highest paragraph density."""
        containers = soup.find_all(["div", "section", "article"])
        best_container = None
        max_score = 0

        from bs4 import Tag

        for container in containers:
            if not isinstance(container, Tag):
                continue
            paragraphs = container.find_all("p", recursive=False)
            if not paragraphs:
                paragraphs = container.find_all("p")

            # Score based on paragraph count and total text length
            text_length = sum(len(p.get_text().strip()) for p in paragraphs)
            score = len(paragraphs) * text_length

            if score > max_score and len(paragraphs) >= 2:
                max_score = score
                best_container = container

        if best_container:
            paragraphs = best_container.find_all("p")
            content = self._extract_paragraphs(paragraphs)
            if len(content) > 200:
                return content

        return None

    def _extract_paragraphs(self, paragraphs: List) -> str:
        """Extract and clean text from paragraph elements."""
        content_parts = []

        for p in paragraphs:
            text = p.get_text().strip()

            # Skip short paragraphs (likely navigations, ads, etc.)
            if len(text) < 20:
                continue

            # Skip paragraphs that look like navogation or metadata
            if self._is_likely_noise(text):
                continue

            content_parts.append(text)

        return "\n\n".join(content_parts)

    def _is_likely_noise(self, text: str) -> bool:
        """Check if the text is likely to be noise(ads, navigation, etc.)."""
        noise_patterns = [
            r"^(read more|continue reading|click here|subscribe|sign up)",
            r"^(share|tweet|facebook|linkedin|email)",
            r"^(advertisement|sponsored|promoted)",
            r"^(related articles|you may also like|recommended)",
            r"^(tags?:|categories?:|filed under)",
            r"^\d+\s*(comments?|replies)",
            r"^(photo|image|video):\s*",
            r"^(source|via|originally published)",
        ]

        text_lower = text.lower()
        for pattern in noise_patterns:
            if re.match(pattern, text_lower):
                return True

        # Skip very short text that's likely metadata
        if len(text) < 20 and any(
            word in text_lower
            for word in ["©", "copyright", "rights reserved", "updated", "published"]
        ):
            return True

        return False

    def _clean_content(self, content: str) -> str:
        """Clean and format the extracted content"""
        # Remove extra whitespace
        content = re.sub(r"\s+", " ", content)

        # Fix paragraph breaks
        content = re.sub(r"\n\s*\n", "\n\n", content)

        # Remove common trailing noise
        noise_endings = [
            r"\s*(read more|continue reading|click here).*$",
            r"\s*(share this article|share on).*$",
            r"\s*(tags?:|categories?:).*$",
        ]

        for pattern in noise_endings:
            content = re.sub(pattern, "", content, flags=re.IGNORECASE)

        return content.strip()


# Create a global instance
universal_scraper = UniversalArticleScraper()


async def scrape_full_article_content(url: str) -> Optional[str]:
    """Public function to scrape article content from any news website"""
    return await universal_scraper.scrape_article_content(url)


async def enhance_articles_with_full_content(
    articles: list, max_concurrent: int = 5
) -> list:
    """Enhandce articles with full scraped content using concurrent processing"""

    async def scrape_single_article(article):
        """Scrape content for a single article"""
        try:
            url = article.get("url", "")
            if not url:
                article["content_source"] = "api"
                return article

            # Scrape full content from URL
            full_content = await scrape_full_article_content(url)

            if full_content and len(full_content) > len(article.get("content", "")):
                # Replace truncated content with full content
                article["content"] = full_content
                article["content_source"] = "scraped"
                logger.info(f"Successfully scraped content from {url}")
            else:
                # Keep Original content if scraping fails or content is shorter
                article["content_source"] = "api"
                logger.warning(f"Scraping returned insufficient content for {url}")
        except Exception as e:
            logger.warning(
                f"Failed to scrape content from {article.get("url", "")}: {str(e)}"
            )
            article["content_source"] = "api"

        return article

    # Process articles concurrently with a limit
    semaphore = asyncio.Semaphore(max_concurrent)

    async def scrape_with_semaphore(article):
        async with semaphore:
            return await scrape_single_article(article)

    # Execute all scraping tasks concurrently
    enhanced_articles = await asyncio.gather(
        *[scrape_with_semaphore(article) for article in articles],
        return_exceptions=True,
    )

    # Filter out any exceptions and return valid articles
    result = []
    for article in enhanced_articles:
        if isinstance(article, Exception):
            logger.error(f"Article processing failed: {article}")
        else:
            result.append(article)

    return result


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


async def _generate_article_metadata(article: dict) -> dict:
    """Generate additional metadata for the article"""
    try:
        content = article.get("content", "")

        # Basic content statistics
        word_count = len(content.split()) if content else 0
        char_count = len(content)
        paragraph_count = (
            len([p for p in content.split("\n\n") if p.strip()]) if content else 0
        )

        # Estimated reading time (average 200 words per minute)
        reading_time_minutes = max(1, round(word_count / 200))

        # Content quality indicators
        has_substantial_content = word_count > 100
        content_completeness = (
            "complete"
            if word_count > 300
            else "partial" if word_count > 100 else "minimal"
        )

        # URL analysis
        url_domain = ""
        if article.get("url"):
            try:
                parsed_url = urlparse(article["url"])
                url_domain = parsed_url.netloc
            except Exception:
                pass

        # Publication analysis
        published_at = article.get("publishedAt")
        time_since_publication = None

        if published_at:
            try:
                if isinstance(published_at, str):
                    # Parse ISO format datetime
                    pub_date = datetime.datetime.fromisoformat(
                        published_at.replace("Z", "+00:00")
                    )
                    time_diff = datetime.datetime.now(datetime.timezone.utc) - pub_date

                    if time_diff.days > 0:
                        time_since_publication = f"{time_diff.days} days ago"
                    elif time_diff.seconds > 3600:
                        hours = time_diff.seconds // 3600
                        time_since_publication = f"{hours} hours ago"
                    else:
                        minutes = time_diff.seconds // 60
                        time_since_publication = f"{minutes} minutes ago"
            except Exception as e:
                logger.debug(f"Error parsing publication date: {e}")

        metadata = {
            "content_stats": {
                "word_count": word_count,
                "character_count": char_count,
                "paragraph_count": paragraph_count,
                "estimated_reading_time_minutes": reading_time_minutes,
                "has_substantial_content": has_substantial_content,
                "content_completeness": content_completeness,
            },
            "source_info": {
                "url_domain": url_domain,
                "source_name": article.get("source", {}).get("name", "Unknown"),
                "content_source": article.get("content_source", "api"),
            },
            "publication_info": {
                "published_at": published_at,
                "time_since_publication": time_since_publication,
            },
        }

        return metadata

    except Exception as e:
        logger.error(f"Error generating article metadata: {str(e)}")
        return {"error": "Failed to generate metadata"}
