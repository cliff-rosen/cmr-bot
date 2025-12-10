"""
Web Retrieval Router

This router provides REST API endpoints for web page retrieval functionality.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl
import logging

from services.auth_service import validate_token
from services.web_retrieval_service import WebRetrievalService, WebRetrievalServiceResult, CanonicalWebpage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/web-retrieval", tags=["web-retrieval"])

# Singleton service instance
web_retrieval_service = WebRetrievalService()

##########################
### Request/Response Models ###
##########################

class WebRetrievalRequest(BaseModel):
    """Request model for single webpage retrieval"""
    url: HttpUrl = Field(..., description="The webpage URL to retrieve")
    extract_text_only: bool = Field(default=True, description="Whether to extract only text content or include HTML")
    timeout: int = Field(default=30, description="Request timeout in seconds", ge=1, le=120)
    user_agent: Optional[str] = Field(default=None, description="Custom user agent string")

class MultipleWebRetrievalRequest(BaseModel):
    """Request model for multiple webpage retrieval"""
    urls: List[HttpUrl] = Field(..., description="List of webpage URLs to retrieve", min_items=1, max_items=10)
    extract_text_only: bool = Field(default=True, description="Whether to extract only text content or include HTML")
    timeout: int = Field(default=30, description="Request timeout in seconds", ge=1, le=120)
    user_agent: Optional[str] = Field(default=None, description="Custom user agent string")
    max_concurrent: int = Field(default=5, description="Maximum concurrent requests", ge=1, le=10)

class WebRetrievalResponseData(BaseModel):
    """API response data structure for single webpage retrieval"""
    webpage: CanonicalWebpage
    status_code: int
    response_time: int
    timestamp: str

class WebRetrievalResponse(BaseModel):
    """Response model for single webpage retrieval"""
    success: bool
    data: Optional[WebRetrievalResponseData] = None
    error: Optional[str] = None
    message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class MultipleWebRetrievalResponseData(BaseModel):
    """API response data structure for multiple webpage retrieval"""
    webpages: List[WebRetrievalResponseData]
    total_requested: int
    total_successful: int
    total_failed: int
    total_time: int
    timestamp: str

class MultipleWebRetrievalResponse(BaseModel):
    """Response model for multiple webpage retrieval"""
    success: bool
    data: Optional[MultipleWebRetrievalResponseData] = None
    error: Optional[str] = None
    message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

##########################
### Web Retrieval Endpoints ###
##########################

@router.post("/", response_model=WebRetrievalResponse)
async def retrieve_webpage(
    request: WebRetrievalRequest,
    user = Depends(validate_token)
):
    """
    Retrieve and parse a single webpage
    
    Args:
        request: Web retrieval request parameters
        user: Authenticated user
        
    Returns:
        WebRetrievalResponse with webpage content and metadata
    """
    try:
        # Convert HttpUrl to string for service call
        url_str = str(request.url)
        
        # Retrieve webpage using the service
        result = await web_retrieval_service.retrieve_webpage(
            url=url_str,
            extract_text_only=request.extract_text_only,
            timeout=request.timeout,
            user_agent=request.user_agent
        )
        
        # Convert service result to API response data
        response_data = WebRetrievalResponseData(
            webpage=result["webpage"],
            status_code=result["status_code"],
            response_time=result["response_time"],
            timestamp=result["timestamp"]
        )
        
        return WebRetrievalResponse(
            success=True,
            data=response_data,
            message=f"Successfully retrieved webpage: {result['webpage'].title}",
            metadata={
                'request_params': request.model_dump(),
                'url': url_str,
                'timestamp': datetime.utcnow().isoformat()
            }
        )
        
    except ValueError as e:
        # Handle validation errors
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error retrieving webpage {request.url}: {str(e)}")
        return WebRetrievalResponse(
            success=False,
            error=str(e),
            message=f"Failed to retrieve webpage: {request.url}"
        )

@router.post("/multiple", response_model=MultipleWebRetrievalResponse)
async def retrieve_multiple_webpages(
    request: MultipleWebRetrievalRequest,
    user = Depends(validate_token)
):
    """
    Retrieve and parse multiple webpages concurrently
    
    Args:
        request: Multiple web retrieval request parameters
        user: Authenticated user
        
    Returns:
        MultipleWebRetrievalResponse with multiple webpage contents and metadata
    """
    try:
        # Convert HttpUrl objects to strings for service call
        url_strings = [str(url) for url in request.urls]
        
        start_time = datetime.utcnow()
        
        # Retrieve multiple webpages using the service
        results = await web_retrieval_service.retrieve_multiple_pages(
            urls=url_strings,
            extract_text_only=request.extract_text_only,
            timeout=request.timeout,
            user_agent=request.user_agent,
            max_concurrent=request.max_concurrent
        )
        
        end_time = datetime.utcnow()
        total_time_ms = int((end_time - start_time).total_seconds() * 1000)
        
        # Convert service results to API response data
        webpage_data = []
        successful_count = 0
        failed_count = 0
        
        for result in results:
            if result:  # Successful retrieval
                webpage_data.append(WebRetrievalResponseData(
                    webpage=result["webpage"],
                    status_code=result["status_code"],
                    response_time=result["response_time"],
                    timestamp=result["timestamp"]
                ))
                successful_count += 1
            else:  # Failed retrieval
                failed_count += 1
        
        response_data = MultipleWebRetrievalResponseData(
            webpages=webpage_data,
            total_requested=len(request.urls),
            total_successful=successful_count,
            total_failed=failed_count,
            total_time=total_time_ms,
            timestamp=datetime.utcnow().isoformat()
        )
        
        return MultipleWebRetrievalResponse(
            success=True,
            data=response_data,
            message=f"Retrieved {successful_count} of {len(request.urls)} webpages successfully",
            metadata={
                'request_params': request.model_dump(),
                'urls': url_strings,
                'timestamp': datetime.utcnow().isoformat()
            }
        )
        
    except ValueError as e:
        # Handle validation errors
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error retrieving multiple webpages: {str(e)}")
        return MultipleWebRetrievalResponse(
            success=False,
            error=str(e),
            message=f"Failed to retrieve webpages"
        )

@router.get("/status")
async def get_web_retrieval_status(
    user = Depends(validate_token)
):
    """
    Get the current status of the web retrieval service
    
    Args:
        user: Authenticated user
        
    Returns:
        Status information about the web retrieval service
    """
    try:
        return {
            "service_available": True,
            "default_timeout": web_retrieval_service.default_timeout,
            "default_user_agent": web_retrieval_service.default_user_agent,
            "message": "Web retrieval service is operational",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error checking web retrieval status: {str(e)}")
        return {
            "service_available": False,
            "message": f"Error checking status: {str(e)}",
            "timestamp": datetime.utcnow().isoformat()
        } 