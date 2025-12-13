"""
Search Service for Web Search functionality

This service handles web search operations using Google Custom Search API.
Requires GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID to be configured.
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


class SearchQuotaExceededError(Exception):
    """Raised when search API quota is exceeded."""
    pass


class SearchAPIError(Exception):
    """Raised when search API returns an error."""
    def __init__(self, message: str, status_code: int = None, is_retryable: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.is_retryable = is_retryable


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
            self.search_engine = "google"

            if not self.api_key:
                logger.warning("Google Search API key not configured - web search will be unavailable")

            if not self.custom_search_id:
                logger.warning("Google Custom Search Engine ID not configured - web search will be unavailable")

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
                        # Parse Google API error response
                        error_data = await response.json()
                        error_info = self._parse_google_error(error_data, response.status)
                        raise error_info

        except (SearchQuotaExceededError, SearchAPIError):
            # Re-raise our custom exceptions
            raise
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error during search: {str(e)}")
            raise SearchAPIError(f"Network error during search: {str(e)}", is_retryable=True)
        except Exception as e:
            logger.error(f"Error performing Google search: {str(e)}")
            raise SearchAPIError(f"Search error: {str(e)}")

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

    def _parse_google_error(self, error_data: Dict[str, Any], status_code: int) -> Exception:
        """
        Parse Google API error response and return appropriate exception.

        Google API error format:
        {
            "error": {
                "code": 429,
                "message": "Quota exceeded...",
                "errors": [{"reason": "rateLimitExceeded", ...}],
                "status": "RESOURCE_EXHAUSTED"
            }
        }
        """
        error = error_data.get("error", {})
        message = error.get("message", "Unknown error")
        errors = error.get("errors", [])
        status = error.get("status", "")

        # Check for quota/rate limit errors
        quota_reasons = {"rateLimitExceeded", "dailyLimitExceeded", "userRateLimitExceeded", "quotaExceeded"}
        for err in errors:
            reason = err.get("reason", "")
            if reason in quota_reasons:
                logger.warning(f"Google Search API quota exceeded: {reason} - {message}")
                return SearchQuotaExceededError(f"Search quota exceeded: {message}")

        # Check status for quota errors
        if status == "RESOURCE_EXHAUSTED" or status_code == 429:
            logger.warning(f"Google Search API quota exceeded: {message}")
            return SearchQuotaExceededError(f"Search quota exceeded: {message}")

        # Check for billing/auth errors (not retryable)
        if status_code in (401, 403):
            logger.error(f"Google Search API auth error: {message}")
            return SearchAPIError(f"Search API authentication error: {message}", status_code, is_retryable=False)

        # Server errors are retryable
        if status_code >= 500:
            logger.error(f"Google Search API server error: {message}")
            return SearchAPIError(f"Search API server error: {message}", status_code, is_retryable=True)

        # Default error
        logger.error(f"Google Search API error {status_code}: {message}")
        return SearchAPIError(f"Search API error: {message}", status_code, is_retryable=False)

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

    async def search(
        self,
        search_term: str,
        num_results: int = 10,
        date_range: str = "all",
        region: str = "global",
        language: str = "en"
    ) -> SearchServiceResult:
        """
        Perform web search using Google Custom Search API.

        Args:
            search_term: The search query
            num_results: Number of results to return
            date_range: Date range filter
            region: Geographic region for search results
            language: Language for search results

        Returns:
            SearchServiceResult containing canonical search results and metadata

        Raises:
            SearchAPIError: If Google API keys are not configured or search fails
            SearchQuotaExceededError: If Google API quota is exceeded
        """
        if not self.initialized:
            if not self.initialize():
                raise ValueError("Search service could not be initialized")

        # Check if Google API is properly configured
        if not self.api_key or not self.custom_search_id:
            raise SearchAPIError(
                "Web search unavailable. Google Search API key and Custom Search Engine ID are required. "
                "Please configure GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID in settings.",
                is_retryable=False
            )

        try:
            return await self.search_google(search_term, num_results, date_range, region, language)
        except (SearchQuotaExceededError, SearchAPIError):
            raise
        except Exception as e:
            logger.error(f"Error performing search: {str(e)}")
            raise SearchAPIError(f"Search failed: {str(e)}")