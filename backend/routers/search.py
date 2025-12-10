"""
Search Router

This router provides REST API endpoints for web search functionality.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

import logging

from schemas.base import CanonicalSearchResult

from services.auth_service import validate_token
from services.search_service import SearchService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/search", tags=["search"])

# Singleton service instance
search_service = SearchService()

##########################
### Request/Response Models ###
##########################

class SearchRequest(BaseModel):
    """Request model for web search"""
    search_term: str = Field(..., description="The search term to look up on the web")
    num_results: int = Field(default=10, description="Number of search results to return", ge=1, le=50)
    date_range: str = Field(default="all", description="Date range for search results")
    region: str = Field(default="global", description="Geographic region for search results")
    language: str = Field(default="en", description="Language for search results")

class SearchResultsData(BaseModel):
    """API response data structure for search results"""
    search_results: List[CanonicalSearchResult]
    query: str
    total_results: int
    search_time: int
    timestamp: str
    search_engine: Optional[str] = None

class SearchResponse(BaseModel):
    """Response model for web search"""
    success: bool
    data: Optional[SearchResultsData] = None
    error: Optional[str] = None
    message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class SearchStatus(BaseModel):
    """Response model for search service status"""
    authenticated: bool
    search_engine: Optional[str] = None
    credentials_configured: bool = False
    message: Optional[str] = None

##########################
### Search Endpoints ###
##########################

@router.post("/", response_model=SearchResponse)
async def perform_search(
    request: SearchRequest,
    user = Depends(validate_token)
):
    """
    Perform a web search using the configured search engine
    
    Args:
        request: Search request parameters
        user: Authenticated user
        
    Returns:
        SearchResponse with search results and metadata
    """
    try:
        # Initialize search service (uses app-level API keys from settings)
        if not search_service.initialized:
            if not search_service.initialize():
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Search service could not be initialized. Please check server configuration."
                )
            
        # Perform search
        result = await search_service.search(
            search_term=request.search_term,
            num_results=request.num_results,
            date_range=request.date_range,
            region=request.region,
            language=request.language
        )
        
        # Convert service result to API response data
        search_data = SearchResultsData(
            search_results=result["search_results"],
            query=result["query"],
            total_results=result["total_results"],
            search_time=result["search_time"],
            timestamp=result["timestamp"],
            search_engine=result["search_engine"]
        )
        
        return SearchResponse(
            success=True,
            data=search_data,
            message=f"Found {len(result['search_results'])} results for '{request.search_term}'",
            metadata={
                'query_params': request.model_dump(),
                'search_engine': search_service.search_engine,
                'timestamp': datetime.utcnow().isoformat()
            }
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Error performing search: {str(e)}")
        return SearchResponse(
            success=False,
            error=str(e),
            message=f"Search failed for '{request.search_term}'"
        )

@router.get("/status", response_model=SearchStatus)
async def get_search_status(
    user = Depends(validate_token)
):
    """
    Get the current status of the search service
    
    Args:
        user: Authenticated user
        
    Returns:
        SearchStatus with service configuration info
    """
    try:
        # Check if search service can be initialized with app-level settings
        service_initialized = search_service.initialized
        search_engine = None
        message = None
        
        if not service_initialized:
            try:
                service_initialized = search_service.initialize()
            except Exception as e:
                message = f"Initialization error: {str(e)}"
        
        if service_initialized:
            search_engine = search_service.search_engine
            message = f"Search service ready with {search_engine}"
        else:
            message = "Search service not properly configured"
        
        return SearchStatus(
            authenticated=service_initialized,
            search_engine=search_engine,
            credentials_configured=service_initialized,
            message=message
        )
        
    except Exception as e:
        logger.error(f"Error checking search status: {str(e)}")
        return SearchStatus(
            authenticated=False,
            credentials_configured=False,
            message=f"Error checking status: {str(e)}"
        )

@router.get("/engines", response_model=List[Dict[str, Any]])
async def get_supported_search_engines(
    user = Depends(validate_token)
):
    """
    Get list of supported search engines
    
    Args:
        user: Authenticated user
        
    Returns:
        List of supported search engines with their requirements
    """
    return [
        {
            "name": "google",
            "display_name": "Google Custom Search",
            "description": "Google Custom Search API with high-quality results",
            "requires_api_key": True,
            "requires_custom_search_id": True,
            "features": ["date_range", "region", "language"],
            "rate_limits": {
                "requests_per_day": 100,
                "requests_per_second": 10
            }
        },
        {
            "name": "duckduckgo",
            "display_name": "DuckDuckGo",
            "description": "Privacy-focused search with instant answers",
            "requires_api_key": False,
            "requires_custom_search_id": False,
            "features": ["region"],
            "rate_limits": {
                "requests_per_day": 1000,
                "requests_per_second": 1
            }
        }
    ]

@router.post("/validate", response_model=SearchResponse)
async def validate_search_service(
    user = Depends(validate_token)
):
    """
    Validate the search service configuration by performing a test search
    
    Args:
        user: Authenticated user
        
    Returns:
        SearchResponse indicating whether search service is working
    """
    try:
        # Initialize search service
        if not search_service.initialized:
            if not search_service.initialize():
                return SearchResponse(
                    success=False,
                    error="Initialization failed",
                    message="Unable to initialize search service with current configuration"
                )
            
        # Perform a simple test search
        test_result = await search_service.search(
            search_term="test",
            num_results=1
        )
        
        if test_result["search_results"]:
            # Convert service result to API response data
            search_data = SearchResultsData(
                search_results=test_result["search_results"],
                query=test_result["query"],
                total_results=test_result["total_results"],
                search_time=test_result["search_time"],
                timestamp=test_result["timestamp"],
                search_engine=test_result["search_engine"]
            )
            
            return SearchResponse(
                success=True,
                data=search_data,
                message=f"Search service validated successfully with {search_service.search_engine}",
                metadata={
                    'search_engine': search_service.search_engine,
                    'test_search_time': test_result["search_time"],
                    'results_count': len(test_result["search_results"])
                }
            )
        else:
            return SearchResponse(
                success=False,
                error="No results returned",
                message="Search service appears to be configured but no results were returned"
            )
            
    except Exception as e:
        logger.error(f"Error validating search service: {str(e)}")
        return SearchResponse(
            success=False,
            error=str(e),
            message="Error validating search service"
        )

##########################
### Search History (Optional) ###
##########################

# Note: These endpoints would require a search history table in the database
# For now, they're commented out as placeholders

# @router.get("/history", response_model=List[Dict[str, Any]])
# async def get_search_history(
#     user = Depends(validate_token),
#     db: Session = Depends(get_db),
#     limit: int = 10
# ):
#     """Get recent search history for the user"""
#     # Implementation would query a search_history table
#     return []

# @router.delete("/history/{search_id}")
# async def delete_search_history_item(
#     search_id: str,
#     user = Depends(validate_token),
#     db: Session = Depends(get_db)
# ):
#     """Delete a specific search history item"""
#     # Implementation would delete from search_history table
#     return {"message": "Search history item deleted"} 