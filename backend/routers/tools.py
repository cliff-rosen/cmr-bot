"""
Tools testing endpoints.

Simple endpoints for testing backend services directly.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from database import get_db
from models import User
from routers.auth import get_current_user
from services.pubmed_service import PubMedService
from services.gmail_service import GmailService, GmailServiceError, NotConnectedError
from tools import get_all_tools, get_tools_by_category

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tools", tags=["tools"])


# ============================================================================
# Tool Registry API
# ============================================================================

class ToolInfo(BaseModel):
    """Information about a registered tool."""
    name: str
    description: str
    category: str
    input_schema: Dict[str, Any]
    output_schema: Optional[Dict[str, Any]] = None
    streaming: bool


class ToolListResponse(BaseModel):
    """Response containing list of available tools."""
    tools: List[ToolInfo]
    categories: List[str]


@router.get("/list", response_model=ToolListResponse)
async def list_tools(
    category: Optional[str] = None,
    current_user: User = Depends(get_current_user)
) -> ToolListResponse:
    """
    List all available tools with their documentation.

    Optionally filter by category.
    """
    if category:
        tools = get_tools_by_category(category)
    else:
        tools = get_all_tools()

    # Get unique categories
    all_tools = get_all_tools()
    categories = sorted(set(t.category for t in all_tools))

    tool_infos = [
        ToolInfo(
            name=tool.name,
            description=tool.description,
            category=tool.category,
            input_schema=tool.input_schema,
            output_schema=tool.output_schema,
            streaming=tool.streaming
        )
        for tool in tools
    ]

    # Sort by category then name
    tool_infos.sort(key=lambda t: (t.category, t.name))

    return ToolListResponse(
        tools=tool_infos,
        categories=categories
    )


# ============================================================================
# PubMed Search
# ============================================================================

class PubMedSearchRequest(BaseModel):
    """Request model for PubMed search."""
    query: str
    max_results: int = 10
    sort_by: str = "relevance"
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class PubMedArticleResponse(BaseModel):
    """Response model for a single PubMed article."""
    pmid: Optional[str]
    title: str
    authors: List[str]
    journal: Optional[str]
    publication_date: Optional[str]
    abstract: Optional[str]
    url: Optional[str]


class PubMedSearchResponse(BaseModel):
    """Response model for PubMed search."""
    success: bool
    query: str
    total_results: int
    returned: int
    articles: List[PubMedArticleResponse]
    error: Optional[str] = None


@router.post("/pubmed/search", response_model=PubMedSearchResponse)
async def search_pubmed(
    request: PubMedSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> PubMedSearchResponse:
    """
    Search PubMed for articles.

    This is a simple testing endpoint that directly calls the PubMed service.
    """
    try:
        service = PubMedService()

        articles, metadata = service.search_articles(
            query=request.query,
            max_results=min(request.max_results, 50),
            offset=0,
            sort_by=request.sort_by,
            start_date=request.start_date,
            end_date=request.end_date
        )

        total_results = metadata.get("total_results", 0)

        article_responses = [
            PubMedArticleResponse(
                pmid=article.pmid,
                title=article.title,
                authors=article.authors or [],
                journal=article.journal,
                publication_date=article.publication_date,
                abstract=article.abstract,
                url=f"https://pubmed.ncbi.nlm.nih.gov/{article.pmid}/" if article.pmid else None
            )
            for article in articles
        ]

        return PubMedSearchResponse(
            success=True,
            query=request.query,
            total_results=total_results,
            returned=len(articles),
            articles=article_responses
        )

    except ValueError as e:
        logger.warning(f"PubMed search validation error: {e}")
        return PubMedSearchResponse(
            success=False,
            query=request.query,
            total_results=0,
            returned=0,
            articles=[],
            error=str(e)
        )
    except Exception as e:
        logger.error(f"PubMed search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Gmail Search
# ============================================================================

class GmailSearchRequest(BaseModel):
    """Request model for Gmail search."""
    query: str
    max_results: int = 10


class GmailMessageResponse(BaseModel):
    """Response model for a single Gmail message."""
    id: str
    thread_id: str
    subject: str
    sender: str
    date: str
    snippet: str
    labels: List[str]


class GmailSearchResponse(BaseModel):
    """Response model for Gmail search."""
    success: bool
    query: str
    count: int
    messages: List[GmailMessageResponse]
    error: Optional[str] = None


@router.post("/gmail/search", response_model=GmailSearchResponse)
async def search_gmail(
    request: GmailSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> GmailSearchResponse:
    """
    Search Gmail for messages.

    This is a simple testing endpoint that directly calls the Gmail service.
    """
    try:
        service = GmailService(db, current_user.user_id)
        messages = service.search_messages(
            query=request.query,
            max_results=min(request.max_results, 50)
        )

        message_responses = [
            GmailMessageResponse(
                id=msg.id,
                thread_id=msg.thread_id,
                subject=msg.subject,
                sender=msg.sender,
                date=msg.date,
                snippet=msg.snippet,
                labels=msg.labels
            )
            for msg in messages
        ]

        return GmailSearchResponse(
            success=True,
            query=request.query,
            count=len(messages),
            messages=message_responses
        )

    except NotConnectedError as e:
        return GmailSearchResponse(
            success=False,
            query=request.query,
            count=0,
            messages=[],
            error=str(e)
        )
    except GmailServiceError as e:
        logger.error(f"Gmail search error: {e}", exc_info=True)
        return GmailSearchResponse(
            success=False,
            query=request.query,
            count=0,
            messages=[],
            error=str(e)
        )
    except Exception as e:
        logger.error(f"Gmail search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
