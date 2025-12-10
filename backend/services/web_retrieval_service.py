"""
Web Retrieval Service for fetching and parsing web pages
"""

from typing import Optional, Dict, Any, TypedDict
from datetime import datetime
from dataclasses import dataclass
import logging
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


@dataclass
class CanonicalWebpage:
    """Simple webpage data structure"""
    url: str
    title: str
    content: str
    html: Optional[str]
    last_modified: Optional[datetime]
    content_type: str
    status_code: int
    headers: Dict[str, str]
    metadata: Dict[str, Any]


class WebRetrievalServiceResult(TypedDict):
    """Service result structure"""
    webpage: CanonicalWebpage
    status_code: int
    response_time: int
    timestamp: str


class WebRetrievalService:
    """Service for retrieving and parsing web pages"""

    def __init__(self):
        self.default_timeout = 30
        self.default_user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

    async def retrieve_webpage(
        self,
        url: str,
        extract_text_only: bool = True,
        timeout: int = None,
        user_agent: str = None
    ) -> WebRetrievalServiceResult:
        """Retrieve and parse a webpage"""
        if not url:
            raise ValueError("URL is required")

        if not self._is_valid_url(url):
            raise ValueError(f"Invalid URL format: {url}")

        timeout = timeout or self.default_timeout
        user_agent = user_agent or self.default_user_agent

        headers = {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=timeout),
                headers=headers
            ) as session:
                start_time = datetime.utcnow()

                async with session.get(url, allow_redirects=True) as response:
                    end_time = datetime.utcnow()
                    response_time_ms = int((end_time - start_time).total_seconds() * 1000)

                    content = await response.read()

                    webpage = await self._parse_webpage(
                        url=str(response.url),
                        content=content,
                        status_code=response.status,
                        headers=dict(response.headers),
                        extract_text_only=extract_text_only
                    )

                    return WebRetrievalServiceResult(
                        webpage=webpage,
                        status_code=response.status,
                        response_time=response_time_ms,
                        timestamp=datetime.utcnow().isoformat()
                    )

        except asyncio.TimeoutError:
            raise Exception(f"Request timed out after {timeout} seconds")
        except aiohttp.ClientError as e:
            raise Exception(f"Network error: {str(e)}")
        except Exception as e:
            logger.error(f"Error retrieving webpage {url}: {str(e)}")
            raise Exception(f"Failed to retrieve webpage: {str(e)}")

    async def _parse_webpage(
        self,
        url: str,
        content: bytes,
        status_code: int,
        headers: Dict[str, str],
        extract_text_only: bool = True
    ) -> CanonicalWebpage:
        """Parse webpage content"""
        try:
            encoding = self._detect_encoding(content, headers)
            html_content = content.decode(encoding, errors='ignore')

            soup = BeautifulSoup(html_content, 'html.parser')
            title = self._extract_title(soup)
            text_content = self._extract_text_content(soup) if extract_text_only else ""
            metadata = self._extract_metadata(soup)
            content_type = headers.get('content-type', 'text/html')
            last_modified = self._parse_last_modified(headers.get('last-modified'))

            return CanonicalWebpage(
                url=url,
                title=title,
                content=text_content,
                html=html_content if not extract_text_only else None,
                last_modified=last_modified,
                content_type=content_type,
                status_code=status_code,
                headers=headers,
                metadata=metadata
            )

        except Exception as e:
            logger.error(f"Error parsing webpage content: {str(e)}")
            return CanonicalWebpage(
                url=url,
                title="Error parsing webpage",
                content=f"Failed to parse webpage content: {str(e)}",
                html=None,
                last_modified=None,
                content_type=headers.get('content-type', 'text/html'),
                status_code=status_code,
                headers=headers,
                metadata={"error": str(e)}
            )

    def _is_valid_url(self, url: str) -> bool:
        """Validate URL format"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False

    def _detect_encoding(self, content: bytes, headers: Dict[str, str]) -> str:
        """Detect content encoding"""
        content_type = headers.get('content-type', '')
        if 'charset=' in content_type:
            try:
                charset = content_type.split('charset=')[1].split(';')[0].strip()
                return charset
            except Exception:
                pass
        return 'utf-8'

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract page title"""
        title_tag = soup.find('title')
        if title_tag and title_tag.get_text(strip=True):
            return title_tag.get_text(strip=True)

        h1_tag = soup.find('h1')
        if h1_tag and h1_tag.get_text(strip=True):
            return h1_tag.get_text(strip=True)

        return "Untitled Page"

    def _extract_text_content(self, soup: BeautifulSoup) -> str:
        """Extract clean text content"""
        for script in soup(["script", "style", "nav", "footer", "header", "aside"]):
            script.decompose()

        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)

        return text

    def _extract_metadata(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract metadata from webpage"""
        metadata = {}

        meta_desc = soup.find('meta', {'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            metadata['description'] = meta_desc.get('content').strip()

        meta_author = soup.find('meta', {'name': 'author'})
        if meta_author and meta_author.get('content'):
            metadata['author'] = meta_author.get('content').strip()

        text_content = self._extract_text_content(soup)
        metadata['word_count'] = len(text_content.split())

        return metadata

    def _parse_last_modified(self, last_modified_header: Optional[str]) -> Optional[datetime]:
        """Parse last-modified header"""
        if not last_modified_header:
            return None

        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(last_modified_header)
        except Exception:
            return None
