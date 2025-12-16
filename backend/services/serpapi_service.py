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

    def _make_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make a request to SerpAPI."""
        params["api_key"] = self.api_key
        params["output"] = "json"

        with httpx.Client(timeout=30.0) as client:
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
        num_reviews: int = 20
    ) -> SerpApiResult:
        """
        Get reviews for a Yelp business.

        Args:
            place_id: The Yelp biz_id (e.g., "WavvLdfdP6g8aZTtbBQHTw")
            num_reviews: Number of reviews to fetch (max ~20 per page)
        """
        if not self.api_key:
            return SerpApiResult(success=False, error="SERPAPI_KEY not configured")

        try:
            params = {
                "engine": "yelp_reviews",
                "place_id": place_id,
            }

            data = self._make_request(params)

            reviews = []
            for r in data.get("reviews", []):
                review = SerpApiReview(
                    rating=r.get("rating"),
                    text=r.get("comment", {}).get("text", "") or r.get("text", ""),
                    author=r.get("user", {}).get("name"),
                    date=r.get("date"),
                    source="yelp"
                )
                if review.text:
                    reviews.append(review)

            # Also get business info if available
            biz_info = data.get("business_info", {})
            business = None
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

            return SerpApiResult(
                success=True,
                business=business,
                reviews=reviews[:num_reviews],
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

            # Parse local results
            businesses = []
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
        num_reviews: int = 20
    ) -> SerpApiResult:
        """
        Get reviews for a Google Maps place.

        Args:
            data_id: The Google data_id (e.g., "0x89c259a61c75684f:0x79d31adb19735291")
            num_reviews: Number of reviews to fetch
        """
        if not self.api_key:
            return SerpApiResult(success=False, error="SERPAPI_KEY not configured")

        try:
            params = {
                "engine": "google_maps_reviews",
                "data_id": data_id,
            }

            data = self._make_request(params)

            reviews = []
            for r in data.get("reviews", []):
                review = SerpApiReview(
                    rating=r.get("rating"),
                    text=r.get("snippet", "") or r.get("extracted_snippet", {}).get("original", ""),
                    author=r.get("user", {}).get("name"),
                    date=r.get("date"),
                    source="google"
                )
                if review.text:
                    reviews.append(review)

            # Get place info
            place_info = data.get("place_info", {})
            business = None
            if place_info:
                business = SerpApiBusiness(
                    name=place_info.get("title", ""),
                    place_id=data_id,
                    rating=place_info.get("rating"),
                    review_count=place_info.get("reviews"),
                    address=place_info.get("address"),
                    source="google"
                )

            return SerpApiResult(
                success=True,
                business=business,
                reviews=reviews[:num_reviews],
                raw_response=data
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
