"""
Tools testing endpoints.

Simple endpoints for testing backend services directly.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session

from database import get_db
from models import User
from routers.auth import get_current_user
from services.pubmed_service import PubMedService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tools", tags=["tools"])


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
