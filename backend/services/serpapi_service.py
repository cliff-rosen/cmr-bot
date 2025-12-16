"""
SerpAPI Service

Provides reliable access to Yelp and Google reviews via SerpAPI.
https://serpapi.com/
"""

import os
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Literal
import httpx

logger = logging.getLogger(__name__)

SERPAPI_BASE_URL = "https://serpapi.com/search.json"


@dataclass
class SerpApiReview:
    """A review from SerpAPI."""
    rating: Optional[float]
    text: str
    author: Optional[str] = None
    date: Optional[str] = None
    source: Optional[str] = None  # "yelp" or "google"


@dataclass
class SerpApiBusiness:
    """A business entity from SerpAPI."""
    name: str
    place_id: str  # yelp biz_id or google place_id/data_id
    address: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    phone: Optional[str] = None
    url: Optional[str] = None
    source: Literal["yelp", "google"] = "yelp"


@dataclass
class SerpApiResult:
    """Result from SerpAPI operations."""
    success: bool
    business: Optional[SerpApiBusiness] = None
    reviews: List[SerpApiReview] = field(default_factory=list)
    error: Optional[str] = None
    raw_response: Optional[Dict] = None


class SerpApiService:
    """Service for accessing Yelp and Google data via SerpAPI."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("SERPAPI_KEY") or os.getenv("SERPAPI_API_KEY")
        if not self.api_key:
            logger.warning("SERPAPI_KEY not set - SerpAPI calls will fail")

    def _make_request(self, params: Dict[str, Any], timeout_seconds: float = 15.0) -> Dict[str, Any]:
        """Make a request to SerpAPI."""
        params["api_key"] = self.api_key
        params["output"] = "json"

        timeout = httpx.Timeout(timeout_seconds, connect=5.0)

        with httpx.Client(timeout=timeout) as client:
            response = client.get(SERPAPI_BASE_URL, params=params)
            response.raise_for_status()
            return response.json()

    # =========================================================================
    # Yelp Methods
    # =========================================================================

    def search_yelp(
        self,
        query: str,
        location: str,
        limit: int = 10
    ) -> SerpApiResult:
        """
        Search for businesses on Yelp.

        Returns a list of matching businesses with their biz_ids.
        """
        if not self.api_key:
            return SerpApiResult(success=False, error="SERPAPI_KEY not configured")

        try:
            params = {
                "engine": "yelp",
                "find_desc": query,
                "find_loc": location,
                "num": limit
            }

            data = self._make_request(params)

            # Parse organic results
            businesses = []
            for result in data.get("organic_results", []):
                biz = SerpApiBusiness(
                    name=result.get("name", ""),
                    place_id=result.get("place_ids", [""])[0] if result.get("place_ids") else "",
                    address=result.get("neighborhoods", result.get("address", "")),
                    rating=result.get("rating"),
                    review_count=result.get("reviews"),
                    phone=result.get("phone"),
                    url=result.get("link"),
                    source="yelp"
                )
                if biz.place_id:
                    businesses.append(biz)

            if businesses:
                return SerpApiResult(
                    success=True,
                    business=businesses[0],  # Best match
                    raw_response=data
                )
            else:
                return SerpApiResult(
                    success=False,
                    error="No Yelp businesses found",
                    raw_response=data
                )

        except httpx.HTTPStatusError as e:
            logger.error(f"SerpAPI HTTP error: {e}")
            return SerpApiResult(success=False, error=f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"SerpAPI error: {e}")
            return SerpApiResult(success=False, error=str(e))

    def get_yelp_reviews(
        self,
        place_id: str,
        num_reviews: int = 20,
        sort_by: Optional[str] = None
    ) -> SerpApiResult:
        """
        Get reviews for a Yelp business with pagination support.

        Args:
            place_id: The Yelp biz_id (e.g., "WavvLdfdP6g8aZTtbBQHTw")
            num_reviews: Number of reviews to fetch (will paginate to get this many)
            sort_by: Optional sort order - "relevance_desc", "date_desc", "rating_desc", "rating_asc"
        """
        if not self.api_key:
            return SerpApiResult(success=False, error="SERPAPI_KEY not configured")

        try:
            all_reviews = []
            business = None
            start = 0
            per_page = 10  # Yelp typically returns ~10 per page
            max_pages = (num_reviews // per_page) + 2

            for page in range(max_pages):
                params = {
                    "engine": "yelp_reviews",
                    "place_id": place_id,
                    "start": start,
                }
                if sort_by:
                    params["sortby"] = sort_by

                data = self._make_request(params)

                # Parse reviews from this page
                page_reviews = data.get("reviews", [])
                for r in page_reviews:
                    review = SerpApiReview(
                        rating=r.get("rating"),
                        text=r.get("comment", {}).get("text", "") or r.get("text", ""),
                        author=r.get("user", {}).get("name"),
                        date=r.get("date"),
                        source="yelp"
                    )
                    if review.text:
                        all_reviews.append(review)

                # Get business info from first page only
                if page == 0:
                    biz_info = data.get("business_info", {})
                    if biz_info:
                        business = SerpApiBusiness(
                            name=biz_info.get("name", ""),
                            place_id=place_id,
                            rating=biz_info.get("rating"),
                            review_count=biz_info.get("reviews"),
                            address=biz_info.get("address"),
                            url=biz_info.get("link"),
                            source="yelp"
                        )

                # Check if we have enough reviews or no more pages
                if len(all_reviews) >= num_reviews:
                    break
                if len(page_reviews) == 0:
                    break  # No more reviews

                start += len(page_reviews)

            logger.info(f"SerpAPI: Fetched {len(all_reviews)} Yelp reviews over {page + 1} pages")

            return SerpApiResult(
                success=True,
                business=business,
                reviews=all_reviews[:num_reviews],
                raw_response=data
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"SerpAPI HTTP error: {e}")
            return SerpApiResult(success=False, error=f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"SerpAPI error: {e}")
            return SerpApiResult(success=False, error=str(e))

    # =========================================================================
    # Google Methods
    # =========================================================================

    def search_google_maps(
        self,
        query: str,
        location: str,
        limit: int = 10
    ) -> SerpApiResult:
        """
        Search for businesses on Google Maps.

        Returns a list of matching businesses with their data_ids.
        """
        if not self.api_key:
            return SerpApiResult(success=False, error="SERPAPI_KEY not configured")

        try:
            # Combine query and location for Google Maps search
            search_query = f"{query} {location}"

            params = {
                "engine": "google_maps",
                "q": search_query,
                "type": "search",
            }

            data = self._make_request(params)

            # Parse results - Google returns either local_results (multiple) or place_results (single exact match)
            businesses = []

            # Check for single exact match first
            if data.get("place_results"):
                result = data["place_results"]
                data_id = result.get("data_id", "")
                place_id = result.get("place_id", "")
                biz = SerpApiBusiness(
                    name=result.get("title", ""),
                    place_id=data_id or place_id,
                    address=result.get("address"),
                    rating=result.get("rating"),
                    review_count=result.get("reviews"),
                    phone=result.get("phone"),
                    url=result.get("website"),
                    source="google"
                )
                if biz.place_id and biz.name:
                    businesses.append(biz)

            # Then check for multiple results
            for result in data.get("local_results", []):
                # Google uses data_id for reviews lookup
                data_id = result.get("data_id", "")
                place_id = result.get("place_id", "")

                biz = SerpApiBusiness(
                    name=result.get("title", ""),
                    place_id=data_id or place_id,  # Prefer data_id for reviews
                    address=result.get("address"),
                    rating=result.get("rating"),
                    review_count=result.get("reviews"),
                    phone=result.get("phone"),
                    url=result.get("website"),
                    source="google"
                )
                if biz.place_id and biz.name:
                    businesses.append(biz)

            if businesses:
                return SerpApiResult(
                    success=True,
                    business=businesses[0],  # Best match
                    raw_response=data
                )
            else:
                return SerpApiResult(
                    success=False,
                    error="No Google Maps businesses found",
                    raw_response=data
                )

        except httpx.HTTPStatusError as e:
            logger.error(f"SerpAPI HTTP error: {e}")
            return SerpApiResult(success=False, error=f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"SerpAPI error: {e}")
            return SerpApiResult(success=False, error=str(e))

    def get_google_reviews(
        self,
        data_id: str,
        num_reviews: int = 20,
        sort_by: Optional[str] = None
    ) -> SerpApiResult:
        """
        Get reviews for a Google Maps place with pagination support.

        Args:
            data_id: The Google data_id (e.g., "0x89c259a61c75684f:0x79d31adb19735291")
            num_reviews: Number of reviews to fetch (will paginate to get this many)
            sort_by: Optional sort order - "qualityScore", "newestFirst", "ratingHigh", "ratingLow"
        """
        if not self.api_key:
            return SerpApiResult(success=False, error="SERPAPI_KEY not configured")

        try:
            all_reviews = []
            business = None
            next_token = None
            max_pages = (num_reviews // 8) + 2  # ~8-10 reviews per page, +1 for safety

            for page in range(max_pages):
                params = {
                    "engine": "google_maps_reviews",
                    "data_id": data_id,
                }
                if sort_by:
                    params["sort_by"] = sort_by
                if next_token:
                    params["next_page_token"] = next_token

                data = self._make_request(params)

                # Parse reviews from this page
                for r in data.get("reviews", []):
                    review = SerpApiReview(
                        rating=r.get("rating"),
                        text=r.get("snippet", "") or r.get("extracted_snippet", {}).get("original", ""),
                        author=r.get("user", {}).get("name"),
                        date=r.get("date"),
                        source="google"
                    )
                    if review.text:
                        all_reviews.append(review)

                # Get place info from first page only
                if page == 0:
                    place_info = data.get("place_info", {})
                    if place_info:
                        business = SerpApiBusiness(
                            name=place_info.get("title", ""),
                            place_id=data_id,
                            rating=place_info.get("rating"),
                            review_count=place_info.get("reviews"),
                            address=place_info.get("address"),
                            source="google"
                        )

                # Check if we have enough reviews
                if len(all_reviews) >= num_reviews:
                    break

                # Get next page token
                pagination = data.get("serpapi_pagination", {})
                next_token = pagination.get("next_page_token")
                if not next_token:
                    break  # No more pages

            logger.info(f"SerpAPI: Fetched {len(all_reviews)} Google reviews over {page + 1} pages")

            return SerpApiResult(
                success=True,
                business=business,
                reviews=all_reviews[:num_reviews],
                raw_response=data  # Last page's response
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"SerpAPI HTTP error: {e}")
            return SerpApiResult(success=False, error=f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"SerpAPI error: {e}")
            return SerpApiResult(success=False, error=str(e))

    # =========================================================================
    # Unified Methods
    # =========================================================================

    def find_and_get_reviews(
        self,
        business_name: str,
        location: str,
        source: Literal["yelp", "google"],
        num_reviews: int = 20
    ) -> SerpApiResult:
        """
        One-shot method: find business and get reviews.

        This is the main entry point for review collection.
        """
        logger.info(f"SerpAPI: Finding {business_name} on {source} in {location}")

        # Step 1: Search for business
        if source == "yelp":
            search_result = self.search_yelp(business_name, location)
        else:
            search_result = self.search_google_maps(business_name, location)

        if not search_result.success or not search_result.business:
            return SerpApiResult(
                success=False,
                error=search_result.error or f"Business not found on {source}",
                raw_response=search_result.raw_response
            )

        business = search_result.business
        logger.info(f"SerpAPI: Found {business.name} (id: {business.place_id})")

        # Step 2: Get reviews
        if source == "yelp":
            reviews_result = self.get_yelp_reviews(business.place_id, num_reviews)
        else:
            reviews_result = self.get_google_reviews(business.place_id, num_reviews)

        if not reviews_result.success:
            # Return business info even if reviews failed
            return SerpApiResult(
                success=True,  # Partial success - we found the business
                business=business,
                reviews=[],
                error=f"Found business but couldn't get reviews: {reviews_result.error}",
                raw_response=reviews_result.raw_response
            )

        # Merge business info (reviews endpoint often has more details)
        final_business = reviews_result.business or business
        final_business.place_id = business.place_id  # Keep original place_id

        logger.info(f"SerpAPI: Got {len(reviews_result.reviews)} reviews for {final_business.name}")

        return SerpApiResult(
            success=True,
            business=final_business,
            reviews=reviews_result.reviews,
            raw_response=reviews_result.raw_response
        )


# Singleton instance
_service: Optional[SerpApiService] = None


def get_serpapi_service() -> SerpApiService:
    """Get or create the SerpAPI service singleton."""
    global _service
    if _service is None:
        _service = SerpApiService()
    return _service
