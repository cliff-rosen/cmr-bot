"""
Search Service for Web Search functionality

This service handles web search operations using various search APIs.
Currently supports Google Custom Search API.
"""

from typing import List, Optional, Dict, Any, TypedDict
from datetime import datetime
import logging
import asyncio
import aiohttp
from sqlalchemy.orm import Session

from config.settings import settings
from schemas.base import CanonicalSearchResult

logger = logging.getLogger(__name__)


class SearchServiceResult(TypedDict):
    """Simple service result structure containing canonical search results"""
    search_results: List[CanonicalSearchResult]
    query: str
    total_results: int
    search_time: int
    timestamp: str
    search_engine: Optional[str]
    metadata: Optional[Dict[str, Any]]


class SearchService:
    """Service for performing web searches using various search APIs"""
    
    def __init__(self):
        self.api_key = None
        self.search_engine = None
        self.custom_search_id = None
        self.initialized = False
        
    def initialize(self) -> bool:
        """
        Initialize search service with app-level API keys from settings
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            # Get API keys from settings (app-level, not user-specific)
            self.api_key = settings.GOOGLE_SEARCH_API_KEY
            self.custom_search_id = settings.GOOGLE_SEARCH_ENGINE_ID
            self.search_engine = "google"  # Default to Google
            
            if not self.api_key:
                logger.warning("Google Search API key not configured in settings")
                # Fall back to DuckDuckGo which doesn't require API key
                self.search_engine = "duckduckgo"
                self.initialized = True
                return True
                
            if not self.custom_search_id:
                logger.warning("Google Custom Search Engine ID not configured in settings")
                # Fall back to DuckDuckGo
                self.search_engine = "duckduckgo"
                self.initialized = True
                return True
            
            logger.info(f"Search service initialized with {self.search_engine}")
            self.initialized = True
            return True
            
        except Exception as e:
            logger.error(f"Error initializing search service: {str(e)}")
            return False

    async def search_google(
        self,
        search_term: str,
        num_results: int = 10,
        date_range: str = "all",
        region: str = "global",
        language: str = "en"
    ) -> SearchServiceResult:
        """
        Perform search using Google Custom Search API
        
        Args:
            search_term: The search query
            num_results: Number of results to return (max 10 per request)
            date_range: Date range filter ('day', 'week', 'month', 'year', 'all')
            region: Geographic region for search results
            language: Language for search results
            
        Returns:
            SearchServiceResult containing List[CanonicalSearchResult] and metadata
        """
        if not self.api_key or not self.custom_search_id:
            raise ValueError("Google search requires API key and custom search ID")
        
        # Google Custom Search API endpoint
        url = "https://www.googleapis.com/customsearch/v1"
        
        # Build parameters
        params = {
            "key": self.api_key,
            "cx": self.custom_search_id,
            "q": search_term,
            "num": min(num_results, 10),  # Google API max is 10 per request
            "lr": f"lang_{language}" if language != "en" else None,
            "gl": region if region != "global" else None,
        }
        
        # Add date range filter
        if date_range != "all":
            date_filters = {
                "day": "d1",
                "week": "w1", 
                "month": "m1",
                "year": "y1"
            }
            if date_range in date_filters:
                params["dateRestrict"] = date_filters[date_range]
        
        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}
        
        try:
            async with aiohttp.ClientSession() as session:
                start_time = datetime.utcnow()
                async with session.get(url, params=params) as response:
                    end_time = datetime.utcnow()
                    search_time_ms = int((end_time - start_time).total_seconds() * 1000)
                    
                    if response.status == 200:
                        data = await response.json()
                        return self._format_google_results(data, search_term, search_time_ms)
                    else:
                        error_text = await response.text()
                        logger.error(f"Google search API error {response.status}: {error_text}")
                        raise Exception(f"Search API error: {response.status} - {error_text}")
                        
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error during search: {str(e)}")
            raise Exception(f"Network error during search: {str(e)}")
        except Exception as e:
            logger.error(f"Error performing Google search: {str(e)}")
            raise

    def _format_google_results(self, data: Dict[str, Any], search_term: str, search_time_ms: int) -> SearchServiceResult:
        """
        Format Google Custom Search API results into our service result format
        
        Args:
            data: Raw Google API response
            search_term: Original search query
            search_time_ms: Search execution time
            
        Returns:
            SearchServiceResult with canonical search results and metadata
        """
        items = data.get("items", [])
        search_results: List[CanonicalSearchResult] = []
        
        for idx, item in enumerate(items, 1):
            # Extract publication date from snippet or use current date
            published_date = self._extract_date_from_snippet(item.get("snippet", ""))
            
            # Create canonical search result
            result = CanonicalSearchResult(
                title=item.get("title", ""),
                url=item.get("link", ""),
                snippet=item.get("snippet", ""),
                published_date=published_date,
                source=self._extract_domain(item.get("link", "")),
                rank=idx
            )
            
            search_results.append(result)
        
        # Get total results count from API
        total_results = int(data.get("searchInformation", {}).get("totalResults", 0))
        
        return SearchServiceResult(
            search_results=search_results,
            query=search_term,
            total_results=total_results,
            search_time=search_time_ms,
            timestamp=datetime.utcnow().isoformat(),
            search_engine=self.search_engine,
            metadata=None
        )

    def _extract_domain(self, url: str) -> str:
        """Extract domain name from URL"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc or url
        except:
            return url

    def _extract_date_from_snippet(self, snippet: str) -> Optional[str]:
        """
        Try to extract a date from the search result snippet
        Returns current date if no date found
        """
        # This is a simple implementation - could be enhanced with better date parsing
        import re
        
        # Look for common date patterns
        date_patterns = [
            r'\b(\d{4}[-/]\d{1,2}[-/]\d{1,2})\b',  # YYYY-MM-DD or YYYY/MM/DD
            r'\b(\d{1,2}[-/]\d{1,2}[-/]\d{4})\b',  # MM-DD-YYYY or MM/DD/YYYY
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, snippet)
            if match:
                try:
                    date_str = match.group(1)
                    # Basic normalization to ISO format
                    if '/' in date_str:
                        date_str = date_str.replace('/', '-')
                    return date_str
                except:
                    continue
        
        # Return current date if no date found in snippet
        return datetime.utcnow().strftime("%Y-%m-%d")

    async def search_duckduckgo(
        self,
        search_term: str,
        num_results: int = 10,
        region: str = "global"
    ) -> SearchServiceResult:
        """
        Perform search using DuckDuckGo API (as fallback)
        
        Args:
            search_term: The search query
            num_results: Number of results to return
            region: Geographic region for search results
            
        Returns:
            SearchServiceResult containing canonical search results and metadata
        """
        # DuckDuckGo Instant Answer API
        url = "https://api.duckduckgo.com/"
        
        params = {
            "q": search_term,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                start_time = datetime.utcnow()
                async with session.get(url, params=params) as response:
                    end_time = datetime.utcnow()
                    search_time_ms = int((end_time - start_time).total_seconds() * 1000)
                    
                    if response.status == 200:
                        data = await response.json()
                        return self._format_duckduckgo_results(data, search_term, search_time_ms, num_results)
                    else:
                        error_text = await response.text()
                        logger.error(f"DuckDuckGo search API error {response.status}: {error_text}")
                        raise Exception(f"Search API error: {response.status} - {error_text}")
                        
        except Exception as e:
            logger.error(f"Error performing DuckDuckGo search: {str(e)}")
            raise

    def _format_duckduckgo_results(self, data: Dict[str, Any], search_term: str, search_time_ms: int, num_results: int) -> SearchServiceResult:
        """
        Format DuckDuckGo API results into our service result format
        
        Returns:
            SearchServiceResult with canonical search results and metadata
        """
        # DuckDuckGo instant answers are limited, so we create a basic response
        search_results: List[CanonicalSearchResult] = []
        
        # Add instant answer if available
        if data.get("AbstractText"):
            result = CanonicalSearchResult(
                title=data.get("AbstractSource", "DuckDuckGo"),
                url=data.get("AbstractURL", ""),
                snippet=data.get("AbstractText", ""),
                published_date=datetime.utcnow().strftime("%Y-%m-%d"),
                source=self._extract_domain(data.get("AbstractURL", "")),
                rank=1
            )
            search_results.append(result)
        
        # Add related topics
        for idx, topic in enumerate(data.get("RelatedTopics", [])[:num_results-1], 2):
            if isinstance(topic, dict) and topic.get("Text"):
                result = CanonicalSearchResult(
                    title=topic.get("FirstURL", "").split("/")[-1].replace("_", " ") or "Related Topic",
                    url=topic.get("FirstURL", ""),
                    snippet=topic.get("Text", ""),
                    published_date=datetime.utcnow().strftime("%Y-%m-%d"),
                    source=self._extract_domain(topic.get("FirstURL", "")),
                    rank=idx
                )
                search_results.append(result)
        
        return SearchServiceResult(
            search_results=search_results,
            query=search_term,
            total_results=len(search_results),
            search_time=search_time_ms,
            timestamp=datetime.utcnow().isoformat(),
            search_engine=self.search_engine,
            metadata=None
        )

    async def search(
        self,
        search_term: str,
        num_results: int = 10,
        date_range: str = "all",
        region: str = "global",
        language: str = "en"
    ) -> SearchServiceResult:
        """
        Perform web search using the configured search engine
        
        Args:
            search_term: The search query
            num_results: Number of results to return
            date_range: Date range filter
            region: Geographic region for search results
            language: Language for search results
            
        Returns:
            SearchServiceResult containing canonical search results and metadata
        """
        if not self.initialized:
            # Auto-initialize if not already done
            if not self.initialize():
                raise ValueError("Search service could not be initialized")
        
        try:
            if self.search_engine == "google" and self.api_key and self.custom_search_id:
                return await self.search_google(search_term, num_results, date_range, region, language)
            elif self.search_engine == "duckduckgo":
                return await self.search_duckduckgo(search_term, num_results, region)
            else:
                # Fallback to DuckDuckGo if Google not properly configured
                logger.warning(f"Search engine '{self.search_engine}' not properly configured, falling back to DuckDuckGo")
                return await self.search_duckduckgo(search_term, num_results, region)
                
        except Exception as e:
            logger.error(f"Error performing search: {str(e)}")
            raise 